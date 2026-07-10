"""
Neo4j 实现。图模型：
  节点  (:Entity {id, name, type, alias, description, props_json})
  关系  (:Entity)-[:REL {relation, evidence}]->(:Entity)
用统一的 :REL 关系类型 + relation 属性，写变长路径查询时最省事。
"""
import json
from typing import List, Optional, Tuple

from neo4j import GraphDatabase

try:
    from .schemas import Entity, Relation, TYPE_PREFIX
    from .store_base import GraphStore
except ImportError:
    from schemas import Entity, Relation, TYPE_PREFIX
    from store_base import GraphStore


def _to_entity(node) -> Entity:
    return Entity(
        id=node["id"], name=node["name"], type=node["type"],
        alias=node.get("alias", "") or "", description=node.get("description", "") or "",
        properties=json.loads(node.get("props_json") or "{}"),
    )


class Neo4jStore(GraphStore):
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database
        self.init_schema()

    def close(self):
        self.driver.close()

    def _run(self, cypher: str, **params):
        with self.driver.session(database=self.database) as s:
            return list(s.run(cypher, **params))

    def init_schema(self) -> None:
        self._run("CREATE CONSTRAINT entity_id IF NOT EXISTS "
                  "FOR (e:Entity) REQUIRE e.id IS UNIQUE")
        self._run("CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)")
        self._run("CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)")

    # ---------- 实体 ----------
    def upsert_entity(self, e: Entity) -> Entity:
        self._run(
            """MERGE (n:Entity {id:$id})
               SET n.name=$name, n.type=$type, n.alias=$alias,
                   n.description=$description, n.props_json=$props""",
            id=e.id, name=e.name, type=e.type, alias=e.alias,
            description=e.description, props=json.dumps(e.properties, ensure_ascii=False),
        )
        return e

    def get_entity(self, eid: str) -> Optional[Entity]:
        rows = self._run("MATCH (n:Entity {id:$id}) RETURN n", id=eid)
        return _to_entity(rows[0]["n"]) if rows else None

    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        rows = self._run(
            "MATCH (n:Entity) WHERE n.name=$name OR n.alias CONTAINS $name RETURN n LIMIT 1",
            name=name)
        return _to_entity(rows[0]["n"]) if rows else None

    def delete_entity(self, eid: str) -> bool:
        rows = self._run("MATCH (n:Entity {id:$id}) DETACH DELETE n RETURN count(*) AS c", id=eid)
        return rows[0]["c"] > 0

    def list_entities(self, type_, keyword, page, size) -> Tuple[int, List[Entity]]:
        where, params = ["1=1"], {}
        if type_:
            where.append("n.type=$type"); params["type"] = type_
        if keyword:
            where.append("(n.name CONTAINS $kw OR n.alias CONTAINS $kw OR n.description CONTAINS $kw)")
            params["kw"] = keyword
        w = " AND ".join(where)
        total = self._run(f"MATCH (n:Entity) WHERE {w} RETURN count(n) AS c", **params)[0]["c"]
        rows = self._run(
            f"MATCH (n:Entity) WHERE {w} RETURN n ORDER BY n.id SKIP $skip LIMIT $lim",
            skip=(page - 1) * size, lim=size, **params)
        return total, [_to_entity(r["n"]) for r in rows]

    def next_id(self, type_: str) -> str:
        prefix = TYPE_PREFIX[type_]
        rows = self._run(
            "MATCH (n:Entity) WHERE n.id STARTS WITH $p RETURN n.id AS id ORDER BY n.id DESC LIMIT 1",
            p=prefix)
        if not rows:
            return f"{prefix}001"
        tail = rows[0]["id"][len(prefix):]
        return f"{prefix}{(int(tail) + 1 if tail.isdigit() else 1):03d}"

    # ---------- 关系 ----------
    def upsert_relation(self, r: Relation) -> Relation:
        self._run(
            """MATCH (a:Entity {id:$sid}), (b:Entity {id:$tid})
               MERGE (a)-[e:REL {relation:$rel}]->(b)
               SET e.evidence=$ev""",
            sid=r.source_id, tid=r.target_id, rel=r.relation, ev=r.evidence)
        return r

    def delete_relation(self, source_id, relation, target_id) -> bool:
        rows = self._run(
            """MATCH (a:Entity {id:$sid})-[e:REL {relation:$rel}]->(b:Entity {id:$tid})
               DELETE e RETURN count(*) AS c""",
            sid=source_id, rel=relation, tid=target_id)
        return rows[0]["c"] > 0

    def list_relations(self, source_id, target_id, relation, page, size):
        where, params = ["1=1"], {}
        if source_id:
            where.append("a.id=$sid"); params["sid"] = source_id
        if target_id:
            where.append("b.id=$tid"); params["tid"] = target_id
        if relation:
            where.append("e.relation=$rel"); params["rel"] = relation
        w = " AND ".join(where)
        base = f"MATCH (a:Entity)-[e:REL]->(b:Entity) WHERE {w}"
        total = self._run(f"{base} RETURN count(e) AS c", **params)[0]["c"]
        rows = self._run(
            f"{base} RETURN a,e,b ORDER BY a.id SKIP $skip LIMIT $lim",
            skip=(page - 1) * size, lim=size, **params)
        return total, [self._rel(r) for r in rows]

    @staticmethod
    def _rel(row) -> Relation:
        a, e, b = row["a"], row["e"], row["b"]
        return Relation(source_id=a["id"], source_name=a["name"], relation=e["relation"],
                        target_id=b["id"], target_name=b["name"], evidence=e.get("evidence", "") or "")

    # ---------- 图查询 ----------
    def neighbors(self, eid, relation, limit):
        cy = ("MATCH (n:Entity {id:$id})-[e:REL]-(m:Entity) "
              + ("WHERE e.relation=$rel " if relation else "")
              + "RETURN startNode(e) AS a, e, endNode(e) AS b LIMIT $lim")
        rows = self._run(cy, id=eid, rel=relation, lim=limit)
        rels = [self._rel(r) for r in rows]
        ids = {eid} | {r.source_id for r in rels} | {r.target_id for r in rels}
        ents = [self.get_entity(i) for i in ids]
        return [e for e in ents if e], rels

    def subgraph(self, eid, depth, limit):
        rows = self._run(
            f"""MATCH p=(n:Entity {{id:$id}})-[:REL*0..{int(depth)}]-(m:Entity)
                WITH p LIMIT $lim
                UNWIND relationships(p) AS e
                RETURN DISTINCT startNode(e) AS a, e, endNode(e) AS b""",
            id=eid, lim=limit)
        rels = [self._rel(r) for r in rows]
        ids = {eid} | {r.source_id for r in rels} | {r.target_id for r in rels}
        ents = [self.get_entity(i) for i in ids]
        return [e for e in ents if e], rels

    def find_paths(self, source_id, target_id, max_depth, limit=5):
        rows = self._run(
            f"""MATCH p=(a:Entity {{id:$sid}})-[:REL*1..{int(max_depth)}]-(b:Entity {{id:$tid}})
                RETURN p ORDER BY length(p) LIMIT $lim""",
            sid=source_id, tid=target_id, lim=limit)
        out = []
        for row in rows:
            p = row["p"]
            ents = [_to_entity(n) for n in p.nodes]
            rels = [Relation(source_id=e.start_node["id"], source_name=e.start_node["name"],
                             relation=e["relation"], target_id=e.end_node["id"],
                             target_name=e.end_node["name"], evidence=e.get("evidence", "") or "")
                    for e in p.relationships]
            out.append((ents, rels))
        return out

    def clear(self) -> None:
        self._run("MATCH (n:Entity) DETACH DELETE n")

    def stats(self) -> dict:
        et = {r["t"]: r["c"] for r in
              self._run("MATCH (n:Entity) RETURN n.type AS t, count(*) AS c")}
        rt = {r["t"]: r["c"] for r in
              self._run("MATCH ()-[e:REL]->() RETURN e.relation AS t, count(*) AS c")}
        return {"entity_count": sum(et.values()), "relation_count": sum(rt.values()),
                "entity_by_type": et, "relation_by_type": rt}
