#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
将 HKCMMS 安全入库集转换为当前 Milvus RAG 可导入的统一 chunk 格式。

输入来自：
data/pharmacopoeia/processed/hkcmms/index_ready/chunks_for_index.jsonl

输出字段兼容 scripts/milvus_insert.py：
chunk_id, doc_id, title, content, source, metadata
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable, Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.hkcmms_cleaning import (
    clean_hkcmms_section_title,
    clean_hkcmms_title,
)

DEFAULT_INPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "pharmacopoeia"
    / "processed"
    / "hkcmms"
    / "index_ready"
    / "chunks_for_index.jsonl"
)

DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "pharmacopoeia"
    / "processed"
    / "hkcmms"
    / "index_ready"
    / "chunks_for_milvus.jsonl"
)

DEFAULT_BASE_CORPUS_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "rag_corpus_clean.jsonl"
)

DEFAULT_COMBINED_OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "rag_corpus_with_hkcmms.jsonl"
)

MILVUS_CONTENT_MAX_LENGTH = 8192
MILVUS_TITLE_MAX_LENGTH = 512

MAJOR_SECTION_TYPES = {
    "name",
    "source",
    "description",
    "identification",
    "tests",
    "assay",
    "chromatography",
}

GENERIC_SUBSECTION_TITLES = {
    "操作程序",
    "供試品溶液",
    "对照品溶液",
    "對照品溶液",
    "展開劑",
    "显色剂",
    "顯色劑",
    "色譜系統",
    "系统适用性要求",
    "系統適用性要求",
}


TRADITIONAL_TO_SIMPLIFIED = str.maketrans(
    {
        "黃": "黄",
        "芪": "芪",
        "澤": "泽",
        "瀉": "泻",
        "龍": "龙",
        "膽": "胆",
        "貝": "贝",
        "蘭": "兰",
        "薑": "姜",
        "參": "参",
        "靈": "灵",
        "風": "风",
        "濕": "湿",
        "熱": "热",
        "氣": "气",
        "血": "血",
        "藥": "药",
        "醫": "医",
        "標": "标",
        "準": "准",
        "檢": "检",
        "測": "测",
        "鑑": "鉴",
        "別": "别",
        "質": "质",
        "量": "量",
        "乾": "干",
        "燥": "燥",
        "葉": "叶",
        "莖": "茎",
        "實": "实",
        "陰": "阴",
        "陽": "阳",
        "經": "经",
        "絡": "络",
        "與": "与",
        "為": "为",
        "後": "后",
        "處": "处",
        "圖": "图",
        "號": "号",
        "冊": "册",
        "頁": "页",
        "廣": "广",
        "東": "东",
        "兒": "儿",
        "長": "长",
        "麥": "麦",
        "黨": "党",
        "歸": "归",
        "鬱": "郁",
        "馬": "马",
        "鱉": "鳖",
        "龜": "龟",
        "獨": "独",
        "連": "连",
        "銀": "银",
        "紅": "红",
        "藍": "蓝",
    }
)


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as file:
        for line_no, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path} 第 {line_no} 行 JSON 解析失败"
                ) from exc


