"""
MySQL 关系数据库实现。
图查询依赖递归 CTE（需要 MySQL 8.0+）。
内置事务控制 + 操作审计 + 用户管理 + 导入批次追踪。
"""
import json
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pymysql

try:
    from .schemas import Entity, Relation
    from .store_base import GraphStore
except ImportError:
    from schemas import Entity, Relation
    from store_base import GraphStore


class MySQLStore(GraphStore):
    def __init__(self, host: str = "localhost", port: int = 3306,
                 user: str = "root", password: str = "", database: str = "tcm"):
        self._conn_params = {
            "host": host, "port": port, "user": user, "password": password,
            "charset": "utf8mb4", "cursorclass": pymysql.cursors.DictCursor,
            "autocommit": False,  # 由上层控制事务边界
        }
        # 先连接无库模式，自动建库
        conn = pymysql.connect(
            host=host, port=port, user=user, password=password,
            charset="utf8mb4", autocommit=True,
        )
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.close()

        self._conn_params["database"] = database
        self._local = threading.local()
        self._init_tables()

    # ---------- 连接管理 ----------
    def _get_conn(self) -> pymysql.Connection:
        """获取当前线程的数据库连接，自动重连。"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = pymysql.connect(**self._conn_params)
            return self._local.conn
        try:
            self._local.conn.ping(reconnect=True)
        except Exception:
            self._local.conn = pymysql.connect(**self._conn_params)
        return self._local.conn

    @contextmanager
    def transaction(self):
        """事务上下文管理器，自动 begin / commit / rollback。"""
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def begin(self):
        """显式开始事务（HybridStore 两阶段提交时使用）。"""
        # pymysql autocommit=False 时 SQL 自动开始事务，显式 BEGIN 只是为了代码可读性
        self._get_conn()

    def commit(self):
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.commit()

    def rollback(self):
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.rollback()

    # ---------- 建表 ----------
    def _init_tables(self) -> None:
        with self._get_conn().cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id VARCHAR(10) PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    type VARCHAR(20) NOT NULL,
                    alias VARCHAR(500) DEFAULT '',
                    description TEXT,
                    props_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_type (type),
                    INDEX idx_name (name)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS relations (
                    source_id VARCHAR(10) NOT NULL,
                    source_name VARCHAR(200) DEFAULT '',
                    relation VARCHAR(20) NOT NULL,
                    target_id VARCHAR(10) NOT NULL,
                    target_name VARCHAR(200) DEFAULT '',
                    evidence TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (source_id, relation, target_id),
                    INDEX idx_src (source_id),
                    INDEX idx_tgt (target_id),
                    INDEX idx_rel (relation)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            # 类型前缀表（自动发现新类型时记录）
            cur.execute("""
                CREATE TABLE IF NOT EXISTS type_prefixes (
                    type VARCHAR(50) PRIMARY KEY,
                    prefix VARCHAR(5) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            # 用户表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password_hash VARCHAR(256) NOT NULL,
                    role VARCHAR(20) NOT NULL DEFAULT 'user',
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_login DATETIME
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            # 操作日志
            cur.execute("""
                CREATE TABLE IF NOT EXISTS operation_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    username VARCHAR(50),
                    action VARCHAR(20) NOT NULL,
                    target_type VARCHAR(20) NOT NULL,
                    target_id VARCHAR(50) NOT NULL,
                    target_name VARCHAR(200) DEFAULT '',
                    before_snapshot JSON,
                    after_snapshot JSON,
                    ip_address VARCHAR(45) DEFAULT '',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user (user_id),
                    INDEX idx_action (action),
                    INDEX idx_target (target_type, target_id),
                    INDEX idx_time (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            # 导入批次
            cur.execute("""
                CREATE TABLE IF NOT EXISTS import_batches (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL DEFAULT 0,
                    username VARCHAR(50) DEFAULT '',
                    kind VARCHAR(20) NOT NULL,
                    file_name VARCHAR(200) DEFAULT '',
                    total INT DEFAULT 0,
                    success INT DEFAULT 0,
                    failed INT DEFAULT 0,
                    errors_json JSON,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_time (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        self._get_conn().commit()

    # ========== 实体 ==========
    def upsert_entity(self, e: Entity) -> Entity:
        with self._get_conn().cursor() as cur:
            cur.execute("""
                INSERT INTO entities (id, name, type, alias, description, props_json)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    name=VALUES(name), type=VALUES(type), alias=VALUES(alias),
                    description=VALUES(description), props_json=VALUES(props_json)
            """, (e.id, e.name, e.type, e.alias, e.description,
                  json.dumps(e.properties, ensure_ascii=False)))
            cur.execute(
                "UPDATE relations SET source_name=%s WHERE source_id=%s",
                (e.name, e.id))
            cur.execute(
                "UPDATE relations SET target_name=%s WHERE target_id=%s",
                (e.name, e.id))
        return e

    def get_entity(self, eid: str) -> Optional[Entity]:
        with self._get_conn().cursor() as cur:
            cur.execute("SELECT * FROM entities WHERE id=%s", (eid,))
            row = cur.fetchone()
        return self._row_to_entity(row) if row else None

    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        with self._get_conn().cursor() as cur:
            cur.execute(
                "SELECT * FROM entities WHERE name=%s OR alias LIKE %s LIMIT 1",
                (name, f"%{name}%"))
            row = cur.fetchone()
        return self._row_to_entity(row) if row else None

    def delete_entity(self, eid: str) -> bool:
        with self._get_conn().cursor() as cur:
            cur.execute("DELETE FROM relations WHERE source_id=%s OR target_id=%s",
                        (eid, eid))
            cur.execute("DELETE FROM entities WHERE id=%s", (eid,))
            deleted = cur.rowcount > 0
        return deleted

    def list_entities(self, type_, keyword, page, size) -> Tuple[int, List[Entity]]:
        where, params = ["1=1"], []
        if type_:
            where.append("type=%s"); params.append(type_)
        if keyword:
            where.append("(name LIKE %s OR alias LIKE %s OR description LIKE %s)")
            params.extend([f"%{keyword}%"] * 3)
        w = " AND ".join(where)
        with self._get_conn().cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS c FROM entities WHERE {w}", params)
            total = cur.fetchone()["c"]
            cur.execute(
                f"SELECT * FROM entities WHERE {w} ORDER BY id LIMIT %s OFFSET %s",
                params + [size, (page - 1) * size])
            items = [self._row_to_entity(r) for r in cur.fetchall()]
        return total, items

    def next_id(self, type_: str) -> str:
        prefix = self._ensure_type_prefix(type_)
        with self._get_conn().cursor() as cur:
            cur.execute(
                "SELECT id FROM entities WHERE id LIKE %s ORDER BY id DESC LIMIT 1",
                (f"{prefix}%",))
            row = cur.fetchone()
        if not row:
            return f"{prefix}001"
        tail = row["id"][len(prefix):]
        return f"{prefix}{(int(tail) + 1 if tail.isdigit() else 1):03d}"

    def _ensure_type_prefix(self, type_: str) -> str:
        """获取类型前缀，若新类型则自动生成并持久化。"""
        from server.schemas import auto_prefix, get_type_prefixes
        known = get_type_prefixes()
        if type_ in known:
            return known[type_]
        with self._get_conn().cursor() as cur:
            cur.execute("SELECT prefix FROM type_prefixes WHERE type=%s", (type_,))
            row = cur.fetchone()
            if row:
                return row["prefix"]
        prefix = auto_prefix(type_)
        with self._get_conn().cursor() as cur:
            cur.execute(
                "INSERT IGNORE INTO type_prefixes (type, prefix) VALUES (%s, %s)",
                (type_, prefix))
        self._get_conn().commit()
        return prefix

    def list_type_prefixes(self):
        """返回所有已注册的类型→前缀映射。"""
        with self._get_conn().cursor() as cur:
            cur.execute("SELECT type, prefix FROM type_prefixes")
            return cur.fetchall()

    # ========== 关系 ==========
    def upsert_relation(self, r: Relation) -> Relation:
        with self._get_conn().cursor() as cur:
            cur.execute("""
                INSERT INTO relations (source_id, source_name, relation, target_id, target_name, evidence)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    source_name=VALUES(source_name), target_name=VALUES(target_name),
                    evidence=VALUES(evidence)
            """, (r.source_id, r.source_name, r.relation,
                  r.target_id, r.target_name, r.evidence))
        return r

    def delete_relation(self, source_id, relation, target_id) -> bool:
        with self._get_conn().cursor() as cur:
            cur.execute(
                "DELETE FROM relations WHERE source_id=%s AND relation=%s AND target_id=%s",
                (source_id, relation, target_id))
            deleted = cur.rowcount > 0
        return deleted

    def list_relations(self, source_id, target_id, relation, page, size):
        where, params = ["1=1"], []
        if source_id:
            where.append("source_id=%s"); params.append(source_id)
        if target_id:
            where.append("target_id=%s"); params.append(target_id)
        if relation:
            where.append("relation=%s"); params.append(relation)
        w = " AND ".join(where)
        with self._get_conn().cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS c FROM relations WHERE {w}", params)
            total = cur.fetchone()["c"]
            cur.execute(
                f"SELECT * FROM relations WHERE {w} ORDER BY source_id LIMIT %s OFFSET %s",
                params + [size, (page - 1) * size])
            items = [self._row_to_relation(r) for r in cur.fetchall()]
        return total, items

    # ========== 图查询 ==========
    def neighbors(self, eid, relation, limit) -> Tuple[List[Entity], List[Relation]]:
        rel_where = "AND r.relation=%s" if relation else ""
        params = [eid, eid] + ([relation] if relation else []) + [limit]
        with self._get_conn().cursor() as cur:
            cur.execute(f"""
                SELECT DISTINCT r.* FROM relations r
                WHERE (r.source_id=%s OR r.target_id=%s) {rel_where}
                LIMIT %s
            """, params)
            rels = [self._row_to_relation(r) for r in cur.fetchall()]
        ids = {eid} | {r.source_id for r in rels} | {r.target_id for r in rels}
        ents = [self.get_entity(i) for i in ids]
        return [e for e in ents if e], rels

    def subgraph(self, eid, depth, limit) -> Tuple[List[Entity], List[Relation]]:
        if not self.get_entity(eid):
            return [], []
        with self._get_conn().cursor() as cur:
            cur.execute("""
                WITH RECURSIVE sub AS (
                    SELECT source_id, relation, target_id, 1 AS d
                    FROM relations
                    WHERE source_id=%s OR target_id=%s
                    UNION DISTINCT
                    SELECT r.source_id, r.relation, r.target_id, sub.d + 1
                    FROM relations r
                    JOIN sub ON (r.source_id = sub.source_id OR r.target_id = sub.target_id
                              OR r.source_id = sub.target_id OR r.target_id = sub.source_id)
                    WHERE sub.d < %s
                )
                SELECT DISTINCT * FROM sub LIMIT %s
            """, (eid, eid, depth, limit))
            rels = [self._row_to_relation(r) for r in cur.fetchall()]
        ids = {eid} | {r.source_id for r in rels} | {r.target_id for r in rels}
        ents = [self.get_entity(i) for i in ids]
        return [e for e in ents if e], rels

    def find_paths(self, source_id, target_id, max_depth, limit=5):
        with self._get_conn().cursor() as cur:
            cur.execute("""
                WITH RECURSIVE paths AS (
                    SELECT source_id, relation, target_id,
                           CONCAT(source_id, ',', target_id) AS visited,
                           CONCAT(source_id, '-', relation, '->', target_id) AS path,
                           1 AS depth
                    FROM relations
                    WHERE source_id=%s
                    UNION DISTINCT
                    SELECT r.source_id, r.relation, r.target_id,
                           CONCAT(p.visited, ',', r.target_id),
                           CONCAT(p.path, '|', r.source_id, '-', r.relation, '->', r.target_id),
                           p.depth + 1
                    FROM relations r
                    JOIN paths p ON r.source_id = p.target_id
                    WHERE p.depth < %s
                      AND FIND_IN_SET(r.target_id, p.visited) = 0
                )
                SELECT * FROM paths
                WHERE target_id=%s
                ORDER BY depth LIMIT %s
            """, (source_id, max_depth, target_id, limit))
            rows = cur.fetchall()
        out = []
        for row in rows:
            ids_in_path = row["visited"].split(",")
            rel_strings = row["path"].split("|")
            ents = [self.get_entity(i) for i in ids_in_path]
            ents = [e for e in ents if e]
            rels = []
            for rs in rel_strings:
                parts = rs.split("-")
                if len(parts) >= 3:
                    r = self._row_to_relation({
                        "source_id": parts[0], "relation": parts[1],
                        "target_id": parts[2],
                        "source_name": "", "target_name": "", "evidence": ""
                    })
                    rels.append(r)
            out.append((ents, rels))
        return out

    def clear(self) -> None:
        with self._get_conn().cursor() as cur:
            cur.execute("DELETE FROM relations")
            cur.execute("DELETE FROM entities")
        self._get_conn().commit()

    def stats(self) -> dict:
        with self._get_conn().cursor() as cur:
            cur.execute("SELECT type, COUNT(*) AS c FROM entities GROUP BY type")
            et = {r["type"]: r["c"] for r in cur.fetchall()}
            cur.execute("SELECT relation, COUNT(*) AS c FROM relations GROUP BY relation")
            rt = {r["relation"]: r["c"] for r in cur.fetchall()}
        return {
            "entity_count": sum(et.values()), "relation_count": sum(rt.values()),
            "entity_by_type": et, "relation_by_type": rt,
        }

    # ========== 用户管理 ==========
    def create_user(self, username: str, password_hash: str, role: str = "viewer") -> int:
        with self._get_conn().cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                (username, password_hash, role))
        self._get_conn().commit()
        return cur.lastrowid

    def get_user_by_username(self, username: str) -> Optional[dict]:
        with self._get_conn().cursor() as cur:
            cur.execute("SELECT * FROM users WHERE username=%s AND is_active=1", (username,))
            row = cur.fetchone()
        return row if row else None

    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        with self._get_conn().cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
            row = cur.fetchone()
        return row if row else None

    def update_last_login(self, user_id: int) -> None:
        with self._get_conn().cursor() as cur:
            cur.execute(
                "UPDATE users SET last_login=%s WHERE id=%s",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        self._get_conn().commit()

    def list_users(self) -> List[dict]:
        with self._get_conn().cursor() as cur:
            cur.execute(
                "SELECT id, username, role, is_active, created_at, last_login "
                "FROM users ORDER BY id")
            return cur.fetchall()

    def change_password(self, user_id: int, password_hash: str) -> bool:
        with self._get_conn().cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash=%s WHERE id=%s",
                (password_hash, user_id))
        self._get_conn().commit()
        return cur.rowcount > 0

    # ========== 操作审计 ==========
    def insert_operation_log(
        self, user_id: int = 0, username: str = "",
        action: str = "", target_type: str = "", target_id: str = "",
        target_name: str = "",
        before_snapshot: dict | None = None, after_snapshot: dict | None = None,
        ip_address: str = "",
    ) -> int:
        with self._get_conn().cursor() as cur:
            cur.execute(
                """INSERT INTO operation_log
                   (user_id, username, action, target_type, target_id, target_name,
                    before_snapshot, after_snapshot, ip_address)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    user_id, username, action, target_type, target_id, target_name,
                    json.dumps(before_snapshot, ensure_ascii=False) if before_snapshot else None,
                    json.dumps(after_snapshot, ensure_ascii=False) if after_snapshot else None,
                    ip_address,
                ))
        self._get_conn().commit()
        return cur.lastrowid

    def list_operation_log(
        self, user_id: int | None = None, action: str | None = None,
        target_type: str | None = None, target_id: str | None = None,
        page: int = 1, size: int = 20,
    ) -> Tuple[int, List[dict]]:
        where, params = ["1=1"], []
        if user_id:
            where.append("user_id=%s"); params.append(user_id)
        if action:
            where.append("action=%s"); params.append(action)
        if target_type:
            where.append("target_type=%s"); params.append(target_type)
        if target_id:
            where.append("target_id=%s"); params.append(target_id)
        w = " AND ".join(where)
        with self._get_conn().cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS c FROM operation_log WHERE {w}", params)
            total = cur.fetchone()["c"]
            cur.execute(
                f"SELECT * FROM operation_log WHERE {w} ORDER BY created_at DESC "
                f"LIMIT %s OFFSET %s",
                params + [size, (page - 1) * size])
            items = cur.fetchall()
        return total, items

    def get_operation_log(self, log_id: int) -> Optional[dict]:
        with self._get_conn().cursor() as cur:
            cur.execute("SELECT * FROM operation_log WHERE id=%s", (log_id,))
            return cur.fetchone()

    # ========== 导入批次 ==========
    def insert_import_batch(
        self, user_id: int = 0, username: str = "",
        kind: str = "entity", file_name: str = "",
        total: int = 0, success: int = 0, failed: int = 0,
        errors: list | None = None,
    ) -> int:
        with self._get_conn().cursor() as cur:
            cur.execute(
                """INSERT INTO import_batches
                   (user_id, username, kind, file_name, total, success, failed, errors_json)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    user_id, username, kind, file_name, total, success, failed,
                    json.dumps(errors, ensure_ascii=False) if errors else None,
                ))
        self._get_conn().commit()
        return cur.lastrowid

    def list_import_batches(self, page: int = 1, size: int = 20) -> Tuple[int, List[dict]]:
        with self._get_conn().cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM import_batches")
            total = cur.fetchone()["c"]
            cur.execute(
                "SELECT * FROM import_batches ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (size, (page - 1) * size))
            items = cur.fetchall()
        return total, items

    # ========== SQL 只读查询（供 SQL Agent） ==========
    def execute_readonly_sql(self, sql: str, params: list | None = None,
                              max_rows: int = 200) -> dict:
        """安全执行一条只读 SQL，返回 {rows, row_count}。"""
        import re
        normalized = re.sub(r"\s+", " ", sql.strip()).rstrip(";")
        if not re.match(r"^(SELECT|WITH|DESCRIBE|SHOW|EXPLAIN)\b", normalized, re.I):
            raise ValueError("只允许 SELECT/WITH/DESCRIBE/SHOW/EXPLAIN 查询")
        if ";" in normalized or re.search(
            r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|REPLACE)\b",
            normalized, re.I,
        ):
            raise ValueError("检测到不安全 SQL")
        limited = normalized if re.search(r"\bLIMIT\s+\d+", normalized, re.I) \
            else f"{normalized} LIMIT {max_rows}"
        with self._get_conn().cursor() as cur:
            cur.execute(limited, params or [])
            rows = cur.fetchmany(max_rows)
        return {"status": "success", "sql": limited, "rows": list(rows),
                "row_count": len(rows)}

    # ========== 同步到 SQLite（供组员 SQL Agent） ==========
    def sync_to_sqlite(self, db_path: str | None = None) -> None:
        """将 MySQL 图谱数据导出到 kg.sqlite，供组员 SQL Agent 查询。"""
        import sqlite3
        target = Path(db_path) if db_path else \
            Path(__file__).resolve().parents[2] / "backend" / "data" / "kg.sqlite"
        target.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(target))
        try:
            # 重建表
            conn.executescript("""
                DROP TABLE IF EXISTS entities;
                DROP TABLE IF EXISTS relations;
                DROP TABLE IF EXISTS metadata;
                CREATE TABLE entities (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL,
                    alias TEXT, description TEXT, properties_json TEXT
                );
                CREATE TABLE relations (
                    id TEXT PRIMARY KEY, source_id TEXT, source_name TEXT,
                    source_type TEXT, relation TEXT, target_id TEXT,
                    target_name TEXT, target_type TEXT, evidence TEXT
                );
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT);
                CREATE INDEX idx_entities_type ON entities(type);
                CREATE INDEX idx_entities_name ON entities(name);
                CREATE INDEX idx_relations_source ON relations(source_id);
                CREATE INDEX idx_relations_target ON relations(target_id);
            """)
            # 同步实体
            rows = []
            for e in self.list_entities(None, None, 1, 100000)[1]:
                rows.append((e.id, e.name, e.type, e.alias, e.description,
                             json.dumps(e.properties, ensure_ascii=False)))
            conn.executemany(
                "INSERT INTO entities VALUES (?,?,?,?,?,?)", rows)
            # 同步关系
            total, rels = self.list_relations(None, None, None, 1, 100000)
            rel_rows = []
            for r in rels:
                src = self.get_entity(r.source_id)
                tgt = self.get_entity(r.target_id)
                rid = f"{r.source_id}|{r.relation}|{r.target_id}"
                rel_rows.append((rid, r.source_id, r.source_name,
                                 src.type if src else "",
                                 r.relation, r.target_id, r.target_name,
                                 tgt.type if tgt else "", r.evidence))
            conn.executemany(
                "INSERT INTO relations VALUES (?,?,?,?,?,?,?,?,?)", rel_rows)
            conn.executemany(
                "INSERT INTO metadata VALUES (?,?)",
                [("entity_count", str(len(rows))),
                 ("relation_count", str(len(rel_rows))),
                 ("source", "mysql_auto_sync")])
            conn.commit()
        finally:
            conn.close()

    # ========== 辅助 ==========
    @staticmethod
    def _row_to_entity(row) -> Entity:
        return Entity(
            id=row["id"], name=row["name"], type=row["type"],
            alias=row.get("alias", "") or "",
            description=row.get("description", "") or "",
            properties=json.loads(row.get("props_json") or "{}"),
        )

    @staticmethod
    def _row_to_relation(row) -> Relation:
        return Relation(
            source_id=row["source_id"], source_name=row.get("source_name", "") or "",
            relation=row["relation"], target_id=row["target_id"],
            target_name=row.get("target_name", "") or "",
            evidence=row.get("evidence", "") or "",
        )
