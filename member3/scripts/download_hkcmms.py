#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HKCMMS 下载器（GraphRAG 精简版）

适用项目：
    基于知识图谱的中医药诊疗智能体
    成员 3：GraphRAG

默认策略：
    1. 扫描并保留 HKCMMS 全量 PDF manifest；
    2. 默认只选择中文 monograph（药材专论）；
    3. 每卷均匀抽取 3 篇，通常约 33 篇；
    4. 支持断点续传、失败重试、文件校验；
    5. 不会默认下载全部 1162 个 PDF。

依赖：
    pip install requests

常用命令：

    # 推荐：默认下载每卷 3 篇中文药材专论，约 33 篇
    python scripts/download_hkcmms.py

    # 每卷下载 5 篇，约 55 篇
    python scripts/download_hkcmms.py --sample-per-volume 5

    # 只生成完整 manifest 和精简 selected manifest，不下载
    python scripts/download_hkcmms.py --manifest-only

    # 下载全部中文药材专论
    python scripts/download_hkcmms.py --mode zh-monographs

    # 根据药材关键词下载
    python scripts/download_hkcmms.py \
        --mode keywords \
        --keywords-file config/hkcmms_keywords.txt

    # 下载 manifest 中的全部文件（通常不建议）
    python scripts/download_hkcmms.py --mode all

    # 强制重新扫描官网，不使用已有 manifest
    python scripts/download_hkcmms.py --refresh-manifest

说明：
    - 已存在且有效的 PDF 自动跳过；
    - 下载中的文件保存为 .pdf.part；
    - 中断后重新运行相同命令即可续传；
    - 完整 manifest 与精简 selected manifest 分开保存。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import re
import sys
import time
from collections import Counter, deque
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import unquote, urldefrag, urljoin, urlsplit, urlunsplit

import requests


# =============================================================================
# 基础配置
# =============================================================================

SITE_ORIGIN = "https://www.cmro.gov.hk"
HKCMMS_BASE = f"{SITE_ORIGIN}/files/hkcmms"
DEFAULT_VOLUMES = tuple(range(1, 12))

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "data" / "pharmacopoeia" / "raw" / "hkcmms"
)

FULL_MANIFEST_CSV = "hkcmms_pdf_manifest.csv"
FULL_MANIFEST_JSON = "hkcmms_pdf_manifest.json"
FULL_MANIFEST_TXT = "hkcmms_pdf_manifest.txt"

SELECTED_MANIFEST_CSV = "hkcmms_selected_manifest.csv"
SELECTED_MANIFEST_JSON = "hkcmms_selected_manifest.json"
SELECTED_MANIFEST_TXT = "hkcmms_selected_manifest.txt"

FAILED_PAGES_TXT = "hkcmms_failed_pages.txt"
FAILED_DOWNLOADS_TXT = "hkcmms_failed_downloads.txt"
MISSING_FILES_TXT = "hkcmms_missing_files.txt"
INVALID_FILES_TXT = "hkcmms_invalid_files.txt"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0 Safari/537.36"
)

CONNECT_TIMEOUT = 25
PAGE_READ_TIMEOUT = 90
DOWNLOAD_READ_TIMEOUT = 240

PAGE_MAX_RETRIES = 8
DOWNLOAD_MAX_RETRIES = 10
DOWNLOAD_CHUNK_SIZE = 1024 * 1024

SCAN_DELAY_SECONDS = 0.25
DOWNLOAD_DELAY_SECONDS = 0.35
MAX_HTML_PAGES_PER_VOLUME = 500


# =============================================================================
# 数据结构
# =============================================================================

@dataclass(frozen=True)
class PdfRecord:
    volume: int
    language: str
    category: str
    title: str
    url: str
    relative_path: str
    discovered_from: str


# =============================================================================
# HTML 链接提取
# =============================================================================

