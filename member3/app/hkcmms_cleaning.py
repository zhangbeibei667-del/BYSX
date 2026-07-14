from __future__ import annotations

import re


OCR_TOKEN_RE = re.compile(
    r"\b(?:THE|VID|VUD|MER|Uff|PBR|RR|Std|Stock)\b",
    flags=re.IGNORECASE,
)

DISPLAY_SIMPLIFIED_REPLACEMENTS = {
    "黃": "黄",
    "鑒別": "鉴别",
    "顯微": "显微",
    "薄層": "薄层",
    "色譜": "色谱",
    "指紋圖譜": "指纹图谱",
    "檢查": "检查",
    "來源": "来源",
    "含量測定": "含量测定",
    "對照品溶液": "对照品溶液",
    "供試品溶液": "供试品溶液",
    "色譜條件": "色谱条件",
    "雜質": "杂质",
    "農藥殘留": "农药残留",
    "二氧化硫殘留": "二氧化硫残留",
    "重金屬": "重金属",
    "霉菌毒素-黃曲霉毒素": "霉菌毒素-黄曲霉毒素",
    "為": "为",
    "乾燥": "干燥",
    "藥典": "药典",
    "標準": "标准",
    "條目": "条目",
    "條件": "条件",
    "圖譜": "图谱",
}


def compact_text(text: object) -> str:
    return " ".join(
        str(text or "")
        .replace("\r", "\n")
        .split()
    ).strip()


def simplify_hkcmms_display_text(text: str) -> str:
    """把回答中常见 HKCMMS 繁体术语转成简体显示。"""
    value = str(text or "")

    for source, target in DISPLAY_SIMPLIFIED_REPLACEMENTS.items():
        value = value.replace(source, target)

    return value


def clean_hkcmms_item_text(item: str) -> str:
    """清理 HKCMMS OCR 残片，保留适合展示/回答的栏目名称。"""
    item = compact_text(item).strip(" ：:。;；,.，")
    item = re.sub(
        r"©|®|™",
        "",
        item,
    )
    item = re.sub(
        r"[（(][^）)]*(?:THE|VID|VUD|MER|Uff|PBR|RR|應絲|季緣|[A-Za-z]{2,})[^）)]*[）)\]]?",
        "",
        item,
        flags=re.IGNORECASE,
    )
    item = re.sub(
        r"[（(]附錄[^）):：]*(?:[):：]|$)",
        "",
        item,
    )
    item = re.sub(
        r"[:：]?\s*應符合有關規定.*$",
        "",
        item,
    )
    item = re.split(
        r"[:：。；;]",
        item,
    )[0].strip()
    item = re.sub(
        r"(.{2,6})\1",
        r"\1",
        item,
    )
    item = re.sub(
        r"\s+",
        "",
        item,
    ).strip(" -—–：:。;；,.，")

    if item in {
        "檢查",
        "检查",
        "應符合有關規定",
    }:
        return ""

    if not re.search(r"[\u4e00-\u9fff]", item):
        return ""

    return item


def clean_hkcmms_section_title(title: str) -> str:
    """清理用于 evidence 标题的 HKCMMS 栏目标题。"""

    def clean_parenthetical(
        match: re.Match[str],
    ) -> str:
        value = match.group(0)

        if "附錄" in value:
            return value

        if re.search(
            r"[A-Za-z©®™]|THE|VID|VUD|MER|Uff|PBR|RR",
            value,
            flags=re.IGNORECASE,
        ):
            return ""

        return value

    section = compact_text(title)
    appendix_placeholders = {
        "__APPENDIX_IV_A__": "（附錄IV(A)）",
    }

    for placeholder, appendix in appendix_placeholders.items():
        section = section.replace(appendix, placeholder)
        section = section.replace("[附錄IV(A)]", placeholder)
    section = re.sub(
        r"©|®|™",
        "",
        section,
    )
    section = re.sub(
        r"[（(][^）)]*[）)\]]?",
        clean_parenthetical,
        section,
    )
    section = OCR_TOKEN_RE.sub(
        "",
        section,
    )
    section = re.sub(
        r"[（(]附錄[^）)]*[:：][^）)]*$",
        "",
        section,
    )
    section = re.sub(
        r"[:：]?\s*應符合有關規定.*$",
        "",
        section,
    )
    section = section.replace("..", "：")
    section = re.sub(
        r"\b(\d+\.\d)(?:\d+\.\d)\b",
        r"\1",
        section,
    )
    section = re.sub(
        r"\s*[:：]\s*",
        "：",
        section,
    )
    section = re.sub(
        r"\s+",
        " ",
        section,
    ).strip(" ：:;；,.，。")
    if (
        section.endswith(("）", ")"))
        and section.count("）") + section.count(")")
        > section.count("（") + section.count("(")
    ):
        section = re.sub(
            r"\s*[）)]\s*$",
            "",
            section,
        ).strip(" ：:;；,.，。")
    for placeholder, appendix in appendix_placeholders.items():
        section = section.replace(placeholder, appendix)

    if len(section) > 48:
        section = re.split(
            r"[。；;]",
            section,
        )[0].strip()

    return section


def clean_hkcmms_title(
    title: str,
) -> str:
    """清理完整 HKCMMS 标题，形如 HKCMMS：三七｜5.5 雜質。"""
    title = compact_text(title)

    if "｜" not in title:
        return clean_hkcmms_section_title(title)

    prefix, section = title.rsplit(
        "｜",
        1,
    )
    section = clean_hkcmms_section_title(section)

    if not section:
        return prefix

    return f"{prefix}｜{section}"
