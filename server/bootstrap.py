"""统一应用启动时初始化图谱存储和管理员。"""

from .config import STORE_BACKEND, get_store
from .init_admin import ensure_admin
from .schemas import Entity, Relation


def initialize_graph_management() -> None:
    store = get_store()
    if STORE_BACKEND == "memory" and store.stats().get("entity_count", 0) == 0:
        from backend.services.local_graphrag_service import LocalGraphRAGService

        source = LocalGraphRAGService()
        entities = [Entity(id=item.id, name=item.name, type=item.type,
                           alias=item.alias, description=item.description,
                           properties=item.properties or {})
                    for item in source.entities]
        relations = [Relation(source_id=item.source_id, source_name=item.source_name,
                              relation=item.relation, target_id=item.target_id,
                              target_name=item.target_name, evidence=item.evidence)
                     for item in source.relations]
        store.bulk_upsert_entities(entities)
        store.bulk_upsert_relations(relations)
        print(f"[graph] Memory 图谱已初始化：{len(entities)} 个实体，{len(relations)} 条关系")
    ensure_admin()
