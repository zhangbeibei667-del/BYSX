#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
HKCMMS GraphRAG 文档提取、清洗、章节识别与分块脚本
====================================================

适用项目：
    基于知识图谱的中医药诊疗智能体
    成员 3：GraphRAG

主要功能：
    1. 支持读取目录或 ZIP 压缩包中的 HKCMMS PDF。
    2. 优先使用 PDF 原生文本层提取。
    3. 自动检测乱码、缺字和低质量文本页。
    4. 对低质量页自动调用 Tesseract OCR（可关闭或强制）。
    5. 清理控制字符、重复页眉页脚、页码、异常空格和断行。
    6. 提取药材正名、中文名、汉语拼音名、来源 URL 等元数据。
    7. 识别“名称、来源、性状、鉴别、检查、含量测定”等章节。
    8. 生成适合向量检索和 GraphRAG 的带重叠文本块。
    9. 每个文本块保留文档、卷册、页码、章节和引用信息。
   10. 生成处理质量报告、异常报告及可增量复用的文档缓存。


依赖：
    pip install PyMuPDF

OCR 依赖（仅乱码页需要）：
    安装 Tesseract OCR，并安装繁体中文和英文语言数据。
    Windows 可通过 --tesseract-cmd 指定 tesseract.exe。

常用命令：

    # 处理精选 33 篇 ZIP，自动对乱码页 OCR
    python scripts/prepare_hkcmms_graphrag.py ^
      --input data/pharmacopoeia/raw/hkcmms/hkcmms_graphrag_selected_33.zip

    # PowerShell 多行写法
    python scripts/prepare_hkcmms_graphrag.py `
      --input data/pharmacopoeia/raw/hkcmms/hkcmms_graphrag_selected_33.zip

    # 输入是已经解压的目录
    python scripts/prepare_hkcmms_graphrag.py `
      --input data/pharmacopoeia/raw/hkcmms

    # 不使用 OCR，只检查原生文本质量
    python scripts/prepare_hkcmms_graphrag.py `
      --input data/pharmacopoeia/raw/hkcmms `
      --ocr never

    # Windows 指定 Tesseract
    python scripts/prepare_hkcmms_graphrag.py `
      --input data/pharmacopoeia/raw/hkcmms `
      --tesseract-cmd "C:\Program Files\Tesseract-OCR\tesseract.exe"

    # 强制重新处理全部文档
    python scripts/prepare_hkcmms_graphrag.py `
      --input data/pharmacopoeia/raw/hkcmms `
      --force

