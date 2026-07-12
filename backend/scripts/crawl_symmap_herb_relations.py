from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_COMPONENTS = ["TCM_symptom", "Syndrome", "MM_symptom", "Mol"]
SYMMAP_DL_URL = "http://www.symmap.org/dl/"


def load_herb_ids(entities_file: Path) -> list[str]:
    data = json.loads(entities_file.read_text(encoding="utf-8"))
    ids = []
    for item in data:
        props = item.get("properties") or {}
        entity_id = str(item.get("id") or "").strip()
        if props.get("symmap_component") == "SMHB" or entity_id.startswith("SMHB"):
            ids.append(entity_id)
    return sorted(set(ids))


def post_download(herb_id: str, component: str, timeout: int) -> bytes:
    body = urllib.parse.urlencode({"rrid": herb_id, "table_name": component, "filter": "0"}).encode()
    request = urllib.request.Request(
        SYMMAP_DL_URL, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": "BYSX-TCM-KG-Research/1.0", "Referer": f"http://www.symmap.org/detail/{herb_id}"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def should_skip(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0 and b"No result" not in path.read_bytes()[:128]


def crawl(herb_ids: list[str], output_dir: Path, components: list[str], delay: float,
          retries: int, timeout: int, limit: int | None = None, offset: int = 0) -> dict:
    raw_dir = output_dir / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    selected = herb_ids[offset : offset + limit] if limit else herb_ids[offset:]
    stats = {"herbs": len(selected), "requests": 0, "downloaded": 0, "skipped": 0, "failed": 0}
    with (output_dir / "crawl_manifest.jsonl").open("a", encoding="utf-8") as log:
        for herb_index, herb_id in enumerate(selected, 1):
            for component in components:
                path = raw_dir / component / f"{herb_id}.csv"
                path.parent.mkdir(parents=True, exist_ok=True)
                if should_skip(path):
                    stats["skipped"] += 1
                    continue
                stats["requests"] += 1
                error = ""
                for attempt in range(retries + 1):
                    try:
                        content = post_download(herb_id, component, timeout)
                        path.write_bytes(content)
                        stats["downloaded"] += 1
                        error = ""
                        break
                    except (urllib.error.URLError, TimeoutError, OSError) as exc:
                        error = str(exc)
                        time.sleep(delay * (attempt + 1))
                if error:
                    stats["failed"] += 1
                log.write(json.dumps({"herb_index": herb_index, "herb_id": herb_id, "component": component,
                                      "ok": not error, "path": str(path), "error": error}, ensure_ascii=False) + "\n")
                log.flush()
                time.sleep(delay)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entities-file", default="integrated_entities_graphrag/data/entities/entities_symmap_import.json")
    parser.add_argument("--output-dir", default="integrated_entities_graphrag/external_data/symmap_v2/herb_relations")
    parser.add_argument("--components", default=",".join(DEFAULT_COMPONENTS))
    parser.add_argument("--delay", type=float, default=0.6)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    stats = crawl(load_herb_ids(Path(args.entities_file)), Path(args.output_dir),
                  [item.strip() for item in args.components.split(",") if item.strip()],
                  args.delay, args.retries, args.timeout, args.limit, args.offset)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