def write_jsonl(
    path: Path,
    rows: Iterable[dict[str, Any]],
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0

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
            count += 1

    return count


def to_simplified_hint(text: str) -> str:
    return text.translate(TRADITIONAL_TO_SIMPLIFIED)


def compact_text(text: str) -> str:
    return " ".join(
        str(text)
        .replace("\r", "\n")
        .split()
    ).strip()


def normalize_section_title(text: str) -> str:
    """修正常见 HKCMMS 旧版 PDF 字体映射造成的栏目标题噪声。"""
    value = compact_text(text)

    replacements = {
        "Uff IV(A)]": "附錄IV(A)]",
        "[Uff IV(A)]": "[附錄IV(A)]",
        "(Uff IV(A)]": "[附錄IV(A)]",
        "MER XID": "附錄XII",
        "lee XD": "附錄IXD",
        "應絲 0": "附錄IX",
        "應絲Xy": "附錄IX",
        "和誰儿 VD": "附錄IVD",
        "鷹線 VID": "附錄IVD",
    }

    for source, target in replacements.items():
        value = value.replace(source, target)

    value = re.sub(
        r"附錄\(附錄XII\)XII",
        "附錄XII",
        value,
    )
    value = re.sub(
        r"鑒別譜法",
        "鑒別法",
        value,
    )
    value = re.sub(
        r"譜法\(附錄XII\)",
        "法（附錄XII）",
        value,
    )
    value = re.sub(
        r"\((附錄[^)]*)\]",
        r"（\1）",
        value,
    )
    value = re.sub(
        r"\[附錄([^]]+)\]",
        r"（附錄\1）",
        value,
    )
    value = re.sub(
        r"\((附錄[^)]*)\)",
        r"（\1）",
        value,
    )
    value = value.replace("  ", " ")

    return value.strip()


def truncate_text(
    text: str,
    max_length: int,
) -> str:
    if len(text) <= max_length:
        return text

    suffix = "\n\n[内容因 Milvus 字段长度限制已截断，请回溯原始 HKCMMS PDF 核对全文。]"
    return text[: max_length - len(suffix)].rstrip() + suffix


def format_section(
    number: Any,
    title: Any,
) -> str:
    section_number = compact_text(number or "")
    section_title = clean_hkcmms_section_title(
        normalize_section_title(title or "正文")
    )

    if section_number:
        return f"{section_number} {section_title}".strip()

    return section_title


def add_section_context(
    rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched_rows: list[dict[str, Any]] = []
    current_doc_id = ""
    current_major = ""

    for row in rows:
        item = dict(row)
        doc_id = str(
            item.get("document_id")
            or item.get("doc_id")
            or ""
        )

        if doc_id != current_doc_id:
            current_doc_id = doc_id
            current_major = ""

        section_type = str(item.get("section_type") or "")
        section_title = normalize_section_title(
            item.get("section_title") or ""
        )
        section_number = compact_text(item.get("section_number") or "")
        current_section = format_section(
            section_number,
            section_title,
        )

        if (
            section_type in MAJOR_SECTION_TYPES
            and section_title
        ):
            current_major = current_section

        elif (
            re.fullmatch(
                r"\d+",
                section_number,
            )
            and section_title
            and section_title not in GENERIC_SUBSECTION_TITLES
        ):
            current_major = current_section

        item["parent_section"] = current_major

        enriched_rows.append(item)

    return enriched_rows


def build_title(row: dict[str, Any]) -> str:
    chinese_name = compact_text(
        row.get("chinese_name")
        or row.get("title")
        or "未知药材"
    )
    section = format_section(
        row.get("section_number"),
        row.get("section_title"),
    )
    parent_section = compact_text(
        row.get("parent_section") or ""
    )
    raw_title = compact_text(row.get("section_title") or "")

    if (
        parent_section
        and parent_section != section
        and raw_title in GENERIC_SUBSECTION_TITLES
    ):
        section = f"{parent_section}｜{raw_title}"

    title = clean_hkcmms_title(
        f"HKCMMS：{chinese_name}｜{section}"
    )
    return truncate_text(
        title,
        MILVUS_TITLE_MAX_LENGTH,
    )


def build_content(row: dict[str, Any]) -> str:
    chinese_name = compact_text(
        row.get("chinese_name")
        or row.get("title")
        or ""
    )
    simplified_name = to_simplified_hint(chinese_name)
    official_name = compact_text(row.get("official_name") or "")
    pinyin_name = compact_text(row.get("pinyin_name") or "")
    section = format_section(
        row.get("section_number"),
        row.get("section_title"),
    )
    parent_section = compact_text(
        row.get("parent_section") or ""
    )
    page_start = row.get("page_start") or ""
    page_end = row.get("page_end") or page_start
    citation = compact_text(row.get("citation") or "")
    source_file = compact_text(row.get("source_file") or "")
    source_url = compact_text(row.get("source_url") or "")
    body = compact_text(row.get("text") or "")

    aliases = [
        value
        for value in [
            chinese_name,
            simplified_name if simplified_name != chinese_name else "",
            official_name,
            pinyin_name,
        ]
        if value
    ]

    lines = [
        "资料库：香港中药材标准（HKCMMS, Hong Kong Chinese Materia Medica Standards）",
        f"药材条目：{chinese_name}",
        f"检索别名：{' / '.join(dict.fromkeys(aliases))}",
        f"章节：{section}",
        f"上级章节：{parent_section}" if parent_section else "",
        f"页码：{page_start}-{page_end}",
        f"引用：{citation}",
        f"原始文件：{source_file}",
        f"官方来源：{source_url}",
        "",
        "正文：",
        body,
    ]

    return truncate_text(
        "\n".join(line for line in lines if line).strip(),
        MILVUS_CONTENT_MAX_LENGTH,
    )


def convert_row(row: dict[str, Any]) -> dict[str, Any]:
    chunk_id = str(row.get("chunk_id") or "").strip()

    if not chunk_id:
        raise ValueError("HKCMMS chunk 缺少 chunk_id")

    document_id = str(
        row.get("document_id")
        or row.get("doc_id")
        or ""
    ).strip()

    if not document_id:
        raise ValueError(
            f"{chunk_id} 缺少 document_id"
        )

    content = build_content(row)

    if not content:
        raise ValueError(
            f"{chunk_id} 内容为空"
        )

    chinese_name = compact_text(row.get("chinese_name") or row.get("title"))
    section_title = clean_hkcmms_section_title(
        normalize_section_title(row.get("section_title") or "")
    )
    parent_section = clean_hkcmms_section_title(
        normalize_section_title(row.get("parent_section") or "")
    )

    return {
        "chunk_id": chunk_id,
        "doc_id": document_id,
        "title": build_title(row),
        "content": content,
        "source": "HKCMMS",
        "record_type": "pharmacopoeia_monograph",
        "chinese_name": chinese_name,
        "chinese_name_simplified": to_simplified_hint(chinese_name),
        "official_name": compact_text(row.get("official_name") or ""),
        "pinyin_name": compact_text(row.get("pinyin_name") or ""),
        "section_type": compact_text(row.get("section_type") or ""),
        "section_number": compact_text(row.get("section_number") or ""),
        "section_title": section_title,
        "parent_section": parent_section,
        "citation": compact_text(row.get("citation") or ""),
        "source_url": compact_text(row.get("source_url") or ""),
        "metadata": {
            "record_type": "pharmacopoeia_monograph",
            "source_id": "HKCMMS",
            "source_name": "香港中药材标准",
            "publisher": "香港特别行政区政府卫生署中医药规管办公室",
            "volume": row.get("volume"),
            "language": row.get("language"),
            "category": row.get("category"),
            "official_name": row.get("official_name"),
            "chinese_name": chinese_name,
            "chinese_name_simplified": to_simplified_hint(chinese_name),
            "pinyin_name": row.get("pinyin_name"),
            "section_id": row.get("section_id"),
            "section_number": row.get("section_number"),
            "section_title": section_title,
            "parent_section": parent_section,
            "section_type": row.get("section_type"),
            "page_start": row.get("page_start"),
            "page_end": row.get("page_end"),
            "source_file": row.get("source_file"),
            "source_url": row.get("source_url"),
            "citation": row.get("citation"),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build HKCMMS corpus chunks compatible with "
            "the current GraphRAG Milvus schema."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="HKCMMS chunks_for_index.jsonl 路径。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="输出的 HKCMMS Milvus chunk JSONL 路径。",
    )
    parser.add_argument(
        "--base-corpus",
        type=Path,
        default=DEFAULT_BASE_CORPUS_PATH,
        help="现有 RAG 语料路径，用于生成合并版语料。",
    )
    parser.add_argument(
        "--combined-output",
        type=Path,
        default=None,
        help=(
            "可选：输出合并后的完整语料。"
            "不传时只生成 HKCMMS 增量语料。"
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.input.exists():
        raise FileNotFoundError(
            f"找不到 HKCMMS 输入文件: {args.input}"
        )

    source_rows = add_section_context(
        read_jsonl(args.input)
    )

    converted_rows = [
        convert_row(row)
        for row in source_rows
    ]

    output_count = write_jsonl(
        args.output,
        converted_rows,
    )

    print("=" * 68)
    print("HKCMMS RAG 语料转换完成")
    print("=" * 68)
    print(f"输入文件: {args.input}")
    print(f"输出文件: {args.output}")
    print(f"输出 chunk 数: {output_count}")

    if args.combined_output is not None:
        if not args.base_corpus.exists():
            raise FileNotFoundError(
                f"找不到基础 RAG 语料: {args.base_corpus}"
            )

        args.combined_output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with args.combined_output.open(
            "wb",
        ) as combined_file:
            with args.base_corpus.open(
                "rb",
            ) as base_file:
                shutil.copyfileobj(
                    base_file,
                    combined_file,
                )

            combined_file.write(b"\n")

            with args.output.open(
                "rb",
            ) as hkcmms_file:
                shutil.copyfileobj(
                    hkcmms_file,
                    combined_file,
                )

        print(f"合并语料: {args.combined_output}")

    print()
    print("下一步导入增量语料：")
    print(
        "python scripts/milvus_insert.py "
        f"--input {args.output} "
        "--limit 0"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
