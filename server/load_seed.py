"""一键灌入数据：  python -m server.load_seed  （在项目根目录运行）
优先读取 data/entities/ 和 data/relations/ （任务1产出），
若为空则回退到 seed/ 下的示例 CSV。
"""
import csv
import io
import json
import os
import sys
from typing import Dict, List

sys.path.insert(0, os.path.dirname(__file__))

try:
    from .config import get_store
    from .service import GraphService
except ImportError:
    from config import get_store
    from service import GraphService

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_files(dir_path: str) -> List[Dict[str, str]]:
    """读取一个目录下的所有 CSV 和 JSON 文件，统一返回行列表。

    JSON 实体中的 properties 子对象会被展开为平铺的顶层键，
    以匹配 CSV 格式（import_entities 用非保留列自动构建 properties）。
    """
    rows: List[Dict[str, str]] = []
    if not os.path.isdir(dir_path):
        return rows

    for fname in sorted(os.listdir(dir_path)):
        fpath = os.path.join(dir_path, fname)
        if not os.path.isfile(fpath):
            continue

        if fname.endswith(".csv"):
            with open(fpath, "r", encoding="utf-8-sig") as f:
                rows.extend(list(csv.DictReader(f)))

        elif fname.endswith(".json"):
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            items: list = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                for key in ("entities", "relations", "items"):
                    if key in data and isinstance(data[key], list):
                        items = data[key]
            # 展平 JSON 中嵌套的 properties 字典
            for item in items:
                flat: Dict[str, str] = {}
                for k, v in item.items():
                    if k == "properties" and isinstance(v, dict):
                        # 把 properties 子对象的键值展开到顶层
                        for pk, pv in v.items():
                            flat[pk] = str(pv) if pv is not None else ""
                    elif not isinstance(v, (dict, list)):
                        flat[k] = str(v) if v is not None else ""
                rows.append(flat)

    return rows


def main(reset: bool = True):
    s = GraphService(get_store())
    if reset:
        s.store.clear()

    entities_dir = os.path.join(ROOT, "data", "entities")
    relations_dir = os.path.join(ROOT, "data", "relations")

    entity_rows = read_files(entities_dir)
    relation_rows = read_files(relations_dir)

    # 如果 data/ 下没数据，回退到 seed/ 示例
    if not entity_rows:
        seed = os.path.join(ROOT, "seed", "entities_seed.csv")
        if os.path.exists(seed):
            with open(seed, "rb") as f:
                entity_rows = s.parse_csv(f.read())
            print("[entities] 使用 seed/ 示例数据")
    else:
        print(f"[entities] 从 data/entities/ 读取 {len(entity_rows)} 行")

    if not relation_rows:
        seed = os.path.join(ROOT, "seed", "relations_seed.csv")
        if os.path.exists(seed):
            with open(seed, "rb") as f:
                relation_rows = s.parse_csv(f.read())
            print("[relations] 使用 seed/ 示例数据")
    else:
        print(f"[relations] 从 data/relations/ 读取 {len(relation_rows)} 行")

    # 导入
    for kind, rows, fn in [("entities", entity_rows, s.import_entities),
                            ("relations", relation_rows, s.import_relations)]:
        res = fn(rows)
        print(f"[{kind}] 总数 {res.total} 成功 {res.success} 失败 {res.failed}")
        for e in res.errors:
            print(f"   第 {e.row} 行: {e.reason}")

    print("统计:", s.stats())


if __name__ == "__main__":
    main(reset="--keep" not in sys.argv)
