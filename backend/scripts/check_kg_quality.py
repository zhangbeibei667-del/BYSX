"""Run the strict file-level KG quality gate and optionally write JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.services.kg_data_quality import assert_kg_quality, audit_kg


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-fail", action="store_true", help="只生成报告，不因质量问题退出")
    args = parser.parse_args()
    report = audit_kg()
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8", newline="\n") as file:
            file.write(text + "\n")
    print(text)
    if not args.no_fail:
        assert_kg_quality()


if __name__ == "__main__":
    main()
