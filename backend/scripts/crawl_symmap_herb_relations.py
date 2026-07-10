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
    herb_ids: list[str] = []
    for item in data:
        props = item.get("properties") or {}
        if item.get("type") != "药材":
            continue
        symmap_id = str(props.get("symmap_id") or item.get("id") or "").strip()
        if symmap_id.startswith("SMHB"):
            herb_ids.append(symmap_id)
    return sorted(dict.fromkeys(herb_ids))


def post_download(herb_id: str, component: str, timeout: int) -> bytes:
    body = urllib.parse.urlencode(
        {
            "rrid": herb_id,
            "table_name": component,
            "filter": "0",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        SYMMAP_DL_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "BYSX-TCM-KG-Research/1.0",
            "Referer": f"http://www.symmap.org/detail/{herb_id}",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def should_skip(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    first = path.read_bytes()[:128]
    return b"No result" not in first


def crawl(
    herb_ids: list[str],
    output_dir: Path,
    components: list[str],
    delay: float,
    retries: int,
    timeout: int,
    limit: int | None = None,
) -> dict:
    raw_dir = output_dir / "raw"
    log_path = output_dir / "crawl_manifest.jsonl"
    output_dir.mkdir(parents=True, exist_ok=True)

    stats = {"herbs": 0, "requests": 0, "downloaded": 0, "skipped": 0, "failed": 0}
    selected_herbs = herb_ids[:limit] if limit else herb_ids
    stats["herbs"] = len(selected_herbs)

    with log_path.open("a", encoding="utf-8") as log_file:
        for herb_index, herb_id in enumerate(selected_herbs, start=1):
            for component in components:
                component_dir = raw_dir / component
                component_dir.mkdir(parents=True, exist_ok=True)
                output_path = component_dir / f"{herb_id}.csv"

                if should_skip(output_path):
                    stats["skipped"] += 1
                    continue

                stats["requests"] += 1
                ok = False
                error_message = ""
                for attempt in range(1, retries + 2):
                    try:
                        content = post_download(herb_id, component, timeout=timeout)
                        output_path.write_bytes(content)
                        stats["downloaded"] += 1
                        ok = True
                        break
                    except (urllib.error.URLError, TimeoutError, OSError) as exc:
                        error_message = str(exc)
                        time.sleep(delay * attempt)

                if not ok:
                    stats["failed"] += 1

                log_file.write(
                    json.dumps(
                        {
                            "herb_index": herb_index,
                            "herb_id": herb_id,
                            "component": component,
                            "ok": ok,
                            "path": str(output_path),
                            "error": error_message,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                log_file.flush()
                time.sleep(delay)

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl downloadable SymMap herb relation CSV files.")
    parser.add_argument(
        "--entities-file",
        default="integrated_entities_graphrag/data/entities/entities_symmap_import.json",
        help="SymMap-imported entity JSON used to enumerate SMHB herb IDs.",
    )
    parser.add_argument(
        "--output-dir",
        default="integrated_entities_graphrag/external_data/symmap_v2/herb_relations",
        help="Directory for raw downloaded CSV files and crawl manifest.",
    )
    parser.add_argument(
        "--components",
        default=",".join(DEFAULT_COMPONENTS),
        help="Comma-separated SymMap related component tables to download.",
    )
    parser.add_argument("--delay", type=float, default=0.6, help="Delay between requests in seconds.")
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--limit", type=int, default=None, help="Optional first-N herb limit for testing.")
    args = parser.parse_args()

    herb_ids = load_herb_ids(Path(args.entities_file))
    components = [item.strip() for item in args.components.split(",") if item.strip()]
    stats = crawl(
        herb_ids=herb_ids,
        output_dir=Path(args.output_dir),
        components=components,
        delay=args.delay,
        retries=args.retries,
        timeout=args.timeout,
        limit=args.limit,
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
