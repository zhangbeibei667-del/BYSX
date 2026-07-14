"""一键灌入数据：  python -m server.import_data  （在项目根目录运行）
读取根目录下的 entities/ 和 relations/（CSV 和 JSON），导入到图谱存储。

支持 --strict 参数：任一失败则整体回滚（需要 hybrid/mysql 存储后端）。
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
    """读取一个目录下的所有 CSV 和 JSON 文件，统一返回行列表。"""
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
            for item in items:
                flat: Dict[str, str] = {}
                for k, v in item.items():
                    if k == "properties" and isinstance(v, dict):
                        for pk, pv in v.items():
                            flat[pk] = str(pv) if pv is not None else ""
                    elif not isinstance(v, (dict, list)):
                        flat[k] = str(v) if v is not None else ""
                rows.append(flat)

    return rows


def main(reset: bool = True, strict: bool = False):
    s = GraphService(get_store())
    if reset:
        print("[store] 清空已有数据...")
        s.store.clear()

    entities_dir = os.path.join(ROOT, "entities")
    relations_dir = os.path.join(ROOT, "relations")

    entity_rows = read_files(entities_dir)
    relation_rows = read_files(relations_dir)

    print(f"[entities] 从 entities/ 读取 {len(entity_rows)} 行")
    print(f"[relations] 从 relations/ 读取 {len(relation_rows)} 行")

    # 导入（先实体后关系，保证外键约束）
    for kind, rows, fn in [("entities", entity_rows, s.import_entities),
                            ("relations", relation_rows, s.import_relations)]:
        mode = "严格模式" if strict else "容错模式"
        print(f"[{kind}] 开始导入 {len(rows)} 条（{mode}）...")
        try:
            res = fn(rows, strict=strict)
            print(f"[{kind}] 总数 {res.total} 成功 {res.success} 失败 {res.failed}")
            # 记录导入批次（命令行操作，用户记为 seed）
            try:
                s.store.insert_import_batch(
                    user_id=0, username="seed", kind=kind, file_name="import_data.py",
                    total=res.total, success=res.success, failed=res.failed,
                    errors=[e.model_dump() for e in res.errors[:50]],
                )
            except Exception:
                pass  # 批次记录失败不中断导入
            for e in res.errors[:10]:
                print(f"   第 {e.row} 行: {e.reason}")
            if len(res.errors) > 10:
                print(f"   ... 共 {len(res.errors)} 条错误")
        except Exception as ex:
            print(f"[{kind}] 导入失败（事务回滚）: {ex}")
            raise

    print("统计:", s.stats())


if __name__ == "__main__":
    strict = "--strict" in sys.argv
    keep = "--keep" in sys.argv
    main(reset=not keep, strict=strict)
