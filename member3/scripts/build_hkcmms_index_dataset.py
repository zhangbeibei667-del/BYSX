#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
为 HKCMMS GraphRAG 生成“安全入库集”和“人工复核集”。

设计原则：
1. 不使用 char_count >= 80 这类激进阈值，避免误删大量有效短章节。
2. 仅排除：
   - 空文本块；
   - 与低质量页面重叠的文本块；
   - 明显包含乱码特征的文本块。
3. 所有被排除的块写入 chunks_for_review.jsonl，便于后续 OCR 修复。
4. 不覆盖原始 chunks.jsonl。

用法：
python build_hkcmms_index_dataset.py ^
  --pages data\pharmacopoeia\processed\hkcmms\pages.jsonl ^
  --chunks data\pharmacopoeia\processed\hkcmms\chunks.jsonl ^
  --output-dir data\pharmacopoeia\processed\hkcmms\index_ready
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


DEFAULT_QUALITY_THRESHOLD = 0.58

GARBLED_PATTERNS = [
    r"={3,}",
    r"(?:OE|NE|PE|RE|PR|PQ|OR|OS|OT|OQ|PP|N)[áÄ~F]{0,3}={1,}",
    r"[!#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~]{8,}",
    r"(?:[A-Za-z]{1,3}K=){3,}",
    r"(?:[A-Za-z]=){4,}",
]

UNIT_HEADING_RE = re.compile(
    r"^\s*\d+(?:\.\d+){1,3}\s*"
    r"(?:µL|μL|uL|mL|L|mg|g|kg|µg|μg|ug|nm|mm|cm|m|"
    r"%|°C|℃|mol|mmol)\b",
    flags=re.IGNORECASE,
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"{path} 第 {line_number} 行不是有效 JSON：{error}"
                ) from error

    return rows


def write_jsonl(
    path: Path,
    rows: Iterable[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
            file.write("\n")


def find_garbled_patterns(text: str) -> list[str]:
    matched: list[str] = []

    for pattern in GARBLED_PATTERNS:
        if re.search(pattern, text):
            matched.append(pattern)

    return matched


def cjk_ratio(text: str) -> float:
    nonspace = [
        char
        for char in text
        if not char.isspace()
    ]

    if not nonspace:
        return 0.0

    cjk = sum(
        "\u3400" <= char <= "\u9fff"
        or "\uf900" <= char <= "\ufaff"
        for char in nonspace
    )

    return cjk / len(nonspace)


def overlaps_low_page(
    chunk: dict[str, Any],
    low_pages_by_file: dict[str, set[int]],
) -> list[int]:
    source_file = str(chunk.get("source_file", ""))
    page_start = int(chunk.get("page_start") or 0)
    page_end = int(chunk.get("page_end") or page_start)

    matched = [
        page
        for page in low_pages_by_file.get(source_file, set())
        if page_start <= page <= page_end
    ]

    return sorted(matched)


def classify_chunk(
    chunk: dict[str, Any],
    low_pages_by_file: dict[str, set[int]],
) -> tuple[bool, list[str], list[int]]:
    text = str(chunk.get("text") or "").strip()
    reasons: list[str] = []

    if not text:
        reasons.append("empty_text")

    low_pages = overlaps_low_page(
        chunk,
        low_pages_by_file,
    )

    if low_pages:
        reasons.append(
            "overlaps_low_quality_page"
        )

    garbled = find_garbled_patterns(text)

    if garbled:
        reasons.append("obvious_garbled_text")

    # 极低中文比例且长度较长，通常是乱码图表文本。
    if len(text) >= 40 and cjk_ratio(text) < 0.08:
        reasons.append("very_low_cjk_ratio")

    return len(reasons) == 0, reasons, low_pages


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a conservative HKCMMS GraphRAG "
            "index dataset."
        )
    )

    parser.add_argument(
        "--pages",
        type=Path,
        required=True,
        help="pages.jsonl 路径。",
    )
    parser.add_argument(
        "--chunks",
        type=Path,
        required=True,
        help="chunks.jsonl 路径。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="输出目录。",
    )
    parser.add_argument(
        "--quality-threshold",
        type=float,
        default=DEFAULT_QUALITY_THRESHOLD,
        help="低质量页面阈值，默认 0.58。",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    pages = read_jsonl(args.pages)
    chunks = read_jsonl(args.chunks)

    low_pages = [
        page
        for page in pages
        if float(page.get("final_quality") or 0.0)
        < args.quality_threshold
    ]

    low_pages_by_file: dict[str, set[int]] = defaultdict(set)

    for page in low_pages:
        low_pages_by_file[
            str(page.get("source_file", ""))
        ].add(int(page.get("page_number") or 0))

    indexable: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []

    for chunk in chunks:
        accepted, reasons, matched_pages = classify_chunk(
            chunk,
            low_pages_by_file,
        )

        output_row = dict(chunk)
        output_row["index_status"] = (
            "indexable" if accepted else "review"
        )
        output_row["index_exclusion_reasons"] = reasons
        output_row["matched_low_quality_pages"] = matched_pages

        # 标记疑似“数值 + 单位”被误识别为章节标题的情况，
        # 但不因此直接排除正文。
        section_title = str(
            chunk.get("section_title") or ""
        )
        output_row["section_title_suspect"] = bool(
            UNIT_HEADING_RE.match(section_title)
        )

        if accepted:
            indexable.append(output_row)
        else:
            review.append(output_row)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    write_jsonl(
        output_dir / "chunks_for_index.jsonl",
        indexable,
    )
    write_jsonl(
        output_dir / "chunks_for_review.jsonl",
        review,
    )

    report = {
        "source_pages": str(args.pages),
        "source_chunks": str(args.chunks),
        "quality_threshold": args.quality_threshold,
        "total_pages": len(pages),
        "low_quality_pages": len(low_pages),
        "total_chunks": len(chunks),
        "indexable_chunks": len(indexable),
        "review_chunks": len(review),
        "section_title_suspect_count": sum(
            bool(row.get("section_title_suspect"))
            for row in indexable + review
        ),
    }

    (
        output_dir / "filter_report.json"
    ).write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    review_csv = output_dir / "chunks_for_review.csv"
    fields = [
        "chunk_id",
        "title",
        "source_file",
        "section_title",
        "page_start",
        "page_end",
        "char_count",
        "index_exclusion_reasons",
        "matched_low_quality_pages",
        "section_title_suspect",
        "text",
    ]

    with review_csv.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
        )
        writer.writeheader()

        for row in review:
            writer.writerow(
                {
                    field: (
                        json.dumps(
                            row.get(field),
                            ensure_ascii=False,
                        )
                        if isinstance(
                            row.get(field),
                            (list, dict),
                        )
                        else row.get(field, "")
                    )
                    for field in fields
                }
            )

    print("=" * 68)
    print("HKCMMS GraphRAG 安全入库集生成完成")
    print("=" * 68)
    print(f"页面总数            : {len(pages)}")
    print(f"低质量页面          : {len(low_pages)}")
    print(f"原始文本块          : {len(chunks)}")
    print(f"可入库文本块        : {len(indexable)}")
    print(f"待复核文本块        : {len(review)}")
    print(
        "疑似错误章节标题    : "
        f"{report['section_title_suspect_count']}"
    )
    print()
    print(
        "入库文件："
        f"{output_dir / 'chunks_for_index.jsonl'}"
    )
    print(
        "复核文件："
        f"{output_dir / 'chunks_for_review.jsonl'}"
    )
    print(
        "复核表格："
        f"{output_dir / 'chunks_for_review.csv'}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
