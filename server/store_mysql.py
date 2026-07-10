"""
MySQL 关系数据库实现。
图查询依赖递归 CTE（需要 MySQL 8.0+）。
"""
import json
from typing import Dict, List, Optional, Tuple

import pymysql

try:
    from .schemas import Entity, Relation, TYPE_PREFIX
    from .store_base import GraphStore
except ImportError:
    from schemas import Entity, Relation, TYPE_PREFIX
    from store_base import GraphStore


class MySQLStore(GraphStore):
    def __init__(self, host: str = "localhost", port: int = 3306,
                 user: str = "root", password: str = "", database: str = "tcm"):
        # 先连接无库模式，自动建库
        conn = pymysql.connect(
            host=host, port=port, user=user, password=password,
            charset="utf8mb4",
        )
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4")
        conn.close()
        # 再连上目标库
        self.conn = pymysql.connect(
            host=host, port=port, user=user, password=password,
            database=database, charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        self._init_tables()

    def _init_tables(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id VARCHAR(10) PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    type VARCHAR(20) NOT NULL,
                    alias VARCHAR(500) DEFAULT '',
                    description TEXT,
                    props_json TEXT,
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
                    PRIMARY KEY (source_id, relation, target_id),
                    INDEX idx_src (source_id),
                    INDEX idx_tgt (target_id),
                    INDEX idx_rel (relation)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        self.conn.commit()

    # ========== 实体 ==========
    def upsert_entity(self, e: Entity) -> Entity:
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO entities (id, name, type, alias, description, props_json)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    name=VALUES(name), type=VALUES(type), alias=VALUES(alias),
                    description=VALUES(description), props_json=VALUES(props_json)
            """, (e.id, e.name, e.type, e.alias, e.description,
                  json.dumps(e.properties, ensure_ascii=False)))
            # 同步关系里的冗余名字
            cur.execute(
                "UPDATE relations SET source_name=%s WHERE source_id=%s",
                (e.name, e.id))
            cur.execute(
                "UPDATE relations SET target_name=%s WHERE target_id=%s",
                (e.name, e.id))
        self.conn.commit()
        return e

    def get_entity(self, eid: str) -> Optional[Entity]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM entities WHERE id=%s", (eid,))
            row = cur.fetchone()
        return self._row_to_entity(row) if row else None

    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM entities WHERE name=%s OR alias LIKE %s LIMIT 1",
                (name, f"%{name}%"))
            row = cur.fetchone()
        return self._row_to_entity(row) if row else None

    def delete_entity(self, eid: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM relations WHERE source_id=%s OR target_id=%s",
                        (eid, eid))
            cur.execute("DELETE FROM entities WHERE id=%s", (eid,))
            deleted = cur.rowcount > 0
        self.conn.commit()
        return deleted

    def list_entities(self, type_, keyword, page, size) -> Tuple[int, List[Entity]]:
        where, params = ["1=1"], []
        if type_:
            where.append("type=%s"); params.append(type_)
        if keyword:
            where.append("(name LIKE %s OR alias LIKE %s OR description LIKE %s)")
            params.extend([f"%{keyword}%"] * 3)
        w = " AND ".join(where)
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS c FROM entities WHERE {w}", params)
            total = cur.fetchone()["c"]
            cur.execute(
                f"SELECT * FROM entities WHERE {w} ORDER BY id LIMIT %s OFFSET %s",
                params + [size, (page - 1) * size])
            items = [self._row_to_entity(r) for r in cur.fetchall()]
        return total, items

    def next_id(self, type_: str) -> str:
        prefix = TYPE_PREFIX[type_]
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM entities WHERE id LIKE %s ORDER BY id DESC LIMIT 1",
                (f"{prefix}%",))
            row = cur.fetchone()
        if not row:
            return f"{prefix}001"
        tail = row["id"][len(prefix):]
        return f"{prefix}{(int(tail) + 1 if tail.isdigit() else 1):03d}"

    # ========== 关系 ==========
    def upsert_relation(self, r: Relation) -> Relation:
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO relations (source_id, source_name, relation, target_id, target_name, evidence)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    source_name=VALUES(source_name), target_name=VALUES(target_name),
                    evidence=VALUES(evidence)
            """, (r.source_id, r.source_name, r.relation,
                  r.target_id, r.target_name, r.evidence))
        self.conn.commit()
        return r

    def delete_relation(self, source_id, relation, target_id) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM relations WHERE source_id=%s AND relation=%s AND target_id=%s",
                (source_id, relation, target_id))
            deleted = cur.rowcount > 0
        self.conn.commit()
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
        with self.conn.cursor() as cur:
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
        with self.conn.cursor() as cur:
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
        with self.conn.cursor() as cur:
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
        with self.conn.cursor() as cur:
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
            # Parse the path string back into entities and relations
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
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM relations")
            cur.execute("DELETE FROM entities")
        self.conn.commit()

    def stats(self) -> dict:
        with self.conn.cursor() as cur:
            cur.execute("SELECT type, COUNT(*) AS c FROM entities GROUP BY type")
            et = {r["type"]: r["c"] for r in cur.fetchall()}
            cur.execute("SELECT relation, COUNT(*) AS c FROM relations GROUP BY relation")
            rt = {r["relation"]: r["c"] for r in cur.fetchall()}
        return {
            "entity_count": sum(et.values()), "relation_count": sum(rt.values()),
            "entity_by_type": et, "relation_by_type": rt,
        }

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
