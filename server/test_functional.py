"""功能测试：覆盖 Task 2 图谱管理模块的新修改。

运行方式：
    cd e:/BYSX_team && python -m pytest server/test_functional.py -v
    或直接：python server/test_functional.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 确保项目根目录在 sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from server.service import GraphService
from server.schemas import (
    Entity, EntityCreate, EntityUpdate,
    Relation, RelationCreate,
    GraphData, GraphNode, GraphEdge,
    get_entity_types, get_relation_types, validate_relation,
)
from server.store_memory import MemoryStore


# ============================================================
# 测试 1：next_id 原子序列
# ============================================================
class TestNextID(unittest.TestCase):
    """验证实体 ID 自动分配：按类型前缀独立计数。"""

    def setUp(self):
        self.store = MemoryStore()
        self.store.clear()
        self.svc = GraphService(self.store)

    def test_herb_ids_sequential(self):
        """药材类型独立计数 H001, H002, H003..."""
        ids = []
        for i in range(5):
            e = self.svc.create_entity(EntityCreate(
                name=f'测试药材{i}', type='药材'))
            ids.append(e.id)
        self.assertEqual(ids, ['H001', 'H002', 'H003', 'H004', 'H005'])

    def test_different_types_independent_counters(self):
        """不同类型独立计数。"""
        h1 = self.svc.create_entity(EntityCreate(name='人参', type='药材'))
        f1 = self.svc.create_entity(EntityCreate(name='归脾汤', type='方剂'))
        h2 = self.svc.create_entity(EntityCreate(name='黄芪', type='药材'))
        self.assertEqual(h1.id, 'H001')
        self.assertEqual(f1.id, 'F001')
        self.assertEqual(h2.id, 'H002')

    def test_custom_id_respected(self):
        """手动指定 ID 时使用自定义 ID。"""
        e = self.svc.create_entity(EntityCreate(id='H999', name='自定义药材', type='药材'))
        self.assertEqual(e.id, 'H999')
        # 下一个自动 ID 在最大已用编号后递增
        e2 = self.svc.create_entity(EntityCreate(name='下一个', type='药材'))
        self.assertEqual(e2.id, 'H1000')

    def test_new_type_auto_prefix(self):
        """新实体类型自动分配前缀。"""
        e = self.svc.create_entity(EntityCreate(name='测试新类型', type='治法'))
        self.assertTrue(len(e.id) >= 3, f'ID too short: {e.id}')
        self.assertFalse(any('一' <= c <= '鿿' for c in e.id),
                         f'ID contains Chinese: {e.id}')


# ============================================================
# 测试 2：关系原子更新
# ============================================================
class TestRelationUpdate(unittest.TestCase):
    """验证 update_relation 的两种路径：键不变走 upsert，键变化走 replace_relation。"""

    def setUp(self):
        self.store = MemoryStore()
        self.store.clear()
        self.svc = GraphService(self.store)
        # 准备测试数据
        self.f1 = self.svc.create_entity(EntityCreate(name='归脾汤', type='方剂'))
        self.h1 = self.svc.create_entity(EntityCreate(name='酸枣仁', type='药材'))
        self.h2 = self.svc.create_entity(EntityCreate(name='人参', type='药材'))
        self.r = self.svc.create_relation(RelationCreate(
            source_id=self.f1.id, relation='包含',
            target_id=self.h1.id, evidence='方剂学教材'))

    def test_update_evidence_only(self):
        """只改 evidence：键不变，走 upsert 路径。"""
        updated = self.svc.update_relation(
            self.f1.id, '包含', self.h1.id,
            {'evidence': '新版方剂学教材'})
        self.assertEqual(updated.evidence, '新版方剂学教材')
        self.assertEqual(updated.source_id, self.f1.id)
        self.assertEqual(updated.target_id, self.h1.id)
        self.assertEqual(updated.relation, '包含')

    def test_update_target(self):
        """改 target：键变化，走 replace_relation 路径。"""
        updated = self.svc.update_relation(
            self.f1.id, '包含', self.h1.id,
            {'target_id': self.h2.id, 'target_name': '人参'})
        self.assertEqual(updated.target_id, self.h2.id)
        self.assertEqual(updated.target_name, '人参')
        # 旧关系应被删除
        _, old_rels = self.svc.list_relations(
            source_id=self.f1.id, target_id=self.h1.id, relation='包含')
        self.assertEqual(len(old_rels), 0, '旧关系未被删除')

    def test_update_source_and_relation(self):
        """同时改 source 和 relation：键变化。"""
        f2 = self.svc.create_entity(EntityCreate(name='四君子汤', type='方剂'))
        s1 = self.svc.create_entity(EntityCreate(name='食少乏力', type='症状'))
        updated = self.svc.update_relation(
            self.f1.id, '包含', self.h1.id,
            {'source_id': f2.id, 'relation': '主治',
             'target_id': s1.id})
        self.assertEqual(updated.source_id, f2.id)
        self.assertEqual(updated.relation, '主治')
        self.assertEqual(updated.target_id, s1.id)
        # 验证只有一条关系存在
        _, all_rels = self.svc.list_relations()
        self.assertEqual(len(all_rels), 1)

    def test_self_loop_prevented(self):
        """自环关系应被拒绝。"""
        with self.assertRaises(ValueError) as ctx:
            self.svc.update_relation(
                self.f1.id, '包含', self.h1.id,
                {'target_id': self.f1.id})
        self.assertIn('自环', str(ctx.exception))

    def test_name_resolution_priority(self):
        """名字解析优先级：名字与 ID 冲突时以名字为准。"""
        # h2 是 '人参' (H002)
        updated = self.svc.update_relation(
            self.f1.id, '包含', self.h1.id,
            {'target_name': '人参'})  # 名字优先
        self.assertEqual(updated.target_id, self.h2.id,
                         '名字应优先于旧 ID')


# ============================================================
# 测试 3：实体 CRUD 回归
# ============================================================
class TestEntityCRUD(unittest.TestCase):
    """验证实体增删改查功能正常。"""

    def setUp(self):
        self.store = MemoryStore()
        self.store.clear()
        self.svc = GraphService(self.store)

    def test_create_and_get(self):
        e = self.svc.create_entity(EntityCreate(
            name='麻黄', type='药材',
            alias='麻黄草', description='发汗解表'))
        self.assertEqual(e.name, '麻黄')
        got = self.svc.get_entity(e.id)
        self.assertIsNotNone(got)
        self.assertEqual(got.name, '麻黄')

    def test_update_entity(self):
        e = self.svc.create_entity(EntityCreate(name='老名称', type='药材'))
        updated = self.svc.update_entity(e.id, EntityUpdate(name='新名称'))
        self.assertEqual(updated.name, '新名称')

    def test_delete_entity_cascades_relations(self):
        """删除实体应级联删除关联关系。"""
        h = self.svc.create_entity(EntityCreate(name='黄连', type='药材'))
        f = self.svc.create_entity(EntityCreate(name='黄连解毒汤', type='方剂'))
        self.svc.create_relation(RelationCreate(
            source_id=f.id, relation='包含', target_id=h.id))
        self.svc.delete_entity(h.id)
        _, rels = self.svc.list_relations()
        self.assertEqual(len(rels), 0)

    def test_duplicate_name_type_rejected(self):
        """同名同类型不能重复创建。"""
        self.svc.create_entity(EntityCreate(name='人参', type='药材'))
        with self.assertRaises(ValueError):
            self.svc.create_entity(EntityCreate(name='人参', type='药材'))

    def test_same_name_different_type_allowed(self):
        """同名不同类型允许。"""
        self.svc.create_entity(EntityCreate(name='测试', type='药材'))
        e2 = self.svc.create_entity(EntityCreate(name='测试', type='方剂'))
        self.assertEqual(e2.name, '测试')
        self.assertEqual(e2.type, '方剂')

    def test_list_with_pagination(self):
        for i in range(15):
            self.svc.create_entity(EntityCreate(name=f'药材{i}', type='药材'))
        total, items = self.svc.list_entities(type_='药材', page=2, size=5)
        self.assertEqual(total, 15)
        self.assertEqual(len(items), 5)

    def test_list_with_keyword(self):
        self.svc.create_entity(EntityCreate(name='人参', type='药材'))
        self.svc.create_entity(EntityCreate(name='人参养荣丸', type='方剂'))
        self.svc.create_entity(EntityCreate(name='黄芪', type='药材'))
        total, items = self.svc.list_entities(keyword='人参')
        self.assertEqual(total, 2)


# ============================================================
# 测试 4：关系 CRUD 回归
# ============================================================
class TestRelationCRUD(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.store.clear()
        self.svc = GraphService(self.store)
        self.h1 = self.svc.create_entity(EntityCreate(name='黄连', type='药材'))
        self.h2 = self.svc.create_entity(EntityCreate(name='黄芩', type='药材'))
        self.f1 = self.svc.create_entity(EntityCreate(name='黄连解毒汤', type='方剂'))

    def test_create_relation_by_name(self):
        """通过名字创建关系。"""
        r = self.svc.create_relation(RelationCreate(
            source_name='黄连解毒汤', relation='包含', target_name='黄连'))
        self.assertEqual(r.source_id, self.f1.id)
        self.assertEqual(r.target_id, self.h1.id)

    def test_self_loop_prevented(self):
        with self.assertRaises(ValueError):
            self.svc.create_relation(RelationCreate(
                source_id=self.h1.id, relation='包含', target_id=self.h1.id))

    def test_missing_endpoint_raises(self):
        with self.assertRaises(ValueError):
            self.svc.create_relation(RelationCreate(
                source_id='X999', relation='包含', target_id=self.h1.id))

    def test_delete_relation(self):
        self.svc.create_relation(RelationCreate(
            source_id=self.f1.id, relation='包含', target_id=self.h1.id))
        ok = self.svc.delete_relation(self.f1.id, '包含', self.h1.id)
        self.assertTrue(ok)
        _, rels = self.svc.list_relations()
        self.assertEqual(len(rels), 0)

    def test_list_relations_filter(self):
        self.svc.create_relation(RelationCreate(
            source_id=self.f1.id, relation='包含', target_id=self.h1.id))
        self.svc.create_relation(RelationCreate(
            source_id=self.f1.id, relation='包含', target_id=self.h2.id))
        _, rels = self.svc.list_relations(source_id=self.f1.id)
        self.assertEqual(len(rels), 2)
        _, rels = self.svc.list_relations(target_id=self.h1.id)
        self.assertEqual(len(rels), 1)


# ============================================================
# 测试 5：图谱查询
# ============================================================
class TestGraphQuery(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.store.clear()
        self.svc = GraphService(self.store)
        # 构建一个小图谱：症状→证候→方剂→药材
        s1 = self.svc.create_entity(EntityCreate(name='失眠', type='症状'))
        z1 = self.svc.create_entity(EntityCreate(name='心脾两虚', type='证候'))
        f1 = self.svc.create_entity(EntityCreate(name='归脾汤', type='方剂'))
        h1 = self.svc.create_entity(EntityCreate(name='酸枣仁', type='药材'))
        h2 = self.svc.create_entity(EntityCreate(name='人参', type='药材'))
        self.svc.create_relation(RelationCreate(
            source_id=s1.id, relation='提示', target_id=z1.id))
        self.svc.create_relation(RelationCreate(
            source_id=z1.id, relation='对应', target_id=f1.id))
        self.svc.create_relation(RelationCreate(
            source_id=f1.id, relation='包含', target_id=h1.id))
        self.svc.create_relation(RelationCreate(
            source_id=f1.id, relation='包含', target_id=h2.id))
        self.s1, self.z1, self.f1 = s1, z1, f1

    def test_subgraph_depth_2(self):
        g = self.svc.subgraph(self.s1.id, depth=2)
        self.assertGreaterEqual(len(g.nodes), 3)
        self.assertGreaterEqual(len(g.edges), 2)

    def test_neighbors(self):
        g = self.svc.neighbors(self.f1.id)
        # 归脾汤连接：心脾两虚(←对应) + 酸枣仁(→包含) + 人参(→包含)
        self.assertGreaterEqual(len(g.nodes), 3)

    def test_find_path(self):
        paths = self.svc.find_paths(self.s1.id, self.f1.id, max_depth=3)
        self.assertGreaterEqual(len(paths), 1)
        # service 返回 [{"length":int, "readable":str, "graph":{nodes,edges}}, ...]
        self.assertIn('readable', paths[0])
        self.assertIn('失眠', paths[0]['readable'])
        self.assertIn('归脾汤', paths[0]['readable'])

    def test_search_graph(self):
        g = self.svc.search_graph('失眠')
        self.assertGreaterEqual(len(g.nodes), 1)


# ============================================================
# 测试 6：批量导入
# ============================================================
class TestImport(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.store.clear()
        self.svc = GraphService(self.store)

    def test_import_entities_csv(self):
        from server.service import GraphService as _  # noqa: F811
        csv_bytes = (
            "id,name,type,alias,description\r\n"
            "H001,人参,药材,人参须,补气要药\r\n"
            "H002,黄芪,药材,,补气升阳\r\n"
        ).encode("utf-8-sig")
        rows = GraphService.parse_csv(csv_bytes)
        result = self.svc.import_entities(rows, strict=False)
        self.assertEqual(result.total, 2)
        self.assertEqual(result.success, 2)
        self.assertEqual(result.failed, 0)

    def test_import_relations_csv(self):
        # 先导入实体
        self.svc.create_entity(EntityCreate(id='F001', name='归脾汤', type='方剂'))
        self.svc.create_entity(EntityCreate(id='H001', name='人参', type='药材'))
        csv_bytes = (
            "source_id,source_name,relation,target_id,target_name,evidence\r\n"
            "F001,归脾汤,包含,H001,人参,方剂学\r\n"
        ).encode("utf-8-sig")
        rows = GraphService.parse_csv(csv_bytes)
        result = self.svc.import_relations(rows, strict=False)
        self.assertEqual(result.total, 1)
        self.assertEqual(result.success, 1)


# ============================================================
# 测试 7：元数据 & 统计
# ============================================================
class TestMeta(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.store.clear()
        self.svc = GraphService(self.store)

    def test_entity_types_include_known(self):
        types = get_entity_types()
        for t in ['药材', '方剂', '症状', '证候', '功效', '禁忌', '文献']:
            self.assertIn(t, types, f'缺少实体类型: {t}')

    def test_relation_types_include_known(self):
        types = get_relation_types()
        for t in ['包含', '主治', '提示', '对应', '具有', '禁忌', '来源于', '记载']:
            self.assertIn(t, types, f'缺少关系类型: {t}')

    def test_new_relation_type_accepted(self):
        """新关系类型自动接受（不抛异常）。"""
        validate_relation('新关系类型', '药材', '方剂')  # 不应 raise

    def test_stats_after_creation(self):
        self.svc.create_entity(EntityCreate(name='人参', type='药材'))
        self.svc.create_entity(EntityCreate(name='归脾汤', type='方剂'))
        stats = self.svc.stats()
        self.assertEqual(stats['entity_count'], 2)
        self.assertIn('entity_by_type', stats)


# ============================================================
# 测试 8：HybridStore 集成（需 MySQL + Neo4j 均运行）
# ============================================================
class TestHybridStoreIntegration(unittest.TestCase):
    """验证 replace_relation 的事务边界和两阶段提交语义。"""

    @classmethod
    def setUpClass(cls):
        from server.config import get_store, STORE_BACKEND
        if STORE_BACKEND != "hybrid":
            raise unittest.SkipTest(f"需要 STORE_BACKEND=hybrid，当前: {STORE_BACKEND}")
        cls.store = get_store()
        cls.svc = GraphService(cls.store)

    def setUp(self):
        # 每条测试前用唯一的测试前缀隔离数据
        import time, random
        self._tag = f"test_{int(time.time()*1000)}_{random.randint(0,9999):04d}"
        self._created: list[Entity] = []

    def tearDown(self):
        # 清理测试数据
        for e in reversed(self._created):
            try:
                self.store.delete_entity(e.id)
            except Exception:
                pass

    def _create(self, name: str, type_: str, eid: str | None = None) -> Entity:
        e = self.svc.create_entity(EntityCreate(
            id=eid, name=f'{self._tag}_{name}', type=type_))
        self._created.append(e)
        return e

    # ------ next_id ------
    def test_next_id_concurrent_types(self):
        """不同类型独立计数。"""
        h = self._create('药材A', '药材')
        f = self._create('方剂A', '方剂')
        h2 = self._create('药材B', '药材')
        self.assertTrue(h.id.startswith('H'))
        self.assertTrue(f.id.startswith('F'))
        self.assertTrue(h2.id.startswith('H'))
        self.assertNotEqual(h.id, h2.id)

    # ------ replace_relation ------
    def test_replace_relation_atomic(self):
        """键变化时：删旧+建新在同一事务，两边数据一致。"""
        f = self._create('方', '方剂')
        h1 = self._create('药材1', '药材')
        h2 = self._create('药材2', '药材')

        # 创建旧关系
        old = self.svc.create_relation(RelationCreate(
            source_id=f.id, relation='包含', target_id=h1.id, evidence='旧证据'))

        # 原子替换 target
        new_r = self.svc.update_relation(f.id, '包含', h1.id, {
            'target_id': h2.id, 'target_name': h2.name, 'evidence': '新证据'})

        self.assertEqual(new_r.target_id, h2.id)
        self.assertEqual(new_r.evidence, '新证据')

        # MySQL 侧：旧关系已删除
        _, old_m = self.store.mysql.list_relations(f.id, h1.id, '包含', 1, 10)
        self.assertEqual(len(old_m), 0, 'MySQL 旧关系应已删除')
        # MySQL 侧：新关系已创建
        _, new_m = self.store.mysql.list_relations(f.id, h2.id, '包含', 1, 10)
        self.assertEqual(len(new_m), 1, 'MySQL 新关系应存在')

        # Neo4j 侧：旧关系已删除
        _, old_n = self.store.neo4j.list_relations(f.id, h1.id, '包含', 1, 10)
        self.assertEqual(len(old_n), 0, 'Neo4j 旧关系应已删除')
        # Neo4j 侧：新关系已创建
        _, new_n = self.store.neo4j.list_relations(f.id, h2.id, '包含', 1, 10)
        self.assertEqual(len(new_n), 1, 'Neo4j 新关系应存在')

    # ------ 两阶段提交 ------
    def test_write_transaction_both_succeed(self):
        """正常写入：MySQL 和 Neo4j 同时成功。"""
        e = self._create('双写测试', '药材')
        # MySQL 侧
        m = self.store.mysql.get_entity(e.id)
        self.assertIsNotNone(m, 'MySQL 应有实体')
        self.assertEqual(m.name, e.name)
        # Neo4j 侧
        n = self.store.neo4j.get_entity(e.id)
        self.assertIsNotNone(n, 'Neo4j 应有实体')
        self.assertEqual(n.name, e.name)

    def test_upsert_idempotent(self):
        """upsert 多次不产生重复。"""
        f = self._create('重复测试方', '方剂')
        h = self._create('重复测试药', '药材')

        r_data = RelationCreate(source_id=f.id, relation='包含',
                                target_id=h.id, evidence='测试')
        for _ in range(3):
            self.svc.create_relation(r_data)

        _, rels = self.store.mysql.list_relations(
            None, None, None, 1, 100)
        key_count = sum(1 for r in rels
                        if r.source_id == f.id and r.target_id == h.id)
        self.assertEqual(key_count, 1, f'MySQL 关系重复: {key_count} 条')
        _, n_rels = self.store.neo4j.list_relations(
            None, None, None, 1, 100)
        n_key_count = sum(1 for r in n_rels
                          if r.source_id == f.id and r.target_id == h.id)
        self.assertEqual(n_key_count, 1, f'Neo4j 关系重复: {n_key_count} 条')


# ============================================================
# main
# ============================================================
if __name__ == '__main__':
    unittest.main(verbosity=2)