主要输出：
    documents.jsonl
        文档级清洗结果。

    pages.jsonl
        页面级清洗结果，包含提取方式和质量分数。

    sections.jsonl
        章节级数据。

    chunks.jsonl
        GraphRAG 检索文本块，推荐直接用于向量入库。

    processing_report.csv
        每份 PDF 的处理统计和 OCR 情况。

    errors.jsonl
        处理失败或 OCR 缺失记录。

    text/*.txt
        每份文档的清洗后纯文本。

    cache/*.json
        文档级中间结果，用于断点续处理。

说明：
    - 本脚本负责“文档清洗与分块”，不直接写入具体向量数据库。
    - chunks.jsonl 可供 Chroma、Milvus、FAISS、Elasticsearch、
      pgvector 或其他检索组件使用。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator, Optional, Sequence

try:
    import fitz  # PyMuPDF
except ImportError as exc:
    raise SystemExit(
        "缺少 PyMuPDF。请运行：\n"
        "python -m pip install PyMuPDF"
    ) from exc


SCRIPT_VERSION = "1.0.0"

DEFAULT_CHUNK_SIZE = 850
DEFAULT_CHUNK_OVERLAP = 120
DEFAULT_NATIVE_QUALITY_THRESHOLD = 0.58
DEFAULT_OCR_DPI = 200
DEFAULT_OCR_TIMEOUT = 60
DEFAULT_OCR_MIN_NATIVE_CHARS = 160
DEFAULT_OCR_LANG = "chi_tra+eng"

CJK_RANGE = r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
CJK_CHAR_RE = re.compile(f"[{CJK_RANGE}]")
LATIN_CHAR_RE = re.compile(r"[A-Za-z]")
CONTROL_CHAR_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"
)
MULTISPACE_RE = re.compile(r"[ \t\u00a0\u2000-\u200b\u202f\u205f\u3000]+")
PAGE_NUMBER_RE = re.compile(
    r"^\s*(?:第\s*)?\d{1,4}\s*(?:頁|页)?\s*$",
    flags=re.IGNORECASE,
)
ROMAN_PAGE_RE = re.compile(
    r"^\s*[ivxlcdm]{1,8}\s*$",
    flags=re.IGNORECASE,
)
MAIN_HEADING_RE = re.compile(
    r"^\s*([1-9]\d?)\s*[.．]\s*([^\d\s].{0,79}?)\s*$"
)
SUBHEADING_RE = re.compile(
    r"^\s*([1-9]\d?(?:[.．][0-9lI]{1,2}){1,3})"
    r"\s+(.{1,80}?)\s*$"
)
METADATA_FIELD_RE = re.compile(
    r"^(?:藥材正名|药材正名|中文名|漢語拼音名|汉语拼音名|"
    r"漢語拼音|汉语拼音)\s*[：:]"
)
PART_HEADING_RE = re.compile(
    r"^\s*第[一二三四五六七八九十]+(?:部份|部分|篇|章)"
    r".{0,80}$"
)
FIGURE_LINE_RE = re.compile(
    r"^\s*(?:圖|图|表)\s*\d+",
    flags=re.IGNORECASE,
)
APPENDIX_REF_RE = re.compile(
    r"附錄\s*[IVXLC\d]+(?:\s*[（(][A-Z\d]+[）)])?",
    flags=re.IGNORECASE,
)
LATIN_BINOMIAL_RE = re.compile(
    r"\b([A-Z][a-z]{2,})\s+([a-z][a-z\-]{2,})\b"
)

KNOWN_SHORT_HEADINGS = {
    "橫切面",
    "横切面",
    "粉末",
    "操作程序",
    "對照品溶液",
    "对照品溶液",
    "供試品溶液",
    "供试品溶液",
    "展開劑",
    "展开剂",
    "顯色劑",
    "显色剂",
    "系統適用性",
    "系统适用性",
    "色譜條件",
    "色谱条件",
    "標準曲線",
    "标准曲线",
    "測定法",
    "测定法",
    "結果",
    "结果",
    "第一部分",
    "第一部份",
    "第二部分",
    "第二部份",
    "第三部分",
    "第三部份",
    "第四部分",
    "第四部份",
}

SEMANTIC_SECTION_ALIASES = {
    "名稱": "name",
    "名称": "name",
    "來源": "source",
    "来源": "source",
    "性狀": "description",
    "性状": "description",
    "鑒別": "identification",
    "鉴别": "identification",
    "檢查": "tests",
    "检查": "tests",
    "浸出物": "extractives",
    "含量測定": "assay",
    "含量测定": "assay",
    "貯藏": "storage",
    "贮藏": "storage",
    "炮製": "processing",
    "炮制": "processing",
    "功能與主治": "functions",
    "功能与主治": "functions",
    "用法與用量": "dosage",
    "用法与用量": "dosage",
    "注意": "caution",
}

SENTENCE_ENDINGS = "。！？；.!?;"


@dataclass
class SourcePdf:
    source_id: str
    display_path: str
    relative_path: str
    zip_member: Optional[str]
    filesystem_path: Optional[str]
    volume: Optional[int]
    language: Optional[str]
    category: Optional[str]
    title_hint: str
    source_url: str


@dataclass
class PageResult:
    page_number: int
    extraction_method: str
    native_quality: float
    final_quality: float
    needs_ocr: bool
    char_count: int
    raw_text: str
    clean_text: str


@dataclass
class SectionResult:
    section_id: str
    document_id: str
    section_number: str
    section_title: str
    section_type: str
    page_start: int
    page_end: int
    text: str


@dataclass
class ChunkResult:
    chunk_id: str
    document_id: str
    volume: Optional[int]
    language: Optional[str]
    category: Optional[str]
    title: str
    official_name: str
    chinese_name: str
    pinyin_name: str
    section_id: str
    section_number: str
    section_title: str
    section_type: str
    page_start: int
    page_end: int
    text: str
    char_count: int
    source_file: str
    source_url: str
    citation: str
    appendix_references: list[str]
    latin_species: list[str]


def json_dumps(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json_dumps(row))
            file.write("\n")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        while True:
            block = file.read(1024 * 1024)
            if not block:
                break
            digest.update(block)

    return digest.hexdigest()


def stable_id(prefix: str, value: str, length: int = 16) -> str:
    digest = hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()[:length]
    return f"{prefix}_{digest}"


def normalize_slashes(value: str) -> str:
    return value.replace("\\", "/").lstrip("./")


def infer_volume(value: str) -> Optional[int]:
    match = re.search(
        r"(?:^|[/\\])vol(\d{1,2})(?:[/\\]|$)",
        value,
        flags=re.IGNORECASE,
    )

    if match:
        return int(match.group(1))

    filename_match = re.search(
        r"_v(\d{1,2})_[ce]\.pdf$",
        value,
        flags=re.IGNORECASE,
    )

    return (
        int(filename_match.group(1))
        if filename_match
        else None
    )


def infer_language(value: str) -> Optional[str]:
    lowered = value.lower().replace("\\", "/")
    filename = PurePosixPath(lowered).name

    if "/zh/" in lowered or filename.endswith("_c.pdf"):
        return "zh"

    if "/en/" in lowered or filename.endswith("_e.pdf"):
        return "en"

    return None


def infer_category(value: str) -> str:
    lowered = value.lower()

    if "preface" in lowered:
        return "preface"

    if "general_notice" in lowered:
        return "general_notices"

    if "index" in lowered:
        return "indexes"

    if "appendix" in lowered or "appendices" in lowered:
        return "appendix"

    return "monograph"


def filename_title_hint(value: str) -> str:
    stem = Path(value).stem
    stem = re.sub(r"_v\d+_[ce]$", "", stem, flags=re.IGNORECASE)
    stem = stem.replace("_", " ")
    return " ".join(stem.split())


def locate_manifest_in_zip(archive: zipfile.ZipFile) -> Optional[str]:
    candidates = [
        "manifests/hkcmms_selected_manifest.csv",
        "hkcmms_selected_manifest.csv",
        "manifests/hkcmms_pdf_manifest_selected.csv",
        "hkcmms_pdf_manifest_selected.csv",
    ]

    lower_to_actual = {
        name.lower(): name
        for name in archive.namelist()
    }

    for candidate in candidates:
        actual = lower_to_actual.get(candidate.lower())
        if actual:
            return actual

    csv_names = [
        name
        for name in archive.namelist()
        if name.lower().endswith(".csv")
        and "manifest" in name.lower()
        and "selected" in name.lower()
    ]

    return sorted(csv_names)[0] if csv_names else None


def locate_manifest_in_directory(root: Path) -> Optional[Path]:
    candidates = [
        root / "manifests" / "hkcmms_selected_manifest.csv",
        root / "hkcmms_selected_manifest.csv",
        root / "hkcmms_pdf_manifest_selected.csv",
    ]

    for path in candidates:
        if path.exists():
            return path

    found = sorted(
        path
        for path in root.rglob("*.csv")
        if "manifest" in path.name.lower()
        and "selected" in path.name.lower()
    )

    return found[0] if found else None


def parse_manifest_csv_bytes(data: bytes) -> list[dict[str, str]]:
    text: str

    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = data.decode("utf-8", errors="replace")

    reader = csv.DictReader(text.splitlines())
    return [
        {
            str(key): "" if value is None else str(value)
            for key, value in row.items()
        }
        for row in reader
    ]


def build_source_list(input_path: Path) -> list[SourcePdf]:
    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        return build_sources_from_zip(input_path)

    if input_path.is_dir():
        return build_sources_from_directory(input_path)

    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        relative = input_path.name
        return [
            SourcePdf(
                source_id=stable_id("src", str(input_path.resolve())),
                display_path=str(input_path),
                relative_path=relative,
                zip_member=None,
                filesystem_path=str(input_path.resolve()),
                volume=infer_volume(relative),
                language=infer_language(relative),
                category=infer_category(relative),
                title_hint=filename_title_hint(relative),
                source_url="",
            )
        ]

    raise FileNotFoundError(
        f"输入路径不存在或不是目录、ZIP、PDF：{input_path}"
    )


def build_sources_from_zip(zip_path: Path) -> list[SourcePdf]:
    with zipfile.ZipFile(zip_path, "r") as archive:
        pdf_members = sorted(
            name
            for name in archive.namelist()
            if name.lower().endswith(".pdf")
            and not name.endswith("/")
        )

        manifest_name = locate_manifest_in_zip(archive)
        manifest_rows: list[dict[str, str]] = []

        if manifest_name:
            manifest_rows = parse_manifest_csv_bytes(
                archive.read(manifest_name)
            )

        by_relative: dict[str, dict[str, str]] = {}

        for row in manifest_rows:
            relative = normalize_slashes(
                row.get("relative_path", "")
            )

            if relative:
                by_relative[relative.lower()] = row

        sources: list[SourcePdf] = []

        for member in pdf_members:
            normalized_member = normalize_slashes(member)

            if normalized_member.startswith("pdf/"):
                manifest_relative = normalized_member[4:]
            else:
                manifest_relative = normalized_member

            row = by_relative.get(
                manifest_relative.lower(),
                {},
            )

            relative = (
                row.get("relative_path", "").strip()
                or manifest_relative
            )

            volume = _safe_int(row.get("volume")) or infer_volume(
                relative
            )
            language = (
                row.get("language", "").strip()
                or infer_language(relative)
            )
            category = (
                row.get("category", "").strip()
                or infer_category(relative)
            )
            title_hint = (
                row.get("title", "").strip()
                or filename_title_hint(relative)
            )
            source_url = row.get("url", "").strip()

            sources.append(
                SourcePdf(
                    source_id=stable_id(
                        "src",
                        f"{zip_path.resolve()}::{member}",
                    ),
                    display_path=f"{zip_path}!/{member}",
                    relative_path=relative,
                    zip_member=member,
                    filesystem_path=None,
                    volume=volume,
                    language=language or None,
                    category=category or None,
                    title_hint=title_hint,
                    source_url=source_url,
                )
            )

    return sources


def build_sources_from_directory(root: Path) -> list[SourcePdf]:
    manifest_path = locate_manifest_in_directory(root)
    manifest_rows: list[dict[str, str]] = []

    if manifest_path:
        manifest_rows = parse_manifest_csv_bytes(
            manifest_path.read_bytes()
        )

    by_relative: dict[str, dict[str, str]] = {}

    for row in manifest_rows:
        relative = normalize_slashes(
            row.get("relative_path", "")
        )

        if relative:
            by_relative[relative.lower()] = row

    pdf_paths = sorted(root.rglob("*.pdf"))
    sources: list[SourcePdf] = []

    for pdf_path in pdf_paths:
        relative_from_root = normalize_slashes(
            str(pdf_path.relative_to(root))
        )

        candidates = [
            relative_from_root,
            relative_from_root.removeprefix("pdf/"),
        ]

        row: dict[str, str] = {}

        for candidate in candidates:
            row = by_relative.get(candidate.lower(), {})
            if row:
                break

        relative = (
            row.get("relative_path", "").strip()
            or candidates[-1]
        )

        sources.append(
            SourcePdf(
                source_id=stable_id(
                    "src",
                    str(pdf_path.resolve()),
                ),
                display_path=str(pdf_path),
                relative_path=relative,
                zip_member=None,
                filesystem_path=str(pdf_path.resolve()),
                volume=_safe_int(row.get("volume"))
                or infer_volume(relative),
                language=row.get("language", "").strip()
                or infer_language(relative),
                category=row.get("category", "").strip()
                or infer_category(relative),
                title_hint=row.get("title", "").strip()
                or filename_title_hint(relative),
                source_url=row.get("url", "").strip(),
            )
        )

    return sources


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


class SourceReader:
    def __init__(self, input_path: Path) -> None:
        self.input_path = input_path
        self._archive: Optional[zipfile.ZipFile] = None

    def __enter__(self) -> "SourceReader":
        if (
            self.input_path.is_file()
            and self.input_path.suffix.lower() == ".zip"
        ):
            self._archive = zipfile.ZipFile(
                self.input_path,
                "r",
            )
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc: Any,
        traceback: Any,
    ) -> None:
        if self._archive is not None:
            self._archive.close()
            self._archive = None

    def read_bytes(self, source: SourcePdf) -> bytes:
        if source.zip_member is not None:
            if self._archive is None:
                raise RuntimeError("ZIP reader is not open")
            return self._archive.read(source.zip_member)

        if source.filesystem_path is None:
            raise RuntimeError(
                f"source has no filesystem path: {source.display_path}"
            )

        return Path(source.filesystem_path).read_bytes()


def normalize_unicode(text: str) -> str:
    text = text.replace("\ufeff", "")
    text = text.replace("\u00ad", "")
    text = text.replace("\x00", "")
    text = CONTROL_CHAR_RE.sub("", text)
    text = unicodedata.normalize("NFKC", text)

    replacements = {
        "\r\n": "\n",
        "\r": "\n",
        "–": "-",
        "—": "-",
        "−": "-",
        "﹣": "-",
        "˚C": "°C",
        "μm": "µm",
        "μL": "µL",
        "μg": "µg",
        "（ ": "（",
        " ）": "）",
        "( ": "(",
        " )": ")",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def normalize_line(line: str) -> str:
    line = normalize_unicode(line)
    line = MULTISPACE_RE.sub(" ", line).strip()

    # OCR 常产生“中 文 名”这种逐字空格。
    line = re.sub(
        f"(?<=[{CJK_RANGE}]) +(?=[{CJK_RANGE}])",
        "",
        line,
    )
    line = re.sub(
        f"(?<=[{CJK_RANGE}]) +(?=[：:，。；、）】])",
        "",
        line,
    )
    line = re.sub(
        f"(?<=[（【]) +(?=[{CJK_RANGE}A-Za-z0-9])",
        "",
        line,
    )
    line = re.sub(r"\s+([,.;:!?%])", r"\1", line)
    line = re.sub(r"([（【])\s+", r"\1", line)
    line = re.sub(r"\s+([）】])", r"\1", line)

    # 修正常见标题字段中的 OCR 间距。
    field_fixes = {
        "藥材正名": "藥材正名",
        "药材正名": "藥材正名",
        "中文名": "中文名",
        "漢語拼音名": "漢語拼音名",
        "汉语拼音名": "漢語拼音名",
        "漢語拼音": "漢語拼音名",
        "汉语拼音": "漢語拼音名",
    }

    for candidate, replacement in field_fixes.items():
        match = re.match(
            rf"^{re.escape(candidate)}\s*[：:]?\s*(.*)$",
            line,
            flags=re.IGNORECASE,
        )

        if match:
            suffix = match.group(1).strip()
            return (
                f"{replacement}：{suffix}"
                if suffix
                else replacement
            )

    return line


def normalize_for_frequency(line: str) -> str:
    value = normalize_line(line)
    value = re.sub(r"\d+", "#", value)
    value = re.sub(r"\s+", "", value)
    return value.lower()


def dedupe_exact_repeated_half(lines: list[str]) -> list[str]:
    """
    某些封面页的文本层会完整重复两遍。
    若整页前后两半完全一致，则只保留一半。
    """
    if len(lines) < 4 or len(lines) % 2 != 0:
        return lines

    middle = len(lines) // 2

    first = [
        normalize_for_frequency(line)
        for line in lines[:middle]
    ]
    second = [
        normalize_for_frequency(line)
        for line in lines[middle:]
    ]

    return lines[:middle] if first == second else lines


def native_text_quality(text: str) -> float:
    """
    返回 0～1 的启发式质量分数。

    重点识别：
    - 控制字符；
    - 大量异常符号；
    - 中文 PDF 字体映射错误造成的乱码；
    - 文本过短。
    """
    if not text or not text.strip():
        return 0.0

    normalized = normalize_unicode(text)
    nonspace = [
        char
        for char in normalized
        if not char.isspace()
    ]

    if not nonspace:
        return 0.0

    total = len(nonspace)
    controls = sum(
        1
        for char in text
        if (
            ord(char) < 32
            and char not in "\n\r\t"
        )
    )
    cjk = len(CJK_CHAR_RE.findall(normalized))
    latin = len(LATIN_CHAR_RE.findall(normalized))
    digits = sum(char.isdigit() for char in normalized)
    useful = cjk + latin + digits

    expected_punctuation = sum(
        char in "，。；：、（）()[]【】,.:%+-/°µ"
        for char in normalized
    )
    strange = max(
        0,
        total - useful - expected_punctuation,
    )

    control_ratio = controls / max(len(text), 1)
    useful_ratio = useful / total
    strange_ratio = strange / total

    # 常见字体映射损坏表现。
    gibberish_patterns = [
        r"\x1f",
        r"[=][A-Za-z]{1,4}[=]",
        r"[!#$%&']{4,}",
        r"(?:[A-Za-z]=){3,}",
        r"[ÇÄÖÜ]{2,}",
    ]

    gibberish_hits = sum(
        len(re.findall(pattern, text))
        for pattern in gibberish_patterns
    )
    gibberish_penalty = min(
        0.55,
        gibberish_hits / 25,
    )

    length_score = min(1.0, total / 220.0)

    score = (
        0.38 * useful_ratio
        + 0.22 * length_score
        + 0.24 * min(1.0, cjk / max(total * 0.25, 1))
        + 0.16 * (1.0 - min(1.0, strange_ratio))
        - 2.5 * min(control_ratio, 0.4)
        - gibberish_penalty
    )

    return max(0.0, min(1.0, score))


def split_raw_lines(text: str) -> list[str]:
    text = normalize_unicode(text)
    lines = [
        normalize_line(line)
        for line in text.splitlines()
    ]
    lines = [line for line in lines if line]
    return dedupe_exact_repeated_half(lines)


def identify_repeated_margin_lines(
    page_lines: list[list[str]],
) -> set[str]:
    """
    依据各页前 22 行和后 10 行识别重复页眉、页脚、侧边目录。
    """
    page_count = len(page_lines)

    if page_count < 3:
        return set()

    counter: Counter[str] = Counter()

    for lines in page_lines:
        candidates = lines[:22] + lines[-10:]
        seen_on_page: set[str] = set()

        for line in candidates:
            normalized = normalize_for_frequency(line)

            if (
                len(normalized) < 2
                or len(normalized) > 80
                or PAGE_NUMBER_RE.match(line)
                or ROMAN_PAGE_RE.match(line)
            ):
                continue

            seen_on_page.add(normalized)

        counter.update(seen_on_page)

    threshold = max(
        2,
        math.ceil(page_count * 0.45),
    )

    return {
        line
        for line, count in counter.items()
        if count >= threshold
    }


def is_heading_line(line: str) -> bool:
    stripped = line.strip()

    if (
        MAIN_HEADING_RE.match(stripped)
        or SUBHEADING_RE.match(stripped)
        or PART_HEADING_RE.match(stripped)
    ):
        return True

    normalized = re.sub(r"\s+", "", stripped)

    if normalized in KNOWN_SHORT_HEADINGS:
        return True

    if (
        len(normalized) <= 18
        and normalized in SEMANTIC_SECTION_ALIASES
    ):
        return True

    return False


def should_join_lines(previous: str, current: str) -> bool:
    if not previous or not current:
        return False

    if is_heading_line(previous) or is_heading_line(current):
        return False

    if (
        METADATA_FIELD_RE.match(previous)
        or METADATA_FIELD_RE.match(current)
    ):
        return False

    if FIGURE_LINE_RE.match(current):
        return False

    if previous[-1] in SENTENCE_ENDINGS + "：:":
        return False

    # 拉丁单词跨行断词。
    if (
        previous.endswith("-")
        and re.search(r"[A-Za-z]-$", previous)
        and re.match(r"^[a-z]", current)
    ):
        return True

    # 中文正文通常应合并换行。
    if (
        CJK_CHAR_RE.search(previous[-1:])
        or previous[-1].isalnum()
        or previous[-1] in "）】"
    ):
        return True

    return False


def clean_page_lines(
    lines: list[str],
    repeated_margin_lines: set[str],
) -> list[str]:
    cleaned: list[str] = []
    previous_key = ""

    for line in lines:
        line = normalize_line(line)

        if not line:
            continue

        key = normalize_for_frequency(line)

        if (
            PAGE_NUMBER_RE.match(line)
            or ROMAN_PAGE_RE.match(line)
        ):
            continue

        if key in repeated_margin_lines:
            continue

        # 连续重复标题、图注或文本行只保留一份。
        if key and key == previous_key:
            continue

        cleaned.append(line)
        previous_key = key

    return cleaned


def lines_to_clean_text(lines: list[str]) -> str:
    paragraphs: list[str] = []
    current = ""

    for line in lines:
        if not current:
            current = line
            continue

        if should_join_lines(current, line):
            if (
                current.endswith("-")
                and re.search(r"[A-Za-z]-$", current)
                and re.match(r"^[a-z]", line)
            ):
                current = current[:-1] + line
            else:
                separator = _join_separator(current, line)
                current += separator + line
        else:
            paragraphs.append(current.strip())
            current = line

    if current:
        paragraphs.append(current.strip())

    text = "\n".join(
        paragraph
        for paragraph in paragraphs
        if paragraph
    )

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _join_separator(previous: str, current: str) -> str:
    if (
        CJK_CHAR_RE.search(previous[-1:])
        and CJK_CHAR_RE.search(current[:1])
    ):
        return ""

    if (
        previous[-1].isalnum()
        and current[:1].isalnum()
    ):
        return " "

    return ""


def resolve_tesseract_command(
    configured: Optional[str],
) -> Optional[str]:
    if configured:
        path = Path(configured)

        if path.exists():
            return str(path)

        found = shutil.which(configured)
        if found:
            return found

        return None

    return shutil.which("tesseract")


def resolve_tesseract_language(
    tesseract_cmd: str,
    requested_language: str,
) -> tuple[Optional[str], str]:
    try:
        process = subprocess.run(
            [tesseract_cmd, "--list-langs"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return None, str(error)

    available = {
        line.strip()
        for line in process.stdout.splitlines()
        if line.strip()
        and "available languages" not in line.lower()
    }

    aliases = {
        "chi_tra": ("chi_tra", "HanT"),
        "chi_sim": ("chi_sim", "HanS"),
        "eng": ("eng", "Latin"),
        "HanT": ("HanT", "chi_tra"),
        "HanS": ("HanS", "chi_sim"),
        "Latin": ("Latin", "eng"),
    }

    resolved: list[str] = []
    missing: list[str] = []

    for requested in (
        item.strip()
        for item in requested_language.split("+")
        if item.strip()
    ):
        candidates = aliases.get(requested, (requested,))
        selected = next(
            (candidate for candidate in candidates if candidate in available),
            None,
        )

        if selected is None:
            missing.append(requested)
        else:
            resolved.append(selected)

    if missing:
        return (
            None,
            "Tesseract 缺少语言数据：" + ", ".join(missing),
        )

    return "+".join(resolved), ""


def ocr_page_with_tesseract(
    page: fitz.Page,
    tesseract_cmd: str,
    language: str,
    dpi: int,
    psm: int,
    timeout_seconds: int,
    temporary_dir: Path,
) -> str:
    scale = dpi / 72.0
    pixmap = page.get_pixmap(
        matrix=fitz.Matrix(scale, scale),
        alpha=False,
        colorspace=fitz.csGRAY,
    )

    image_path = (
        temporary_dir
        / f"page_{page.number + 1:04d}.png"
    )
    pixmap.save(str(image_path))

    command = [
        tesseract_cmd,
        str(image_path),
        "stdout",
        "-l",
        language,
        "--psm",
        str(psm),
        "--dpi",
        str(dpi),
        "-c",
        "preserve_interword_spaces=1",
    ]

    process = subprocess.run(
        command,
        check=False,
        capture_output=True,
        timeout=timeout_seconds,
    )

    stdout = process.stdout.decode(
        "utf-8",
        errors="replace",
    )
    stderr = process.stderr.decode(
        "utf-8",
        errors="replace",
    )

    image_path.unlink(missing_ok=True)

    if process.returncode != 0:
        raise RuntimeError(
            "Tesseract OCR 失败："
            + (stderr.strip() or f"exit={process.returncode}")
        )

    return stdout


def extract_native_page_text(page: fitz.Page) -> str:
    """
    sort=True 对多数 HKCMMS 页面可提供较合理阅读顺序。
    """
    return page.get_text(
        "text",
        sort=True,
    )


def parse_field(
    text: str,
    field_names: Sequence[str],
) -> str:
    for field_name in field_names:
        pattern = re.compile(
            rf"{re.escape(field_name)}\s*[：:]\s*([^\n]+)",
            flags=re.IGNORECASE,
        )
        match = pattern.search(text)

        if match:
            value = match.group(1).strip()
            value = re.split(
                r"\s+(?=\d+[.．]\s*)",
                value,
                maxsplit=1,
            )[0]
            return value.strip(" ;；")

    return ""


def infer_document_metadata(
    clean_text: str,
    source: SourcePdf,
) -> dict[str, Any]:
    official_name = parse_field(
        clean_text,
        ["藥材正名", "药材正名"],
    )
    chinese_name = parse_field(
        clean_text,
        ["中文名"],
    )
    pinyin_name = parse_field(
        clean_text,
        ["漢語拼音名", "汉语拼音名", "漢語拼音", "汉语拼音"],
    )

    title = (
        chinese_name
        or source.title_hint
        or official_name
        or Path(source.relative_path).stem
    )

    return {
        "title": title,
        "official_name": official_name,
        "chinese_name": chinese_name,
        "pinyin_name": pinyin_name,
    }


def detect_section_heading(
    line: str,
) -> Optional[tuple[str, str, str]]:
    stripped = line.strip()

    match = SUBHEADING_RE.match(stripped)

    if not match:
        match = MAIN_HEADING_RE.match(stripped)

    if match:
        number = match.group(1).strip()
        number = number.replace("．", ".")
        number = re.sub(r"(?<=\.)[lI](?=\.|$)", "1", number)
        title = match.group(2).strip(" .．")

        # 图例常写成“1. 木栓层 2. 韧皮部 ...”，不应当作章节。
        if (
            not title
            or len(re.findall(r"\b\d+[.．]", title)) >= 1
            or re.match(r"^(?:cm|mm|µm|mL|mg|g|%)(?:\s|$)", title)
        ):
            return None

        section_type = semantic_section_type(title)
        return number, title, section_type

    if PART_HEADING_RE.match(stripped):
        return "", stripped, "part"

    normalized = re.sub(r"\s+", "", stripped)

    if normalized in KNOWN_SHORT_HEADINGS:
        return "", normalized, semantic_section_type(
            normalized
        )

    return None


def semantic_section_type(title: str) -> str:
    normalized = re.sub(r"\s+", "", title)

    for alias, section_type in SEMANTIC_SECTION_ALIASES.items():
        if alias in normalized:
            return section_type

    if "顯微" in normalized or "显微" in normalized:
        return "microscopy"

    if "薄層" in normalized or "薄层" in normalized:
        return "tlc"

    if "色譜" in normalized or "色谱" in normalized:
        return "chromatography"

    if normalized in {"橫切面", "横切面"}:
        return "cross_section"

    if normalized == "粉末":
        return "powder"

    return "subsection"


def build_sections(
    document_id: str,
    pages: list[PageResult],
) -> list[SectionResult]:
    units: list[tuple[int, str]] = []

    for page in pages:
        for line in page.clean_text.splitlines():
            normalized = normalize_line(line)
            if normalized:
                units.append(
                    (page.page_number, normalized)
                )

    if not units:
        return []

    sections: list[SectionResult] = []
    current_number = ""
    current_title = "文档正文"
    current_type = "document"
    current_page_start = units[0][0]
    current_page_end = units[0][0]
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines

        text = lines_to_clean_text(current_lines).strip()

        if not text:
            current_lines = []
            return

        index = len(sections) + 1
        section_id = (
            f"{document_id}_s{index:03d}"
        )

        sections.append(
            SectionResult(
                section_id=section_id,
                document_id=document_id,
                section_number=current_number,
                section_title=current_title,
                section_type=current_type,
                page_start=current_page_start,
                page_end=current_page_end,
                text=text,
            )
        )
        current_lines = []

    for page_number, line in units:
        heading = detect_section_heading(line)

        if heading:
            flush()

            current_number, current_title, current_type = heading
            current_page_start = page_number
            current_page_end = page_number
            current_lines = [line]
            continue

        current_page_end = page_number
        current_lines.append(line)

    flush()
    return sections


def split_sentences(text: str) -> list[str]:
    text = text.strip()

    if not text:
        return []

    pieces = re.split(
        r"(?<=[。！？；.!?;])\s*|\n+",
        text,
    )

    return [
        piece.strip()
        for piece in pieces
        if piece and piece.strip()
    ]


def hard_split_text(
    text: str,
    maximum: int,
    overlap: int,
) -> list[str]:
    if len(text) <= maximum:
        return [text]

    result: list[str] = []
    start = 0

    while start < len(text):
        end = min(len(text), start + maximum)

        if end < len(text):
            candidates = [
                text.rfind(char, start, end)
                for char in "。；！？,.，"
            ]
            best = max(candidates)

            if best > start + maximum // 2:
                end = best + 1

        piece = text[start:end].strip()

        if piece:
            result.append(piece)

        if end >= len(text):
            break

        start = max(start + 1, end - overlap)

    return result


def chunk_section_text(
    text: str,
    chunk_size: int,
    overlap: int,
) -> list[str]:
    sentences = split_sentences(text)

    if not sentences:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for sentence in sentences:
        if len(sentence) > chunk_size:
            if current:
                chunks.append("".join(current).strip())
                current = []
                current_length = 0

            chunks.extend(
                hard_split_text(
                    sentence,
                    maximum=chunk_size,
                    overlap=overlap,
                )
            )
            continue

        if (
            current
            and current_length + len(sentence) > chunk_size
        ):
            completed = "".join(current).strip()

            if completed:
                chunks.append(completed)

            overlap_sentences: list[str] = []
            overlap_length = 0

            for previous in reversed(current):
                if (
                    overlap_length + len(previous) > overlap
                    and overlap_sentences
                ):
                    break

                overlap_sentences.insert(0, previous)
                overlap_length += len(previous)

                if overlap_length >= overlap:
                    break

            current = overlap_sentences
            current_length = sum(
                len(item) for item in current
            )

        current.append(sentence)
        current_length += len(sentence)

    if current:
        completed = "".join(current).strip()

        if completed:
            chunks.append(completed)

    # 去除完全相同的相邻块。
    deduplicated: list[str] = []

    for chunk in chunks:
        if not deduplicated or chunk != deduplicated[-1]:
            deduplicated.append(chunk)

    return deduplicated


def extract_appendix_references(text: str) -> list[str]:
    return sorted(
        {
            re.sub(r"\s+", "", match)
            for match in APPENDIX_REF_RE.findall(text)
        }
    )


def extract_latin_species(text: str) -> list[str]:
    candidates = {
        f"{genus} {species}"
        for genus, species in LATIN_BINOMIAL_RE.findall(text)
    }

    excluded_second_words = {
        "Radix",
        "Rhizoma",
        "Herba",
        "Flos",
        "Fructus",
        "Semen",
        "Cortex",
        "Caulis",
        "Folium",
    }

    return sorted(
        candidate
        for candidate in candidates
        if candidate.split()[1] not in excluded_second_words
    )


def estimate_chunk_pages(
    section: SectionResult,
    chunk_index: int,
    chunk_count: int,
) -> tuple[int, int]:
    if chunk_count <= 1:
        return section.page_start, section.page_end

    page_span = max(
        1,
        section.page_end - section.page_start + 1,
    )
    start_ratio = chunk_index / chunk_count
    end_ratio = (chunk_index + 1) / chunk_count

    page_start = section.page_start + min(
        page_span - 1,
        int(start_ratio * page_span),
    )
    page_end = section.page_start + min(
        page_span - 1,
        max(
            int(math.ceil(end_ratio * page_span)) - 1,
            0,
        ),
    )

    return page_start, max(page_start, page_end)


def build_chunks(
    document_id: str,
    source: SourcePdf,
    metadata: dict[str, Any],
    sections: list[SectionResult],
    chunk_size: int,
    chunk_overlap: int,
) -> list[ChunkResult]:
    chunks: list[ChunkResult] = []

    for section in sections:
        texts = chunk_section_text(
            section.text,
            chunk_size=chunk_size,
            overlap=chunk_overlap,
        )

        for local_index, text in enumerate(texts):
            page_start, page_end = estimate_chunk_pages(
                section,
                chunk_index=local_index,
                chunk_count=len(texts),
            )

            chunk_id = (
                f"{document_id}_c{len(chunks) + 1:04d}"
            )
            title = str(metadata["title"])
            citation = build_citation(
                title=title,
                volume=source.volume,
                page_start=page_start,
                page_end=page_end,
            )

            chunks.append(
                ChunkResult(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    volume=source.volume,
                    language=source.language,
                    category=source.category,
                    title=title,
                    official_name=str(
                        metadata["official_name"]
                    ),
                    chinese_name=str(
                        metadata["chinese_name"]
                    ),
                    pinyin_name=str(
                        metadata["pinyin_name"]
                    ),
                    section_id=section.section_id,
                    section_number=section.section_number,
                    section_title=section.section_title,
                    section_type=section.section_type,
                    page_start=page_start,
                    page_end=page_end,
                    text=text,
                    char_count=len(text),
                    source_file=source.relative_path,
                    source_url=source.source_url,
                    citation=citation,
                    appendix_references=(
                        extract_appendix_references(text)
                    ),
                    latin_species=extract_latin_species(text),
                )
            )

    return chunks


def build_citation(
    title: str,
    volume: Optional[int],
    page_start: int,
    page_end: int,
) -> str:
    volume_label = (
        f"第{volume}册"
        if volume is not None
        else "卷册未知"
    )
    page_label = (
        f"第{page_start}页"
        if page_start == page_end
        else f"第{page_start}-{page_end}页"
    )

    return f"HKCMMS {volume_label}《{title}》{page_label}"


def processing_config_hash(args: argparse.Namespace) -> str:
    relevant = {
        "script_version": SCRIPT_VERSION,
        "ocr": args.ocr,
        "ocr_language": args.ocr_language,
        "ocr_dpi": args.ocr_dpi,
        "ocr_psm": args.ocr_psm,
        "ocr_timeout": args.ocr_timeout,
        "ocr_min_native_chars": args.ocr_min_native_chars,
        "native_quality_threshold": (
            args.native_quality_threshold
        ),
        "chunk_size": args.chunk_size,
        "chunk_overlap": args.chunk_overlap,
    }

    return sha256_bytes(
        json_dumps(relevant).encode("utf-8")
    )


def process_document(
    source: SourcePdf,
    pdf_bytes: bytes,
    args: argparse.Namespace,
    tesseract_cmd: Optional[str],
    config_hash: str,
    cache_dir: Path,
    text_dir: Path,
) -> dict[str, Any]:
    source_sha256 = sha256_bytes(pdf_bytes)
    document_id = stable_id(
        "hkcmms",
        source.relative_path.lower(),
        length=20,
    )
    cache_path = cache_dir / f"{document_id}.json"

    if (
        cache_path.exists()
        and not args.force
    ):
        try:
            cached = read_json(cache_path)

            if (
                cached.get("source_sha256") == source_sha256
                and cached.get("config_hash") == config_hash
            ):
                print(
                    f"[CACHE] {source.relative_path}"
                )
                return cached
        except Exception:
            pass

    started_at = time.time()
    errors: list[dict[str, Any]] = []
    pages: list[PageResult] = []

    with fitz.open(
        stream=pdf_bytes,
        filetype="pdf",
    ) as document:
        page_count = document.page_count
        native_raw_texts: list[str] = []
        native_lines: list[list[str]] = []

        for page in document:
            raw_text = extract_native_page_text(page)
            native_raw_texts.append(raw_text)
            native_lines.append(split_raw_lines(raw_text))

        repeated_margin_lines = (
            identify_repeated_margin_lines(native_lines)
        )

        with tempfile.TemporaryDirectory(
            prefix="hkcmms_ocr_"
        ) as temp_name:
            temp_dir = Path(temp_name)

            for page_index, page in enumerate(document):
                native_raw = native_raw_texts[page_index]
                native_quality = native_text_quality(
                    native_raw
                )
                use_ocr = False

                native_nonspace_chars = len(
                    re.sub(r"\s+", "", normalize_unicode(native_raw))
                )

                if args.ocr == "always":
                    use_ocr = True
                elif (
                    args.ocr == "auto"
                    and native_quality
                    < args.native_quality_threshold
                    and native_nonspace_chars
                    >= args.ocr_min_native_chars
                ):
                    use_ocr = True

                final_raw = native_raw
                method = (
                    "native_sparse"
                    if (
                        args.ocr == "auto"
                        and native_quality < args.native_quality_threshold
                        and native_nonspace_chars
                        < args.ocr_min_native_chars
                    )
                    else "native"
                )
                needs_ocr = (
                    native_quality
                    < args.native_quality_threshold
                    and native_nonspace_chars
                    >= args.ocr_min_native_chars
                )

                if use_ocr:
                    if tesseract_cmd is None:
                        errors.append(
                            {
                                "type": "ocr_unavailable",
                                "document_id": document_id,
                                "source_file": (
                                    source.relative_path
                                ),
                                "page_number": page_index + 1,
                                "message": (
                                    "该页原生文本质量低，但未找到 "
                                    "Tesseract OCR。"
                                ),
                            }
                        )
                        method = "native_low_quality"
                    else:
                        try:
                            final_raw = (
                                ocr_page_with_tesseract(
                                    page=page,
                                    tesseract_cmd=(
                                        tesseract_cmd
                                    ),
                                    language=(
                                        args.ocr_language
                                    ),
                                    dpi=args.ocr_dpi,
                                    psm=args.ocr_psm,
                                    timeout_seconds=(
                                        args.ocr_timeout
                                    ),
                                    temporary_dir=temp_dir,
                                )
                            )
                            method = "tesseract_ocr"
                        except Exception as error:
                            errors.append(
                                {
                                    "type": "ocr_error",
                                    "document_id": document_id,
                                    "source_file": (
                                        source.relative_path
                                    ),
                                    "page_number": (
                                        page_index + 1
                                    ),
                                    "message": str(error),
                                }
                            )
                            final_raw = native_raw
                            method = "native_ocr_failed"

                final_lines = split_raw_lines(final_raw)
                cleaned_lines = clean_page_lines(
                    final_lines,
                    repeated_margin_lines=(
                        repeated_margin_lines
                        if method == "native"
                        else set()
                    ),
                )
                clean_text = lines_to_clean_text(
                    cleaned_lines
                )
                final_quality = native_text_quality(
                    clean_text
                )

                pages.append(
                    PageResult(
                        page_number=page_index + 1,
                        extraction_method=method,
                        native_quality=round(
                            native_quality,
                            4,
                        ),
                        final_quality=round(
                            final_quality,
                            4,
                        ),
                        needs_ocr=needs_ocr,
                        char_count=len(clean_text),
                        raw_text=final_raw,
                        clean_text=clean_text,
                    )
                )

    clean_text = "\n\n".join(
        page.clean_text
        for page in pages
        if page.clean_text
    ).strip()

    metadata = infer_document_metadata(
        clean_text,
        source,
    )
    sections = build_sections(
        document_id=document_id,
        pages=pages,
    )
    chunks = build_chunks(
        document_id=document_id,
        source=source,
        metadata=metadata,
        sections=sections,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    ocr_pages = sum(
        page.extraction_method == "tesseract_ocr"
        for page in pages
    )
    low_quality_pages = sum(
        page.final_quality
        < args.native_quality_threshold
        for page in pages
    )
    avg_quality = (
        sum(page.final_quality for page in pages)
        / max(len(pages), 1)
    )

    document_row = {
        "document_id": document_id,
        "volume": source.volume,
        "language": source.language,
        "category": source.category,
        "title": metadata["title"],
        "official_name": metadata["official_name"],
        "chinese_name": metadata["chinese_name"],
        "pinyin_name": metadata["pinyin_name"],
        "source_file": source.relative_path,
        "source_display_path": source.display_path,
        "source_url": source.source_url,
        "source_sha256": source_sha256,
        "page_count": len(pages),
        "section_count": len(sections),
        "chunk_count": len(chunks),
        "ocr_page_count": ocr_pages,
        "low_quality_page_count": low_quality_pages,
        "average_quality": round(avg_quality, 4),
        "clean_char_count": len(clean_text),
        "clean_text": clean_text,
    }

    text_path = text_dir / f"{document_id}.txt"
    text_path.parent.mkdir(parents=True, exist_ok=True)

    text_header = [
        f"标题：{metadata['title']}",
        f"药材正名：{metadata['official_name']}",
        f"中文名：{metadata['chinese_name']}",
        f"汉语拼音名：{metadata['pinyin_name']}",
        f"卷册：{source.volume or ''}",
        f"来源文件：{source.relative_path}",
        f"来源网址：{source.source_url}",
        "",
    ]
    text_path.write_text(
        "\n".join(text_header) + clean_text,
        encoding="utf-8",
    )

    elapsed = time.time() - started_at

    result = {
        "source_sha256": source_sha256,
        "config_hash": config_hash,
        "document": document_row,
        "pages": [
            {
                **asdict(page),
                "document_id": document_id,
                "source_file": source.relative_path,
            }
            for page in pages
        ],
        "sections": [
            asdict(section)
            for section in sections
        ],
        "chunks": [
            asdict(chunk)
            for chunk in chunks
        ],
        "errors": errors,
        "report": {
            "document_id": document_id,
            "volume": source.volume,
            "source_file": source.relative_path,
            "title": metadata["title"],
            "official_name": metadata["official_name"],
            "chinese_name": metadata["chinese_name"],
            "page_count": len(pages),
            "ocr_page_count": ocr_pages,
            "low_quality_page_count": low_quality_pages,
            "average_quality": round(
                avg_quality,
                4,
            ),
            "clean_char_count": len(clean_text),
            "section_count": len(sections),
            "chunk_count": len(chunks),
            "error_count": len(errors),
            "elapsed_seconds": round(elapsed, 2),
            "status": (
                "ok"
                if not errors and low_quality_pages == 0
                else (
                    "warning"
                    if clean_text
                    else "failed"
                )
            ),
        },
    }

    cache_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    cache_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return result


def merge_results(
    results: list[dict[str, Any]],
    output_dir: Path,
) -> None:
    documents: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []

    for result in results:
        documents.append(result["document"])
        pages.extend(result["pages"])
        sections.extend(result["sections"])
        chunks.extend(result["chunks"])
        errors.extend(result["errors"])
        reports.append(result["report"])

    documents.sort(
        key=lambda row: (
            row.get("volume") or 999,
            row.get("source_file") or "",
        )
    )
    pages.sort(
        key=lambda row: (
            row.get("document_id") or "",
            row.get("page_number") or 0,
        )
    )
    sections.sort(
        key=lambda row: row.get("section_id") or ""
    )
    chunks.sort(
        key=lambda row: row.get("chunk_id") or ""
    )
    reports.sort(
        key=lambda row: (
            row.get("volume") or 999,
            row.get("source_file") or "",
        )
    )

    write_jsonl(
        output_dir / "documents.jsonl",
        documents,
    )
    write_jsonl(
        output_dir / "pages.jsonl",
        pages,
    )
    write_jsonl(
        output_dir / "sections.jsonl",
        sections,
    )
    write_jsonl(
        output_dir / "chunks.jsonl",
        chunks,
    )
    write_jsonl(
        output_dir / "errors.jsonl",
        errors,
    )

    report_path = (
        output_dir / "processing_report.csv"
    )
    report_fields = [
        "document_id",
        "volume",
        "source_file",
        "title",
        "official_name",
        "chinese_name",
        "page_count",
        "ocr_page_count",
        "low_quality_page_count",
        "average_quality",
        "clean_char_count",
        "section_count",
        "chunk_count",
        "error_count",
        "elapsed_seconds",
        "status",
    ]

    with report_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=report_fields,
        )
        writer.writeheader()
        writer.writerows(reports)

    dataset_info = {
        "script_version": SCRIPT_VERSION,
        "created_at": time.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "document_count": len(documents),
        "page_count": len(pages),
        "section_count": len(sections),
        "chunk_count": len(chunks),
        "error_count": len(errors),
        "volumes": sorted(
            {
                document["volume"]
                for document in documents
                if document.get("volume") is not None
            }
        ),
        "output_files": {
            "documents": "documents.jsonl",
            "pages": "pages.jsonl",
            "sections": "sections.jsonl",
            "chunks": "chunks.jsonl",
            "report": "processing_report.csv",
            "errors": "errors.jsonl",
            "text_directory": "text/",
        },
    }

    (
        output_dir / "dataset_info.json"
    ).write_text(
        json.dumps(
            dataset_info,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract, clean, OCR and chunk HKCMMS PDFs "
            "for GraphRAG."
        )
    )

    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="PDF、PDF目录或精选 ZIP 数据包。",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/pharmacopoeia/processed/hkcmms"
        ),
        help=(
            "输出目录。默认："
            "data/pharmacopoeia/processed/hkcmms"
        ),
    )

    parser.add_argument(
        "--ocr",
        choices=["auto", "never", "always"],
        default="auto",
        help=(
            "auto：仅低质量页 OCR；"
            "never：禁用 OCR；"
            "always：所有页面 OCR。默认 auto。"
        ),
    )

    parser.add_argument(
        "--tesseract-cmd",
        default=None,
        help=(
            "Tesseract 可执行文件路径。"
            "未指定时从 PATH 自动查找。"
        ),
    )

    parser.add_argument(
        "--ocr-language",
        default=DEFAULT_OCR_LANG,
        help=(
            "Tesseract 语言组合。"
            f"默认：{DEFAULT_OCR_LANG}"
        ),
    )

    parser.add_argument(
        "--ocr-dpi",
        type=int,
        default=DEFAULT_OCR_DPI,
        help=f"OCR 渲染 DPI。默认：{DEFAULT_OCR_DPI}",
    )

    parser.add_argument(
        "--ocr-psm",
        type=int,
        default=6,
        help="Tesseract 页面分割模式。默认：6。",
    )

    parser.add_argument(
        "--ocr-timeout",
        type=int,
        default=DEFAULT_OCR_TIMEOUT,
        help=(
            "单页 OCR 最大秒数，超时后保留原生文本并记录警告。"
            f"默认：{DEFAULT_OCR_TIMEOUT}。"
        ),
    )

    parser.add_argument(
        "--ocr-min-native-chars",
        type=int,
        default=DEFAULT_OCR_MIN_NATIVE_CHARS,
        help=(
            "auto 模式下，低质量页原生字符数达到该值才 OCR；"
            "较短的图片页会跳过，减少耗时。"
            f"默认：{DEFAULT_OCR_MIN_NATIVE_CHARS}。"
        ),
    )

    parser.add_argument(
        "--native-quality-threshold",
        type=float,
        default=DEFAULT_NATIVE_QUALITY_THRESHOLD,
        help=(
            "原生文本质量低于该值时触发 OCR。"
            f"默认：{DEFAULT_NATIVE_QUALITY_THRESHOLD}"
        ),
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=(
            f"目标文本块字符数。默认：{DEFAULT_CHUNK_SIZE}"
        ),
    )

    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=DEFAULT_CHUNK_OVERLAP,
        help=(
            f"相邻文本块重叠字符数。默认："
            f"{DEFAULT_CHUNK_OVERLAP}"
        ),
    )

    parser.add_argument(
        "--volumes",
        type=int,
        nargs="*",
        default=None,
        help="只处理指定卷，例如：--volumes 1 2 3",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="仅处理前 N 份 PDF，用于调试。",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="忽略缓存，强制重新处理。",
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not args.input.exists():
        raise FileNotFoundError(
            f"输入路径不存在：{args.input}"
        )

    if args.chunk_size < 200:
        raise ValueError(
            "--chunk-size 不能小于 200"
        )

    if (
        args.chunk_overlap < 0
        or args.chunk_overlap >= args.chunk_size
    ):
        raise ValueError(
            "--chunk-overlap 必须大于等于 0，"
            "且小于 --chunk-size"
        )

    if not 0 <= args.native_quality_threshold <= 1:
        raise ValueError(
            "--native-quality-threshold 必须在 0～1"
        )

    if args.ocr_dpi < 100 or args.ocr_dpi > 600:
        raise ValueError(
            "--ocr-dpi 建议范围为 100～600"
        )

    if args.ocr_timeout < 5:
        raise ValueError(
            "--ocr-timeout 不能小于 5 秒"
        )

    if args.ocr_min_native_chars < 0:
        raise ValueError(
            "--ocr-min-native-chars 不能小于 0"
        )


def print_summary(
    results: list[dict[str, Any]],
    output_dir: Path,
) -> None:
    documents = [
        result["document"]
        for result in results
    ]
    reports = [
        result["report"]
        for result in results
    ]

    total_pages = sum(
        row["page_count"] for row in reports
    )
    total_ocr_pages = sum(
        row["ocr_page_count"] for row in reports
    )
    total_sections = sum(
        row["section_count"] for row in reports
    )
    total_chunks = sum(
        row["chunk_count"] for row in reports
    )
    total_errors = sum(
        row["error_count"] for row in reports
    )
    low_quality_pages = sum(
        row["low_quality_page_count"]
        for row in reports
    )

    print()
    print("=" * 76)
    print("[FINAL SUMMARY]")
    print("=" * 76)
    print(f"Documents          : {len(documents)}")
    print(f"Pages              : {total_pages}")
    print(f"OCR pages          : {total_ocr_pages}")
    print(f"Low-quality pages  : {low_quality_pages}")
    print(f"Sections           : {total_sections}")
    print(f"Chunks             : {total_chunks}")
    print(f"Errors/warnings    : {total_errors}")
    print(f"Output             : {output_dir.resolve()}")
    print()
    print("GraphRAG 主要入库文件：")
    print(f"  {output_dir / 'chunks.jsonl'}")
    print("质量报告：")
    print(f"  {output_dir / 'processing_report.csv'}")

    if total_errors or low_quality_pages:
        print()
        print(
            "[WARN] 存在警告或低质量页面，请检查："
        )
        print(f"  {output_dir / 'errors.jsonl'}")
        print(
            f"  {output_dir / 'processing_report.csv'}"
        )
    else:
        print()
        print(
            "[DONE] 所有文档均已完成清洗、章节识别和分块。"
        )


def main() -> int:
    args = parse_args()

    try:
        validate_args(args)
    except (FileNotFoundError, ValueError) as error:
        print(f"[ERROR] {error}")
        return 2

    input_path = args.input.resolve()
    output_dir = args.output.resolve()
    cache_dir = output_dir / "cache"
    text_dir = output_dir / "text"

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    cache_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    text_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        sources = build_source_list(input_path)
    except Exception as error:
        print(f"[ERROR] 无法读取输入数据：{error}")
        return 2

    if args.volumes:
        selected_volumes = set(args.volumes)
        sources = [
            source
            for source in sources
            if source.volume in selected_volumes
        ]

    sources = sorted(
        sources,
        key=lambda source: (
            source.volume or 999,
            source.relative_path.lower(),
        ),
    )

    if args.limit is not None:
        sources = sources[: max(args.limit, 0)]

    if not sources:
        print("[ERROR] 没有找到符合条件的 PDF")
        return 2

    tesseract_cmd: Optional[str] = None

    if args.ocr != "never":
        tesseract_cmd = resolve_tesseract_command(
            args.tesseract_cmd
        )

        if tesseract_cmd:
            resolved_language, message = (
                resolve_tesseract_language(
                    tesseract_cmd,
                    args.ocr_language,
                )
            )

            if resolved_language is None:
                print(f"[WARN] {message}")
                print(
                    "[WARN] 低质量页将无法 OCR，"
                    "但脚本仍会生成质量报告。"
                )
                tesseract_cmd = None
            else:
                args.ocr_language = resolved_language
                print(
                    f"[INFO] Tesseract: {tesseract_cmd}"
                )
                print(
                    f"[INFO] OCR language: "
                    f"{args.ocr_language}"
                )
        else:
            print(
                "[WARN] 未找到 Tesseract。"
                "PDF 原生文本正常的页面仍可处理；"
                "乱码页会写入 errors.jsonl。"
            )

    print(f"[INFO] Script version : {SCRIPT_VERSION}")
    print(f"[INFO] Input          : {input_path}")
    print(f"[INFO] Output         : {output_dir}")
    print(f"[INFO] PDF count      : {len(sources)}")
    print(f"[INFO] OCR mode       : {args.ocr}")
    print(f"[INFO] Chunk size     : {args.chunk_size}")
    print(f"[INFO] Chunk overlap  : {args.chunk_overlap}")

    config_hash = processing_config_hash(args)
    results: list[dict[str, Any]] = []

    with SourceReader(input_path) as reader:
        for index, source in enumerate(
            sources,
            start=1,
        ):
            print()
            print(
                f"[DOC] {index}/{len(sources)} "
                f"{source.relative_path}"
            )

            try:
                pdf_bytes = reader.read_bytes(source)

                if not pdf_bytes.startswith(b"%PDF-"):
                    raise ValueError(
                        "文件头不是 %PDF-"
                    )

                result = process_document(
                    source=source,
                    pdf_bytes=pdf_bytes,
                    args=args,
                    tesseract_cmd=tesseract_cmd,
                    config_hash=config_hash,
                    cache_dir=cache_dir,
                    text_dir=text_dir,
                )
                results.append(result)

                report = result["report"]
                print(
                    "[OK] "
                    f"title={report['title']!r}, "
                    f"pages={report['page_count']}, "
                    f"ocr={report['ocr_page_count']}, "
                    f"sections={report['section_count']}, "
                    f"chunks={report['chunk_count']}, "
                    f"quality={report['average_quality']}"
                )

            except Exception as error:
                document_id = stable_id(
                    "hkcmms",
                    source.relative_path.lower(),
                    length=20,
                )
                print(
                    f"[FAILED] {source.relative_path}: "
                    f"{error}"
                )

                results.append(
                    {
                        "source_sha256": "",
                        "config_hash": config_hash,
                        "document": {
                            "document_id": document_id,
                            "volume": source.volume,
                            "language": source.language,
                            "category": source.category,
                            "title": source.title_hint,
                            "official_name": "",
                            "chinese_name": "",
                            "pinyin_name": "",
                            "source_file": source.relative_path,
                            "source_display_path": (
                                source.display_path
                            ),
                            "source_url": source.source_url,
                            "source_sha256": "",
                            "page_count": 0,
                            "section_count": 0,
                            "chunk_count": 0,
                            "ocr_page_count": 0,
                            "low_quality_page_count": 0,
                            "average_quality": 0.0,
                            "clean_char_count": 0,
                            "clean_text": "",
                        },
                        "pages": [],
                        "sections": [],
                        "chunks": [],
                        "errors": [
                            {
                                "type": "document_error",
                                "document_id": document_id,
                                "source_file": (
                                    source.relative_path
                                ),
                                "page_number": None,
                                "message": str(error),
                            }
                        ],
                        "report": {
                            "document_id": document_id,
                            "volume": source.volume,
                            "source_file": (
                                source.relative_path
                            ),
                            "title": source.title_hint,
                            "official_name": "",
                            "chinese_name": "",
                            "page_count": 0,
                            "ocr_page_count": 0,
                            "low_quality_page_count": 0,
                            "average_quality": 0.0,
                            "clean_char_count": 0,
                            "section_count": 0,
                            "chunk_count": 0,
                            "error_count": 1,
                            "elapsed_seconds": 0.0,
                            "status": "failed",
                        },
                    }
                )

    merge_results(
        results=results,
        output_dir=output_dir,
    )
    print_summary(
        results=results,
        output_dir=output_dir,
    )

    has_failed_document = any(
        result["report"]["status"] == "failed"
        for result in results
    )

    return 1 if has_failed_document else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print()
        print(
            "[INTERRUPTED] 已生成的文档缓存会保留，"
            "重新执行相同命令可继续。"
        )
        raise SystemExit(130)
