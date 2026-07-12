#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
HKCMMS GraphRAG 数据质量检查脚本
================================

用途：
    检查以下文件是否适合进入向量数据库：
    - pages.jsonl
    - chunks.jsonl
    - index_ready/chunks_for_index.jsonl
    - index_ready/chunks_for_review.jsonl

检查内容：
    1. JSONL 格式是否有效
    2. 页面、原始块、可入库块、待复核块数量
    3. chunk_id 是否重复
    4. index/review 是否覆盖全部原始 chunk
    5. index/review 是否存在交集
    6. 文本是否为空
    7. 必填字段是否缺失
    8. char_count 是否与实际文本长度一致
    9. 页码范围是否有效
   10. 是否仍有明显乱码进入可入库集
   11. 是否存在疑似错误章节标题
   12. 低质量页面及其对应文本块
   13. 空白页、纯图像页不作为阻塞错误
   14. 输出 JSON、CSV 和控制台报告

本脚本不会修改任何原始数据。

推荐运行位置：
    F:\bysx\BYSX\member3

运行命令：
    python .\scripts\validate_hkcmms_index_dataset.py ^
      --base-dir .\data\pharmacopoeia\processed\hkcmms

PowerShell：
    python .\scripts\validate_hkcmms_index_dataset.py `
      --base-dir .\data\pharmacopoeia\processed\hkcmms

输出目录：
    data\pharmacopoeia\processed\hkcmms\validation\

输出文件：
    validation_report.json
    validation_issues.csv
    low_quality_pages.csv
    suspect_sections.csv
    review_summary.csv

退出码：
    0 = 未发现阻塞性问题
    1 = 发现阻塞性问题
    2 = 输入文件或参数错误
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable


SCRIPT_VERSION = "1.1.0"
DEFAULT_QUALITY_THRESHOLD = 0.58

REQUIRED_CHUNK_FIELDS = [
    "chunk_id",
    "document_id",
    "title",
    "section_title",
    "page_start",
    "page_end",
    "text",
    "source_file",
]

REQUIRED_PAGE_FIELDS = [
    "document_id",
    "source_file",
    "page_number",
    "extraction_method",
    "native_quality",
    "final_quality",
]

GARBLED_PATTERNS: list[tuple[str, str]] = [
    ("repeated_equals", r"={3,}"),
    (
        "latin_symbol_gibberish",
        r"(?:OE|NE|PE|RE|PR|PQ|OR|OS|OT|OQ|PP|N)"
        r"[áÄ~F]{0,3}={1,}",
    ),
    (
        "long_symbol_run",
        r"[!#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~]{8,}",
    ),
    ("repeated_k_equals", r"(?:[A-Za-z]{1,3}K=){3,}"),
    ("repeated_letter_equals", r"(?:[A-Za-z]=){4,}"),
    ("mojibake_cjk_1", r"銆俓|闄勯寗|榄氳|楝遍|鍚嶇"),
    ("replacement_char", "\ufffd"),
]

UNIT_TITLE_RE = re.compile(
    r"^\s*\d+(?:\.\d+){1,3}\s*"
    r"(?:µL|μL|uL|mL|L|mg|g|kg|µg|μg|ug|nm|mm|cm|m|"
    r"%|°C|℃|mol|mmol)\b",
    flags=re.IGNORECASE,
)

LONG_SECTION_TITLE_LIMIT = 40


@dataclass
class Issue:
    severity: str
    category: str
    file_type: str
    record_id: str
    source_file: str
    page_start: str
    page_end: str
    message: str
    text_preview: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate HKCMMS GraphRAG JSONL datasets."
    )

    parser.add_argument(
        "--base-dir",
        type=Path,
        required=True,
        help=(
            "清洗结果目录，例如："
            "data/pharmacopoeia/processed/hkcmms"
        ),
    )
    parser.add_argument(
        "--quality-threshold",
        type=float,
        default=DEFAULT_QUALITY_THRESHOLD,
        help=f"低质量页面阈值，默认 {DEFAULT_QUALITY_THRESHOLD}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="报告输出目录，默认 base-dir/validation",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "严格模式：疑似章节标题和 char_count 不一致"
            "也作为阻塞性问题。"
        ),
    )

    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{path}")

    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            raw = line.strip()

            if not raw:
                continue

            try:
                value = json.loads(raw)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"{path} 第 {line_number} 行不是有效 JSON：{error}"
                ) from error

            if not isinstance(value, dict):
                raise ValueError(
                    f"{path} 第 {line_number} 行不是 JSON 对象"
                )

            rows.append(value)

    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def write_csv(
    path: Path,
    rows: Iterable[dict[str, Any]],
    fields: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore",
        )
        writer.writeheader()

        for row in rows:
            converted = {}

            for field in fields:
                value = row.get(field, "")

                if isinstance(value, (list, dict)):
                    converted[field] = json.dumps(
                        value,
                        ensure_ascii=False,
                    )
                else:
                    converted[field] = value

            writer.writerow(converted)


def preview(text: Any, limit: int = 160) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()

    if len(value) <= limit:
        return value

    return value[:limit] + "..."


def safe_int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None

        return int(value)
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None

        return float(value)
    except (TypeError, ValueError):
        return None


def cjk_ratio(text: str) -> float:
    chars = [
        char
        for char in text
        if not char.isspace()
    ]

    if not chars:
        return 0.0

    cjk = sum(
        "\u3400" <= char <= "\u9fff"
        or "\uf900" <= char <= "\ufaff"
        for char in chars
    )

    return cjk / len(chars)


def detect_garbled(text: str) -> list[str]:
    matches: list[str] = []

    for name, pattern in GARBLED_PATTERNS:
        if re.search(pattern, text):
            matches.append(name)

    if len(text) >= 40 and cjk_ratio(text) < 0.08:
        matches.append("very_low_cjk_ratio")

    return sorted(set(matches))


def check_required_fields(
    rows: list[dict[str, Any]],
    fields: list[str],
    file_type: str,
    issues: list[Issue],
) -> None:
    for row in rows:
        missing = [
            field
            for field in fields
            if field not in row
            or row.get(field) is None
            or (
                isinstance(row.get(field), str)
                and not row.get(field).strip()
            )
        ]

        if not missing:
            continue

        issues.append(
            Issue(
                severity="error",
                category="missing_required_field",
                file_type=file_type,
                record_id=str(
                    row.get("chunk_id")
                    or row.get("document_id")
                    or ""
                ),
                source_file=str(row.get("source_file") or ""),
                page_start=str(
                    row.get("page_start")
                    or row.get("page_number")
                    or ""
                ),
                page_end=str(row.get("page_end") or ""),
                message="缺少字段：" + ", ".join(missing),
                text_preview=preview(
                    row.get("text")
                    or row.get("clean_text")
                ),
            )
        )


def check_duplicate_ids(
    rows: list[dict[str, Any]],
    field: str,
    file_type: str,
    issues: list[Issue],
) -> list[str]:
    values = [
        str(row.get(field))
        for row in rows
        if row.get(field) is not None
    ]
    duplicates = sorted(
        value
        for value, count in Counter(values).items()
        if count > 1
    )

    for value in duplicates:
        issues.append(
            Issue(
                severity="error",
                category="duplicate_id",
                file_type=file_type,
                record_id=value,
                source_file="",
                page_start="",
                page_end="",
                message=f"{field} 重复",
                text_preview="",
            )
        )

    return duplicates


def build_page_maps(
    pages: list[dict[str, Any]],
) -> tuple[
    dict[str, set[int]],
    dict[str, int],
    dict[str, dict[int, dict[str, Any]]],
]:
    page_numbers: dict[str, set[int]] = defaultdict(set)
    max_pages: dict[str, int] = defaultdict(int)
    page_lookup: dict[
        str,
        dict[int, dict[str, Any]],
    ] = defaultdict(dict)

    for page in pages:
        source_file = str(page.get("source_file") or "")
        page_number = safe_int(page.get("page_number"))

        if not source_file or page_number is None:
            continue

        page_numbers[source_file].add(page_number)
        max_pages[source_file] = max(
            max_pages[source_file],
            page_number,
        )
        page_lookup[source_file][page_number] = page

    return page_numbers, max_pages, page_lookup


def check_page_sequences(
    page_numbers: dict[str, set[int]],
    issues: list[Issue],
) -> dict[str, list[int]]:
    missing_by_file: dict[str, list[int]] = {}

    for source_file, numbers in page_numbers.items():
        if not numbers:
            continue

        expected = set(
            range(min(numbers), max(numbers) + 1)
        )
        missing = sorted(expected - numbers)

        if missing:
            missing_by_file[source_file] = missing
            issues.append(
                Issue(
                    severity="error",
                    category="missing_page_records",
                    file_type="pages",
                    record_id="",
                    source_file=source_file,
                    page_start="",
                    page_end="",
                    message=(
                        "缺少页面记录："
                        + ", ".join(map(str, missing))
                    ),
                    text_preview="",
                )
            )

    return missing_by_file


def check_chunk_rows(
    rows: list[dict[str, Any]],
    file_type: str,
    max_pages: dict[str, int],
    strict: bool,
    issues: list[Issue],
) -> dict[str, Any]:
    empty_text = 0
    char_count_mismatch = 0
    invalid_page_ranges = 0
    missing_source_pages = 0
    garbled_count = 0
    suspect_section_count = 0
    long_section_count = 0

    suspect_sections: list[dict[str, Any]] = []

    for row in rows:
        chunk_id = str(row.get("chunk_id") or "")
        source_file = str(row.get("source_file") or "")
        text = str(row.get("text") or "")
        section_title = str(
            row.get("section_title") or ""
        )

        page_start = safe_int(row.get("page_start"))
        page_end = safe_int(row.get("page_end"))
        declared_char_count = safe_int(
            row.get("char_count")
        )

        if not text.strip():
            empty_text += 1
            issues.append(
                Issue(
                    severity="error",
                    category="empty_text",
                    file_type=file_type,
                    record_id=chunk_id,
                    source_file=source_file,
                    page_start=str(page_start or ""),
                    page_end=str(page_end or ""),
                    message="文本块为空",
                    text_preview="",
                )
            )

        if (
            declared_char_count is not None
            and declared_char_count != len(text)
        ):
            char_count_mismatch += 1
            issues.append(
                Issue(
                    severity=(
                        "error" if strict else "warning"
                    ),
                    category="char_count_mismatch",
                    file_type=file_type,
                    record_id=chunk_id,
                    source_file=source_file,
                    page_start=str(page_start or ""),
                    page_end=str(page_end or ""),
                    message=(
                        f"char_count={declared_char_count}，"
                        f"实际长度={len(text)}"
                    ),
                    text_preview=preview(text),
                )
            )

        if (
            page_start is None
            or page_end is None
            or page_start < 1
            or page_end < page_start
        ):
            invalid_page_ranges += 1
            issues.append(
                Issue(
                    severity="error",
                    category="invalid_page_range",
                    file_type=file_type,
                    record_id=chunk_id,
                    source_file=source_file,
                    page_start=str(page_start or ""),
                    page_end=str(page_end or ""),
                    message="页码范围无效",
                    text_preview=preview(text),
                )
            )
        elif (
            source_file in max_pages
            and page_end > max_pages[source_file]
        ):
            missing_source_pages += 1
            issues.append(
                Issue(
                    severity="error",
                    category="page_out_of_range",
                    file_type=file_type,
                    record_id=chunk_id,
                    source_file=source_file,
                    page_start=str(page_start),
                    page_end=str(page_end),
                    message=(
                        f"page_end={page_end} 超出文档最大页码 "
                        f"{max_pages[source_file]}"
                    ),
                    text_preview=preview(text),
                )
            )

        garbled_matches = detect_garbled(text)

        if garbled_matches:
            garbled_count += 1
            issues.append(
                Issue(
                    severity=(
                        "error"
                        if file_type == "index"
                        else "warning"
                    ),
                    category="garbled_text",
                    file_type=file_type,
                    record_id=chunk_id,
                    source_file=source_file,
                    page_start=str(page_start or ""),
                    page_end=str(page_end or ""),
                    message=(
                        "命中乱码规则："
                        + ", ".join(garbled_matches)
                    ),
                    text_preview=preview(text),
                )
            )

        section_reasons: list[str] = []

        if len(section_title) > LONG_SECTION_TITLE_LIMIT:
            long_section_count += 1
            section_reasons.append(
                f"标题长度超过 {LONG_SECTION_TITLE_LIMIT}"
            )

        if UNIT_TITLE_RE.match(section_title):
            suspect_section_count += 1
            section_reasons.append(
                "标题疑似由数值和单位误识别"
            )

        if section_reasons:
            suspect_sections.append(
                {
                    "chunk_id": chunk_id,
                    "title": row.get("title", ""),
                    "source_file": source_file,
                    "page_start": page_start,
                    "page_end": page_end,
                    "section_title": section_title,
                    "reasons": section_reasons,
                    "text": text,
                }
            )
            issues.append(
                Issue(
                    severity=(
                        "error" if strict else "warning"
                    ),
                    category="suspect_section_title",
                    file_type=file_type,
                    record_id=chunk_id,
                    source_file=source_file,
                    page_start=str(page_start or ""),
                    page_end=str(page_end or ""),
                    message="；".join(section_reasons),
                    text_preview=preview(text),
                )
            )

    return {
        "empty_text": empty_text,
        "char_count_mismatch": char_count_mismatch,
        "invalid_page_ranges": invalid_page_ranges,
        "page_out_of_range": missing_source_pages,
        "garbled_text": garbled_count,
        "suspect_section_title": suspect_section_count,
        "long_section_title": long_section_count,
        "suspect_sections": suspect_sections,
    }


def check_partition(
    raw_chunks: list[dict[str, Any]],
    index_chunks: list[dict[str, Any]],
    review_chunks: list[dict[str, Any]],
    issues: list[Issue],
) -> dict[str, Any]:
    raw_ids = {
        str(row.get("chunk_id"))
        for row in raw_chunks
        if row.get("chunk_id") is not None
    }
    index_ids = {
        str(row.get("chunk_id"))
        for row in index_chunks
        if row.get("chunk_id") is not None
    }
    review_ids = {
        str(row.get("chunk_id"))
        for row in review_chunks
        if row.get("chunk_id") is not None
    }

    overlap = sorted(index_ids & review_ids)
    missing = sorted(
        raw_ids - index_ids - review_ids
    )
    unexpected = sorted(
        (index_ids | review_ids) - raw_ids
    )

    for chunk_id in overlap:
        issues.append(
            Issue(
                severity="error",
                category="partition_overlap",
                file_type="partition",
                record_id=chunk_id,
                source_file="",
                page_start="",
                page_end="",
                message=(
                    "同一 chunk 同时存在于 index 和 review"
                ),
                text_preview="",
            )
        )

    for chunk_id in missing:
        issues.append(
            Issue(
                severity="error",
                category="partition_missing",
                file_type="partition",
                record_id=chunk_id,
                source_file="",
                page_start="",
                page_end="",
                message=(
                    "原始 chunk 未进入 index 或 review"
                ),
                text_preview="",
            )
        )

    for chunk_id in unexpected:
        issues.append(
            Issue(
                severity="error",
                category="partition_unexpected",
                file_type="partition",
                record_id=chunk_id,
                source_file="",
                page_start="",
                page_end="",
                message=(
                    "index/review 中存在原始 chunks 没有的 ID"
                ),
                text_preview="",
            )
        )

    return {
        "raw_unique_ids": len(raw_ids),
        "index_unique_ids": len(index_ids),
        "review_unique_ids": len(review_ids),
        "index_review_overlap": len(overlap),
        "missing_from_partition": len(missing),
        "unexpected_in_partition": len(unexpected),
    }


def summarize_review(
    review_chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for row in review_chunks:
        reasons = row.get(
            "index_exclusion_reasons",
            [],
        )

        if not isinstance(reasons, list):
            reasons = [str(reasons)]

        result.append(
            {
                "chunk_id": row.get("chunk_id", ""),
                "title": row.get("title", ""),
                "source_file": row.get(
                    "source_file",
                    "",
                ),
                "page_start": row.get(
                    "page_start",
                    "",
                ),
                "page_end": row.get(
                    "page_end",
                    "",
                ),
                "section_title": row.get(
                    "section_title",
                    "",
                ),
                "char_count": row.get(
                    "char_count",
                    "",
                ),
                "reasons": reasons,
                "matched_low_quality_pages": row.get(
                    "matched_low_quality_pages",
                    [],
                ),
                "text": row.get("text", ""),
            }
        )

    return result


def main() -> int:
    args = parse_args()

    if not 0 <= args.quality_threshold <= 1:
        print(
            "[ERROR] --quality-threshold 必须在 0～1"
        )
        return 2

    base_dir = args.base_dir.resolve()
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else base_dir / "validation"
    )

    paths = {
        "pages": base_dir / "pages.jsonl",
        "raw_chunks": base_dir / "chunks.jsonl",
        "index_chunks": (
            base_dir
            / "index_ready"
            / "chunks_for_index.jsonl"
        ),
        "review_chunks": (
            base_dir
            / "index_ready"
            / "chunks_for_review.jsonl"
        ),
    }

    try:
        pages = read_jsonl(paths["pages"])
        raw_chunks = read_jsonl(paths["raw_chunks"])
        index_chunks = read_jsonl(
            paths["index_chunks"]
        )
        review_chunks = read_jsonl(
            paths["review_chunks"]
        )
    except (FileNotFoundError, ValueError) as error:
        print(f"[ERROR] {error}")
        return 2

    issues: list[Issue] = []

    check_required_fields(
        pages,
        REQUIRED_PAGE_FIELDS,
        "pages",
        issues,
    )
    check_required_fields(
        raw_chunks,
        REQUIRED_CHUNK_FIELDS,
        "raw",
        issues,
    )
    check_required_fields(
        index_chunks,
        REQUIRED_CHUNK_FIELDS,
        "index",
        issues,
    )
    check_required_fields(
        review_chunks,
        REQUIRED_CHUNK_FIELDS,
        "review",
        issues,
    )

    page_numbers, max_pages, _ = build_page_maps(
        pages
    )
    missing_page_records = check_page_sequences(
        page_numbers,
        issues,
    )

    duplicate_page_keys = []
    page_key_counter = Counter(
        (
            str(row.get("source_file") or ""),
            safe_int(row.get("page_number")),
        )
        for row in pages
    )

    for key, count in page_key_counter.items():
        if count > 1:
            duplicate_page_keys.append(key)
            issues.append(
                Issue(
                    severity="error",
                    category="duplicate_page",
                    file_type="pages",
                    record_id="",
                    source_file=key[0],
                    page_start=str(key[1] or ""),
                    page_end="",
                    message="同一 PDF 页出现多次",
                    text_preview="",
                )
            )

    raw_duplicate_ids = check_duplicate_ids(
        raw_chunks,
        "chunk_id",
        "raw",
        issues,
    )
    index_duplicate_ids = check_duplicate_ids(
        index_chunks,
        "chunk_id",
        "index",
        issues,
    )
    review_duplicate_ids = check_duplicate_ids(
        review_chunks,
        "chunk_id",
        "review",
        issues,
    )

    raw_stats = check_chunk_rows(
        raw_chunks,
        "raw",
        max_pages,
        args.strict,
        issues,
    )
    index_stats = check_chunk_rows(
        index_chunks,
        "index",
        max_pages,
        args.strict,
        issues,
    )
    review_stats = check_chunk_rows(
        review_chunks,
        "review",
        max_pages,
        args.strict,
        issues,
    )

    partition_stats = check_partition(
        raw_chunks,
        index_chunks,
        review_chunks,
        issues,
    )

    empty_page_text_rows = [
        page
        for page in pages
        if not str(page.get("clean_text") or "").strip()
    ]

    for page in empty_page_text_rows:
        issues.append(
            Issue(
                severity="warning",
                category="empty_page_text",
                file_type="pages",
                record_id=str(page.get("document_id") or ""),
                source_file=str(page.get("source_file") or ""),
                page_start=str(page.get("page_number") or ""),
                page_end="",
                message=(
                    "页面没有可提取文本，可能是空白页、纯图像页或图表页；"
                    "该情况不阻止其他文本块入库。"
                ),
                text_preview="",
            )
        )

    low_quality_pages = [
        page
        for page in pages
        if (
            safe_float(page.get("final_quality"))
            is not None
            and float(page["final_quality"])
            < args.quality_threshold
        )
    ]

    ocr_pages = [
        page
        for page in pages
        if page.get("extraction_method")
        == "tesseract_ocr"
    ]

    review_summary = summarize_review(
        review_chunks
    )

    suspect_sections = (
        raw_stats["suspect_sections"]
        + index_stats["suspect_sections"]
        + review_stats["suspect_sections"]
    )

    # 去重：同一 chunk 可能同时在 raw 和 index/review 中被检查。
    unique_suspects: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    for row in suspect_sections:
        key = (
            str(row.get("chunk_id") or ""),
            str(row.get("section_title") or ""),
        )
        unique_suspects[key] = row

    severity_counts = Counter(
        issue.severity
        for issue in issues
    )
    category_counts = Counter(
        issue.category
        for issue in issues
    )

    blocking_errors = severity_counts.get(
        "error",
        0,
    )

    report = {
        "script_version": SCRIPT_VERSION,
        "base_dir": str(base_dir),
        "strict_mode": args.strict,
        "quality_threshold": (
            args.quality_threshold
        ),
        "files": {
            key: str(value)
            for key, value in paths.items()
        },
        "counts": {
            "pages": len(pages),
            "documents": len(
                {
                    str(page.get("document_id"))
                    for page in pages
                    if page.get("document_id")
                }
            ),
            "source_pdfs": len(page_numbers),
            "ocr_pages": len(ocr_pages),
            "low_quality_pages": len(
                low_quality_pages
            ),
            "empty_page_text": len(
                empty_page_text_rows
            ),
            "raw_chunks": len(raw_chunks),
            "indexable_chunks": len(
                index_chunks
            ),
            "review_chunks": len(
                review_chunks
            ),
        },
        "partition": partition_stats,
        "page_checks": {
            "duplicate_page_records": len(
                duplicate_page_keys
            ),
            "documents_with_missing_pages": len(
                missing_page_records
            ),
        },
        "raw_chunk_checks": {
            key: value
            for key, value in raw_stats.items()
            if key != "suspect_sections"
        },
        "index_chunk_checks": {
            key: value
            for key, value in index_stats.items()
            if key != "suspect_sections"
        },
        "review_chunk_checks": {
            key: value
            for key, value in review_stats.items()
            if key != "suspect_sections"
        },
        "duplicate_ids": {
            "raw": len(raw_duplicate_ids),
            "index": len(index_duplicate_ids),
            "review": len(review_duplicate_ids),
        },
        "issues": {
            "total": len(issues),
            "blocking_errors": blocking_errors,
            "warnings": severity_counts.get(
                "warning",
                0,
            ),
            "by_category": dict(
                sorted(category_counts.items())
            ),
        },
        "result": (
            "PASS"
            if blocking_errors == 0
            else "FAIL"
        ),
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_json(
        output_dir / "validation_report.json",
        report,
    )

    issue_fields = [
        "severity",
        "category",
        "file_type",
        "record_id",
        "source_file",
        "page_start",
        "page_end",
        "message",
        "text_preview",
    ]
    write_csv(
        output_dir / "validation_issues.csv",
        [asdict(issue) for issue in issues],
        issue_fields,
    )

    low_page_fields = [
        "document_id",
        "source_file",
        "page_number",
        "extraction_method",
        "native_quality",
        "final_quality",
        "char_count",
        "clean_text",
    ]
    write_csv(
        output_dir / "low_quality_pages.csv",
        low_quality_pages,
        low_page_fields,
    )

    suspect_fields = [
        "chunk_id",
        "title",
        "source_file",
        "page_start",
        "page_end",
        "section_title",
        "reasons",
        "text",
    ]
    write_csv(
        output_dir / "suspect_sections.csv",
        unique_suspects.values(),
        suspect_fields,
    )

    review_fields = [
        "chunk_id",
        "title",
        "source_file",
        "page_start",
        "page_end",
        "section_title",
        "char_count",
        "reasons",
        "matched_low_quality_pages",
        "text",
    ]
    write_csv(
        output_dir / "review_summary.csv",
        review_summary,
        review_fields,
    )

    print("=" * 72)
    print("HKCMMS GraphRAG 数据质量检查")
    print("=" * 72)
    print(f"脚本版本            : {SCRIPT_VERSION}")
    print(f"页面总数            : {len(pages)}")
    print(f"PDF 数量            : {len(page_numbers)}")
    print(f"OCR 页面            : {len(ocr_pages)}")
    print(
        f"低质量页面          : {len(low_quality_pages)}"
    )
    print(
        f"无可提取文本页面    : {len(empty_page_text_rows)}"
    )
    print(f"原始文本块          : {len(raw_chunks)}")
    print(
        f"可入库文本块        : {len(index_chunks)}"
    )
    print(
        f"待复核文本块        : {len(review_chunks)}"
    )
    print("-" * 72)
    print(
        "index 中明显乱码    : "
        f"{index_stats['garbled_text']}"
    )
    print(
        "index 中空文本      : "
        f"{index_stats['empty_text']}"
    )
    print(
        "index 重复 chunk_id : "
        f"{len(index_duplicate_ids)}"
    )
    print(
        "分区遗漏 chunk      : "
        f"{partition_stats['missing_from_partition']}"
    )
    print(
        "分区重复 chunk      : "
        f"{partition_stats['index_review_overlap']}"
    )
    print(
        "疑似章节标题        : "
        f"{len(unique_suspects)}"
    )
    print("-" * 72)
    print(
        f"阻塞性问题          : {blocking_errors}"
    )
    print(
        f"警告                : "
        f"{severity_counts.get('warning', 0)}"
    )
    print(f"最终结果            : {report['result']}")
    print()
    print(f"报告目录：{output_dir}")
    print(
        "主报告："
        f"{output_dir / 'validation_report.json'}"
    )
    print(
        "问题清单："
        f"{output_dir / 'validation_issues.csv'}"
    )
    print(
        "低质量页面："
        f"{output_dir / 'low_quality_pages.csv'}"
    )
    print(
        "待复核块："
        f"{output_dir / 'review_summary.csv'}"
    )

    if blocking_errors == 0:
        print()
        print(
            "[PASS] 未发现阻止向量入库的结构性问题。"
        )
        return 0

    print()
    print(
        "[FAIL] 存在阻塞性问题，请先查看 "
        "validation_issues.csv。"
    )
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print()
        print("[INTERRUPTED] 用户中断检查。")
        raise SystemExit(130)