class LinkExtractor(HTMLParser):
    """提取 <a href="..."> 的链接和可见文本。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: Optional[str] = None
        self._text_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, Optional[str]]],
    ) -> None:
        if tag.lower() != "a":
            return

        href: Optional[str] = None

        for key, value in attrs:
            if key.lower() == "href":
                href = value
                break

        if href:
            self._href = href.strip()
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._href is None:
            return

        title = " ".join("".join(self._text_parts).split())
        self.links.append((self._href, title))

        self._href = None
        self._text_parts = []


# =============================================================================
# URL、文件和校验工具
# =============================================================================

def normalize_url(url: str) -> str:
    clean_url, _fragment = urldefrag(url.strip())
    parts = urlsplit(clean_url)

    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path,
            parts.query,
            "",
        )
    )


def is_http_url(url: str) -> bool:
    return urlsplit(url).scheme.lower() in {"http", "https"}


def is_pdf_url(url: str) -> bool:
    return urlsplit(url).path.lower().endswith(".pdf")


def is_html_url(url: str) -> bool:
    path = urlsplit(url).path.lower()
    return path.endswith(".html") or path.endswith(".htm")


def is_same_volume_url(url: str, volume: int) -> bool:
    parts = urlsplit(url)

    if parts.netloc.lower() != "www.cmro.gov.hk":
        return False

    prefix = f"/files/hkcmms/vol{volume}/"
    return parts.path.lower().startswith(prefix.lower())


def safe_filename_from_url(url: str) -> str:
    name = Path(unquote(urlsplit(url).path)).name
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.rstrip(". ")

    if not name:
        digest = hashlib.sha256(
            url.encode("utf-8")
        ).hexdigest()[:16]
        name = f"document_{digest}.pdf"

    if not name.lower().endswith(".pdf"):
        name += ".pdf"

    return name


def detect_language(url: str, source_page: str = "") -> str:
    value = f"{url} {source_page}".lower()
    path = urlsplit(url).path.lower()
    filename = Path(path).name

    if "/pdf_e/" in path or filename.endswith("_e.pdf"):
        return "en"

    if (
        "/pdf_c/" in path
        or filename.endswith("_c.pdf")
        or "_b5" in value
    ):
        return "zh"

    return "other"


def detect_category(url: str, title: str = "") -> str:
    value = f"{url} {title}".lower()

    if "preface" in value:
        return "preface"

    if "general_notice" in value or "general notice" in value:
        return "general_notices"

    if "index" in value:
        return "indexes"

    if "appendix" in value or "appendices" in value:
        return "appendix"

    return "monograph"


def backoff_seconds(
    attempt: int,
    maximum: float = 60.0,
) -> float:
    return min(
        maximum,
        float(2 ** attempt) + random.uniform(0.4, 1.4),
    )


def parse_content_range_total(
    content_range: Optional[str],
) -> Optional[int]:
    if not content_range:
        return None

    match = re.search(r"/(\d+)$", content_range.strip())
    return int(match.group(1)) if match else None


def parse_content_range_start(
    content_range: Optional[str],
) -> Optional[int]:
    if not content_range:
        return None

    match = re.match(
        r"^bytes\s+(\d+)-\d+/\d+$",
        content_range.strip(),
        flags=re.IGNORECASE,
    )

    return int(match.group(1)) if match else None


def is_valid_pdf(path: Path) -> bool:
    """
    基础完整性检查：
    - 文件头为 %PDF-
    - 文件末尾 64 KiB 内存在 %%EOF
    """
    if not path.exists() or not path.is_file():
        return False

    try:
        size = path.stat().st_size

        if size < 10:
            return False

        with path.open("rb") as file:
            if file.read(5) != b"%PDF-":
                return False

            tail_size = min(size, 64 * 1024)
            file.seek(-tail_size, os.SEEK_END)
            tail = file.read(tail_size)

        return b"%%EOF" in tail

    except OSError:
        return False


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            "Connection": "close",
        }
    )
    return session


# =============================================================================
# 官网扫描
# =============================================================================

def fetch_html(
    session: requests.Session,
    url: str,
    max_retries: int = PAGE_MAX_RETRIES,
) -> Optional[str]:
    for attempt in range(1, max_retries + 1):
        try:
            print(
                f"[PAGE] attempt {attempt}/{max_retries}: {url}"
            )

            response = session.get(
                url,
                timeout=(CONNECT_TIMEOUT, PAGE_READ_TIMEOUT),
                allow_redirects=True,
                headers={
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        "application/xml;q=0.9,*/*;q=0.8"
                    ),
                    "Accept-Encoding": "identity",
                    "Connection": "close",
                },
            )

            response.raise_for_status()

            encoding = response.encoding

            if not encoding or encoding.lower() == "iso-8859-1":
                encoding = response.apparent_encoding or "utf-8"

            html = response.content.decode(
                encoding,
                errors="replace",
            )

            time.sleep(SCAN_DELAY_SECONDS)
            return html

        except requests.RequestException as error:
            print(f"[WARN] failed page {url}: {error}")

            if attempt >= max_retries:
                return None

            wait = backoff_seconds(attempt)
            print(f"[RETRY] page retry after {wait:.1f}s")
            time.sleep(wait)

    return None


def extract_links(
    html: str,
    base_url: str,
) -> list[tuple[str, str]]:
    parser = LinkExtractor()

    try:
        parser.feed(html)
    except Exception as error:
        print(f"[WARN] HTML parser warning: {error}")

    result: list[tuple[str, str]] = []

    for href, title in parser.links:
        if not href:
            continue

        if href.lower().startswith(
            ("javascript:", "mailto:", "tel:", "data:")
        ):
            continue

        absolute = normalize_url(urljoin(base_url, href))

        if is_http_url(absolute):
            result.append((absolute, title))

    return result


def build_pdf_record(
    volume: int,
    pdf_url: str,
    title: str,
    discovered_from: str,
) -> PdfRecord:
    language = detect_language(pdf_url, discovered_from)
    category = detect_category(pdf_url, title)
    filename = safe_filename_from_url(pdf_url)

    relative_path = (
        Path(f"vol{volume}") / language / filename
    ).as_posix()

    return PdfRecord(
        volume=volume,
        language=language,
        category=category,
        title=title.strip(),
        url=pdf_url,
        relative_path=relative_path,
        discovered_from=discovered_from,
    )


def crawl_volume(
    session: requests.Session,
    volume: int,
    max_pages: int,
) -> tuple[list[PdfRecord], list[str]]:
    volume_base = f"{HKCMMS_BASE}/vol{volume}/"

    seeds = [
        f"{volume_base}main.html",
        f"{volume_base}index_eng.html",
        f"{volume_base}index_b5.html",
    ]

    queue: deque[str] = deque(
        normalize_url(url) for url in seeds
    )
    queued: set[str] = set(queue)
    visited: set[str] = set()

    pdf_by_url: dict[str, PdfRecord] = {}
    failed_pages: list[str] = []

    print()
    print("=" * 78)
    print(f"[INFO] scan HKCMMS volume {volume}")
    print("=" * 78)

    while queue and len(visited) < max_pages:
        page_url = queue.popleft()
        queued.discard(page_url)

        if page_url in visited:
            continue

        visited.add(page_url)
        html = fetch_html(session, page_url)

        if html is None:
            failed_pages.append(page_url)
            continue

        for link_url, link_title in extract_links(
            html,
            page_url,
        ):
            if not is_same_volume_url(link_url, volume):
                continue

            if is_pdf_url(link_url):
                pdf_by_url.setdefault(
                    link_url,
                    build_pdf_record(
                        volume=volume,
                        pdf_url=link_url,
                        title=link_title,
                        discovered_from=page_url,
                    ),
                )
                continue

            if (
                is_html_url(link_url)
                and link_url not in visited
                and link_url not in queued
            ):
                queue.append(link_url)
                queued.add(link_url)

    if queue:
        print(
            f"[WARN] vol{volume} reached page limit "
            f"{max_pages}; unscanned pages={len(queue)}"
        )

    records = sorted(
        pdf_by_url.values(),
        key=lambda item: (
            item.language,
            item.category,
            item.relative_path.lower(),
            item.url,
        ),
    )

    print(
        f"[INFO] vol{volume}: "
        f"HTML pages={len(visited)}, "
        f"PDFs={len(records)}, "
        f"failed pages={len(failed_pages)}"
    )

    return records, failed_pages


def scan_all_volumes(
    volumes: list[int],
    max_pages_per_volume: int,
) -> tuple[list[PdfRecord], list[str]]:
    all_records: list[PdfRecord] = []
    all_failed_pages: list[str] = []

    with create_session() as session:
        for volume in volumes:
            records, failed_pages = crawl_volume(
                session=session,
                volume=volume,
                max_pages=max_pages_per_volume,
            )

            all_records.extend(records)
            all_failed_pages.extend(failed_pages)

    unique_by_url: dict[str, PdfRecord] = {}

    for record in all_records:
        unique_by_url.setdefault(record.url, record)

    records = sorted(
        unique_by_url.values(),
        key=lambda item: (
            item.volume,
            item.language,
            item.category,
            item.relative_path.lower(),
            item.url,
        ),
    )

    return resolve_path_collisions(records), all_failed_pages


def resolve_path_collisions(
    records: Iterable[PdfRecord],
) -> list[PdfRecord]:
    """
    防止不同 URL 映射到相同本地路径。
    """
    result: list[PdfRecord] = []
    path_to_url: dict[str, str] = {}

    for record in records:
        key = record.relative_path.lower()
        previous_url = path_to_url.get(key)

        if previous_url is None or previous_url == record.url:
            path_to_url[key] = record.url
            result.append(record)
            continue

        old_path = Path(record.relative_path)
        digest = hashlib.sha256(
            record.url.encode("utf-8")
        ).hexdigest()[:10]

        new_name = (
            f"{old_path.stem}__{digest}{old_path.suffix}"
        )

        updated = PdfRecord(
            volume=record.volume,
            language=record.language,
            category=record.category,
            title=record.title,
            url=record.url,
            relative_path=(
                old_path.parent / new_name
            ).as_posix(),
            discovered_from=record.discovered_from,
        )

        path_to_url[updated.relative_path.lower()] = record.url
        result.append(updated)

    return result


# =============================================================================
# Manifest 读写
# =============================================================================

MANIFEST_FIELDS = [
    "volume",
    "language",
    "category",
    "title",
    "url",
    "relative_path",
    "discovered_from",
]


def write_manifest_set(
    output_dir: Path,
    records: list[PdfRecord],
    csv_name: str,
    json_name: str,
    txt_name: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / csv_name
    json_path = output_dir / json_name
    txt_path = output_dir / txt_name

    with csv_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=MANIFEST_FIELDS,
        )
        writer.writeheader()

        for record in records:
            writer.writerow(asdict(record))

    json_path.write_text(
        json.dumps(
            [asdict(record) for record in records],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    txt_path.write_text(
        "".join(f"{record.url}\n" for record in records),
        encoding="utf-8",
    )


def write_full_manifest(
    output_dir: Path,
    records: list[PdfRecord],
) -> None:
    write_manifest_set(
        output_dir=output_dir,
        records=records,
        csv_name=FULL_MANIFEST_CSV,
        json_name=FULL_MANIFEST_JSON,
        txt_name=FULL_MANIFEST_TXT,
    )

    print(
        f"[MANIFEST] full records={len(records)}: "
        f"{output_dir / FULL_MANIFEST_CSV}"
    )


def write_selected_manifest(
    output_dir: Path,
    records: list[PdfRecord],
) -> None:
    write_manifest_set(
        output_dir=output_dir,
        records=records,
        csv_name=SELECTED_MANIFEST_CSV,
        json_name=SELECTED_MANIFEST_JSON,
        txt_name=SELECTED_MANIFEST_TXT,
    )

    print(
        f"[MANIFEST] selected records={len(records)}: "
        f"{output_dir / SELECTED_MANIFEST_CSV}"
    )


def load_manifest(csv_path: Path) -> list[PdfRecord]:
    records: list[PdfRecord] = []

    with csv_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        missing_columns = set(MANIFEST_FIELDS) - set(
            reader.fieldnames or []
        )

        if missing_columns:
            raise ValueError(
                "manifest missing columns: "
                + ", ".join(sorted(missing_columns))
            )

        for row in reader:
            records.append(
                PdfRecord(
                    volume=int(row["volume"]),
                    language=row["language"].strip(),
                    category=row["category"].strip(),
                    title=row["title"].strip(),
                    url=row["url"].strip(),
                    relative_path=row["relative_path"].strip(),
                    discovered_from=row[
                        "discovered_from"
                    ].strip(),
                )
            )

    return records


def write_lines(
    path: Path,
    values: Iterable[str],
) -> None:
    lines = sorted(
        {value.strip() for value in values if value.strip()}
    )

    if lines:
        path.write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )
    elif path.exists():
        path.unlink()


# =============================================================================
# GraphRAG 精简选择策略
# =============================================================================

def evenly_select(
    records: list[PdfRecord],
    count: int,
) -> list[PdfRecord]:
    """
    在排序后的列表中均匀选取 count 条，保证可重复。
    不使用随机抽样，避免每次运行选择不同文件。
    """
    if count <= 0 or not records:
        return []

    ordered = sorted(
        records,
        key=lambda item: (
            item.title.lower(),
            item.relative_path.lower(),
            item.url,
        ),
    )

    if count >= len(ordered):
        return ordered

    if count == 1:
        return [ordered[len(ordered) // 2]]

    indexes = [
        round(index * (len(ordered) - 1) / (count - 1))
        for index in range(count)
    ]

    # round 在个别长度组合下可能重复，进行稳定去重。
    selected_indexes: list[int] = []

    for index in indexes:
        if index not in selected_indexes:
            selected_indexes.append(index)

    cursor = 0

    while len(selected_indexes) < count:
        if cursor not in selected_indexes:
            selected_indexes.append(cursor)
        cursor += 1

    return [
        ordered[index]
        for index in sorted(selected_indexes[:count])
    ]


def load_keywords(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(
            f"keywords file does not exist: {path}"
        )

    keywords: list[str] = []

    for raw_line in path.read_text(
        encoding="utf-8-sig"
    ).splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        keywords.append(line.lower())

    if not keywords:
        raise ValueError(
            f"keywords file is empty: {path}"
        )

    return keywords


def select_records(
    records: list[PdfRecord],
    mode: str,
    sample_per_volume: int,
    keywords_file: Optional[Path],
    volumes: list[int],
) -> list[PdfRecord]:
    target_volumes = set(volumes)

    available = [
        record
        for record in records
        if record.volume in target_volumes
    ]

    if mode == "all":
        selected = available

    elif mode == "zh-monographs":
        selected = [
            record
            for record in available
            if (
                record.language == "zh"
                and record.category == "monograph"
            )
        ]

    elif mode == "sample":
        zh_monographs = [
            record
            for record in available
            if (
                record.language == "zh"
                and record.category == "monograph"
            )
        ]

        selected = []

        for volume in sorted(target_volumes):
            volume_records = [
                record
                for record in zh_monographs
                if record.volume == volume
            ]

            volume_selected = evenly_select(
                volume_records,
                sample_per_volume,
            )

            selected.extend(volume_selected)

            print(
                f"[SELECT] vol{volume}: "
                f"available={len(volume_records)}, "
                f"selected={len(volume_selected)}"
            )

    elif mode == "keywords":
        if keywords_file is None:
            raise ValueError(
                "--mode keywords requires --keywords-file"
            )

        keywords = load_keywords(keywords_file)

        candidates = [
            record
            for record in available
            if (
                record.language == "zh"
                and record.category == "monograph"
            )
        ]

        selected = []

        for record in candidates:
            searchable = " ".join(
                [
                    record.title,
                    record.url,
                    record.relative_path,
                ]
            ).lower()

            if any(
                keyword in searchable
                for keyword in keywords
            ):
                selected.append(record)

    else:
        raise ValueError(f"unsupported mode: {mode}")

    # URL 去重并稳定排序。
    unique_by_url: dict[str, PdfRecord] = {}

    for record in selected:
        unique_by_url.setdefault(record.url, record)

    return sorted(
        unique_by_url.values(),
        key=lambda item: (
            item.volume,
            item.language,
            item.category,
            item.relative_path.lower(),
        ),
    )


# =============================================================================
# 断点续传下载
# =============================================================================

def download_pdf(
    session: requests.Session,
    url: str,
    output_path: Path,
    max_retries: int,
) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    part_path = output_path.with_name(
        output_path.name + ".part"
    )

    if is_valid_pdf(output_path):
        print(
            f"[SKIP] {output_path} "
            f"({output_path.stat().st_size} bytes)"
        )
        return True

    if output_path.exists():
        try:
            size = output_path.stat().st_size
        except OSError:
            size = 0

        print(
            f"[WARN] remove invalid final file: "
            f"{output_path} ({size} bytes)"
        )

        try:
            output_path.unlink()
        except OSError as error:
            print(
                f"[FAILED] cannot remove invalid file: "
                f"{error}"
            )
            return False

    for attempt in range(1, max_retries + 1):
        try:
            local_size = (
                part_path.stat().st_size
                if part_path.exists()
                else 0
            )
        except OSError:
            local_size = 0

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": (
                "application/pdf,"
                "application/octet-stream;q=0.9,"
                "*/*;q=0.8"
            ),
            "Accept-Encoding": "identity",
            "Connection": "close",
        }

        if local_size > 0:
            headers["Range"] = f"bytes={local_size}-"

            print(
                f"[RESUME] attempt {attempt}/{max_retries}: "
                f"{url}"
            )
            print(f"         from byte {local_size}")
        else:
            print(
                f"[GET] attempt {attempt}/{max_retries}: {url}"
            )

        try:
            with session.get(
                url,
                headers=headers,
                stream=True,
                timeout=(
                    CONNECT_TIMEOUT,
                    DOWNLOAD_READ_TIMEOUT,
                ),
                allow_redirects=True,
            ) as response:
                status = response.status_code
                content_range = response.headers.get(
                    "Content-Range"
                )

                if status == 416:
                    remote_total = parse_content_range_total(
                        content_range
                    )
                    current_size = (
                        part_path.stat().st_size
                        if part_path.exists()
                        else 0
                    )

                    if (
                        remote_total is not None
                        and current_size == remote_total
                        and is_valid_pdf(part_path)
                    ):
                        os.replace(part_path, output_path)

                        print(
                            f"[OK] recovered completed .part: "
                            f"{output_path}"
                        )
                        return True

                    if part_path.exists():
                        part_path.unlink()

                    raise RuntimeError(
                        "HTTP 416; restart from zero"
                    )

                response.raise_for_status()

                remote_total = parse_content_range_total(
                    content_range
                )

                if local_size > 0 and status == 206:
                    range_start = parse_content_range_start(
                        content_range
                    )

                    if range_start != local_size:
                        raise RuntimeError(
                            "Content-Range start mismatch: "
                            f"expected {local_size}, "
                            f"received {content_range!r}"
                        )

                    write_mode = "ab"
                    initial_size = local_size

                elif status == 200:
                    if local_size > 0:
                        print(
                            "[WARN] server ignored Range; "
                            "restart current file from zero"
                        )

                    write_mode = "wb"
                    initial_size = 0

                elif local_size == 0 and status == 206:
                    range_start = parse_content_range_start(
                        content_range
                    )

                    if range_start not in {None, 0}:
                        raise RuntimeError(
                            "unexpected initial Content-Range: "
                            f"{content_range!r}"
                        )

                    write_mode = "wb"
                    initial_size = 0

                else:
                    raise RuntimeError(
                        f"unexpected HTTP status: {status}"
                    )

                content_length = response.headers.get(
                    "Content-Length"
                )

                expected_total: Optional[int] = None

                if remote_total is not None:
                    expected_total = remote_total
                elif content_length and content_length.isdigit():
                    expected_total = (
                        initial_size + int(content_length)
                    )

                with part_path.open(write_mode) as file:
                    for chunk in response.iter_content(
                        chunk_size=DOWNLOAD_CHUNK_SIZE
                    ):
                        if chunk:
                            file.write(chunk)

                    file.flush()
                    os.fsync(file.fileno())

            actual_size = part_path.stat().st_size

            if (
                expected_total is not None
                and actual_size != expected_total
            ):
                raise IOError(
                    "incomplete download: "
                    f"expected {expected_total} bytes, "
                    f"received {actual_size} bytes"
                )

            if not is_valid_pdf(part_path):
                if (
                    expected_total is not None
                    and actual_size == expected_total
                ):
                    part_path.unlink(missing_ok=True)

                raise IOError(
                    f"PDF validation failed: {part_path}"
                )

            os.replace(part_path, output_path)

            print(
                f"[OK] {output_path} "
                f"({output_path.stat().st_size} bytes)"
            )

            time.sleep(DOWNLOAD_DELAY_SECONDS)
            return True

        except (
            requests.RequestException,
            OSError,
            RuntimeError,
        ) as error:
            try:
                saved_size = (
                    part_path.stat().st_size
                    if part_path.exists()
                    else 0
                )
            except OSError:
                saved_size = 0

            print(f"[WARN] failed download {url}: {error}")
            print(f"       saved .part: {saved_size} bytes")

            if attempt >= max_retries:
                print(
                    f"[FAILED] after {max_retries} attempts: "
                    f"{url}"
                )
                return False

            wait = backoff_seconds(attempt)
            print(
                f"[RETRY] download retry after {wait:.1f}s"
            )
            time.sleep(wait)

    return False


# =============================================================================
# 汇总与校验
# =============================================================================

def print_record_summary(
    heading: str,
    records: list[PdfRecord],
) -> None:
    by_volume = Counter(
        record.volume for record in records
    )
    by_language = Counter(
        record.language for record in records
    )
    by_category = Counter(
        record.category for record in records
    )

    print()
    print("=" * 78)
    print(f"[{heading}]")
    print("=" * 78)
    print(f"Total records: {len(records)}")

    print("By volume:")
    for volume in sorted(by_volume):
        print(f"  vol{volume}: {by_volume[volume]}")

    print("By language:")
    for language, count in sorted(
        by_language.items()
    ):
        print(f"  {language}: {count}")

    print("By category:")
    for category, count in sorted(
        by_category.items()
    ):
        print(f"  {category}: {count}")


def validate_selected_files(
    output_dir: Path,
    records: list[PdfRecord],
) -> tuple[int, list[str], list[str]]:
    valid_count = 0
    missing: list[str] = []
    invalid: list[str] = []

    for record in records:
        path = output_dir / record.relative_path

        if not path.exists():
            missing.append(str(path))
        elif is_valid_pdf(path):
            valid_count += 1
        else:
            invalid.append(str(path))

    return valid_count, missing, invalid


# =============================================================================
# 命令行
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "HKCMMS downloader optimized for a small "
            "GraphRAG document corpus."
        )
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=(
            "Output directory. Default: "
            "data/pharmacopoeia/raw/hkcmms"
        ),
    )

    parser.add_argument(
        "--volumes",
        type=int,
        nargs="+",
        default=list(DEFAULT_VOLUMES),
        help="Volumes to include, e.g. --volumes 1 2 3",
    )

    parser.add_argument(
        "--mode",
        choices=[
            "sample",
            "keywords",
            "zh-monographs",
            "all",
        ],
        default="sample",
        help=(
            "sample: evenly sample Chinese monographs; "
            "keywords: match a keyword file; "
            "zh-monographs: all Chinese monographs; "
            "all: all manifest records."
        ),
    )

    parser.add_argument(
        "--sample-per-volume",
        type=int,
        default=3,
        help=(
            "Number of Chinese monographs selected per volume "
            "in sample mode. Default: 3."
        ),
    )

    parser.add_argument(
        "--keywords-file",
        type=Path,
        default=None,
        help=(
            "UTF-8 text file containing one keyword per line. "
            "Required for --mode keywords."
        ),
    )

    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help=(
            "Write full and selected manifests, but do not "
            "download PDFs."
        ),
    )

    parser.add_argument(
        "--refresh-manifest",
        action="store_true",
        help=(
            "Rescan the official website even when an existing "
            "full CSV manifest is available."
        ),
    )

    parser.add_argument(
        "--max-pages-per-volume",
        type=int,
        default=MAX_HTML_PAGES_PER_VOLUME,
        help=(
            "Safety limit for scanned HTML pages per volume. "
            f"Default: {MAX_HTML_PAGES_PER_VOLUME}."
        ),
    )

    parser.add_argument(
        "--download-retries",
        type=int,
        default=DOWNLOAD_MAX_RETRIES,
        help=(
            "Maximum retries for each PDF. "
            f"Default: {DOWNLOAD_MAX_RETRIES}."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    volumes = sorted(set(args.volumes))

    invalid_volumes = [
        volume
        for volume in volumes
        if volume < 1 or volume > 11
    ]

    if invalid_volumes:
        print(
            f"[ERROR] invalid volumes: {invalid_volumes}; "
            "allowed range is 1-11"
        )
        return 2

    if args.sample_per_volume < 1:
        print(
            "[ERROR] --sample-per-volume must be at least 1"
        )
        return 2

    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    full_manifest_path = output_dir / FULL_MANIFEST_CSV
    failed_pages: list[str] = []

    print(f"[INFO] project root : {PROJECT_ROOT}")
    print(f"[INFO] output dir   : {output_dir}")
    print(f"[INFO] mode         : {args.mode}")
    print(f"[INFO] volumes      : {volumes}")

    # 优先复用已有的全量 manifest，避免每次都重新扫描官网。
    if (
        full_manifest_path.exists()
        and not args.refresh_manifest
    ):
        print(
            f"[INFO] load existing manifest: "
            f"{full_manifest_path}"
        )

        try:
            full_records = load_manifest(
                full_manifest_path
            )
        except Exception as error:
            print(
                f"[WARN] existing manifest cannot be loaded: "
                f"{error}"
            )
            print("[INFO] rescan official website")

            full_records, failed_pages = scan_all_volumes(
                volumes=list(DEFAULT_VOLUMES),
                max_pages_per_volume=(
                    args.max_pages_per_volume
                ),
            )

            write_full_manifest(
                output_dir,
                full_records,
            )
    else:
        full_records, failed_pages = scan_all_volumes(
            volumes=list(DEFAULT_VOLUMES),
            max_pages_per_volume=(
                args.max_pages_per_volume
            ),
        )

        write_full_manifest(
            output_dir,
            full_records,
        )

    write_lines(
        output_dir / FAILED_PAGES_TXT,
        failed_pages,
    )

    print_record_summary(
        "FULL MANIFEST SUMMARY",
        full_records,
    )

    try:
        selected_records = select_records(
            records=full_records,
            mode=args.mode,
            sample_per_volume=args.sample_per_volume,
            keywords_file=args.keywords_file,
            volumes=volumes,
        )
    except (
        FileNotFoundError,
        ValueError,
    ) as error:
        print(f"[ERROR] {error}")
        return 2

    write_selected_manifest(
        output_dir,
        selected_records,
    )

    print_record_summary(
        "SELECTED DATASET SUMMARY",
        selected_records,
    )

    if not selected_records:
        print(
            "[ERROR] no PDF records matched the current "
            "selection conditions"
        )
        return 2

    if args.manifest_only:
        print()
        print(
            "[DONE] manifest-only mode; no PDF was downloaded"
        )
        return 1 if failed_pages else 0

    failed_downloads: list[str] = []

    print()
    print("=" * 78)
    print("[DOWNLOAD SELECTED DATASET]")
    print("=" * 78)

    with create_session() as session:
        total = len(selected_records)

        for index, record in enumerate(
            selected_records,
            start=1,
        ):
            output_path = (
                output_dir / record.relative_path
            )

            print()
            print(
                f"[ITEM] {index}/{total} "
                f"vol{record.volume}/"
                f"{record.language}/"
                f"{record.category}"
            )

            success = download_pdf(
                session=session,
                url=record.url,
                output_path=output_path,
                max_retries=args.download_retries,
            )

            if not success:
                failed_downloads.append(record.url)

    write_lines(
        output_dir / FAILED_DOWNLOADS_TXT,
        failed_downloads,
    )

    valid_count, missing, invalid = (
        validate_selected_files(
            output_dir=output_dir,
            records=selected_records,
        )
    )

    write_lines(
        output_dir / MISSING_FILES_TXT,
        missing,
    )
    write_lines(
        output_dir / INVALID_FILES_TXT,
        invalid,
    )

    total_size_bytes = sum(
        (output_dir / record.relative_path).stat().st_size
        for record in selected_records
        if is_valid_pdf(
            output_dir / record.relative_path
        )
    )

    print()
    print("=" * 78)
    print("[FINAL SUMMARY]")
    print("=" * 78)
    print(f"Full manifest records : {len(full_records)}")
    print(
        f"Selected target PDFs  : "
        f"{len(selected_records)}"
    )
    print(f"Valid selected PDFs   : {valid_count}")
    print(f"Missing selected PDFs : {len(missing)}")
    print(f"Invalid selected PDFs : {len(invalid)}")
    print(f"Failed downloads      : {len(failed_downloads)}")
    print(f"Failed HTML pages     : {len(set(failed_pages))}")
    print(
        f"Selected size (MB)    : "
        f"{total_size_bytes / 1024 / 1024:.2f}"
    )

    if (
        failed_pages
        or failed_downloads
        or missing
        or invalid
    ):
        print()
        print(
            "[INCOMPLETE] rerun the same command. Valid PDFs "
            "will be skipped and .part files will resume."
        )
        return 1

    print()
    print(
        "[DONE] selected GraphRAG PDF dataset downloaded "
        "and validated."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print()
        print(
            "[INTERRUPTED] .part files are preserved. "
            "Rerun the same command to resume."
        )
        raise SystemExit(130)
