from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value)
    text = text.replace("\ufeff", "").replace("\u200b", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    text = text.strip()

    # 仅清理首尾异常 ASCII 双引号，不修改中文引号
    if text.startswith('"'):
        text = text[1:]
    if text.endswith('"'):
        text = text[:-1]

    lines: list[str] = []
    for line in text.split("\n"):
        line = re.sub(r"[ \u3000]+", " ", line).strip()
        if line:
            lines.append(line)

    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sliding_chunks(
    text: str,
    max_chars: int = 700,
    overlap: int = 80,
) -> list[str]:
    text = clean_text(text)

    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = min(start + max_chars, len(text))

        if end < len(text):
            window = text[start:end]
            search_from = int(len(window) * 0.65)

            candidates = [
                window.rfind("。", search_from),
                window.rfind("；", search_from),
                window.rfind("\n", search_from),
                window.rfind("！", search_from),
                window.rfind("？", search_from),
            ]

            cut = max(candidates)

            if cut > 0:
                end = start + cut + 1

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = max(end - overlap, start + 1)

    return chunks


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl_from_zip(
    zip_file: zipfile.ZipFile,
    name: str,
) -> list[dict]:
    rows: list[dict] = []

    with zip_file.open(name) as file:
        for line_no, raw in enumerate(file, start=1):
            if not raw.strip():
                continue

            try:
                rows.append(json.loads(raw.decode("utf-8")))
            except Exception as exc:
                raise ValueError(
                    f"{name} 第 {line_no} 行 JSON 解析失败"
                ) from exc

    return rows


def clean_tcm_qg(qg_path: Path) -> tuple[list[dict], list[dict]]:
    with qg_path.open("r", encoding="utf-8") as file:
        raw_rows = json.load(file)

    chunks: list[dict] = []
    alignment_issues: list[dict] = []

    for item in raw_rows:
        doc_id = str(item["id"])
        content = clean_text(item.get("text", ""))

        questions: list[str] = []
        answers: list[str] = []
        aligned_flags: list[bool] = []

        for annotation in item.get("annotations", []):
            question = clean_text(annotation.get("Q", ""))
            answer = clean_text(annotation.get("A", ""))

            if question:
                questions.append(question)

            if answer:
                answers.append(answer)

            aligned = bool(answer and answer in content)
            aligned_flags.append(aligned)

            if answer and not aligned:
                alignment_issues.append(
                    {
                        "doc_id": doc_id,
                        "question": question,
                        "answer": answer,
                    }
                )

        chunks.append(
            {
                "chunk_id": f"TCMQG_{doc_id}",
                "doc_id": doc_id,
                "title": f"TCM-QG 文档 {doc_id}",
                "content": content,
                "source": "TCM-QG",
                "metadata": {
                    "record_type": "literature_qa",
                    "questions": questions,
                    "answers": answers,
                    "qa_count": len(item.get("annotations", [])),
                    "all_answers_aligned": (
                        all(aligned_flags)
                        if aligned_flags
                        else True
                    ),
                },
            }
        )

    return chunks, alignment_issues


def clean_tcm_sd(
    sd_zip_path: Path,
) -> tuple[
    list[dict],
    list[dict],
    dict,
]:
    with zipfile.ZipFile(sd_zip_path, "r") as zip_file:
        train_rows = read_jsonl_from_zip(zip_file, "train.json")
        dev_rows = read_jsonl_from_zip(zip_file, "dev.json")
        knowledge_rows = read_jsonl_from_zip(
            zip_file,
            "syndrome_knowledge.json",
        )
        vocab = [
            line.strip()
            for line in zip_file
            .read("syndrome_vocab.txt")
            .decode("utf-8")
            .splitlines()
            if line.strip()
        ]

    # 证候知识 -> RAG corpus
    knowledge_chunks: list[dict] = []

    for item in knowledge_rows:
        knowledge_id = str(item.get("id", ""))
        name = clean_text(item.get("Name", ""))
        definition = clean_text(item.get("Definition", ""))
        typical = clean_text(item.get("Typical_performance", ""))
        common = clean_text(item.get("Common_isease", ""))

        overview_parts = [f"证候：{name}"]

        if definition:
            overview_parts.append(f"定义：{definition}")

        if typical:
            overview_parts.append(f"典型表现：{typical}")

        overview = "\n".join(overview_parts)

        if overview.strip():
            knowledge_chunks.append(
                {
                    "chunk_id": (
                        f"TCMSD_KNOW_{knowledge_id}_OVERVIEW"
                    ),
                    "doc_id": f"TCMSD_KNOW_{knowledge_id}",
                    "title": f"{name}：定义与典型表现",
                    "content": overview,
                    "source": "TCM-SD",
                    "metadata": {
                        "record_type": "syndrome_knowledge",
                        "section": "overview",
                        "syndrome": name,
                        "knowledge_id": knowledge_id,
                    },
                }
            )

        common_chunks = sliding_chunks(
            common,
            max_chars=700,
            overlap=80,
        )

        for part_no, chunk in enumerate(common_chunks, start=1):
            knowledge_chunks.append(
                {
                    "chunk_id": (
                        f"TCMSD_KNOW_{knowledge_id}_"
                        f"COMMON_{part_no}"
                    ),
                    "doc_id": f"TCMSD_KNOW_{knowledge_id}",
                    "title": f"{name}：常见疾病与相关说明",
                    "content": f"证候：{name}\n{chunk}",
                    "source": "TCM-SD",
                    "metadata": {
                        "record_type": "syndrome_knowledge",
                        "section": "common_disease",
                        "syndrome": name,
                        "knowledge_id": knowledge_id,
                        "part": part_no,
                    },
                }
            )

    # dev -> evaluation only
    # 删除 user_id，避免将原始用户标识带入评测集
    dev_eval: list[dict] = []
    seen_signatures: set[str] = set()

    for item in dev_rows:
        chief = clean_text(item.get("chief_complaint", ""))
        description = clean_text(item.get("description", ""))
        detection = clean_text(item.get("detection", ""))
        norm_syndrome = clean_text(item.get("norm_syndrome", ""))
        raw_syndrome = clean_text(item.get("syndrome", ""))
        lcd_id = clean_text(item.get("lcd_id", ""))
        lcd_name = clean_text(item.get("lcd_name", ""))

        signature_source = "\n".join(
            [
                chief,
                description,
                detection,
                norm_syndrome,
            ]
        )

        signature = hashlib.sha256(
            signature_source.encode("utf-8")
        ).hexdigest()

        if signature in seen_signatures:
            continue

        seen_signatures.add(signature)

        query_parts = []

        if chief:
            query_parts.append(f"主诉：{chief}")

        if description:
            query_parts.append(f"病情描述：{description}")

        if detection:
            query_parts.append(f"四诊/检查摘要：{detection}")

        dev_eval.append(
            {
                "eval_id": (
                    f"TCMSD_DEV_{len(dev_eval) + 1:05d}"
                ),
                "query_text": "\n".join(query_parts),
                "label": {
                    "syndrome": raw_syndrome,
                    "norm_syndrome": norm_syndrome,
                    "lcd_id": lcd_id,
                    "lcd_name": lcd_name,
                },
                "source": "TCM-SD",
            }
        )

    train_users = {
        str(row.get("user_id", ""))
        for row in train_rows
    }

    dev_users = {
        str(row.get("user_id", ""))
        for row in dev_rows
    }

    def signature_tuple(row: dict) -> tuple:
        return (
            clean_text(row.get("chief_complaint", "")),
            clean_text(row.get("description", "")),
            clean_text(row.get("detection", "")),
            clean_text(row.get("norm_syndrome", "")),
        )

    train_counts = Counter(
        signature_tuple(row)
        for row in train_rows
    )

    dev_counts = Counter(
        signature_tuple(row)
        for row in dev_rows
    )

    stats = {
        "train_records": len(train_rows),
        "dev_records": len(dev_rows),
        "knowledge_records": len(knowledge_rows),
        "vocab_size": len(vocab),
        "train_norm_syndromes": len(
            {
                row.get("norm_syndrome", "")
                for row in train_rows
            }
        ),
        "dev_norm_syndromes": len(
            {
                row.get("norm_syndrome", "")
                for row in dev_rows
            }
        ),
        "shared_user_ids": len(train_users & dev_users),
        "train_exact_duplicate_surplus": sum(
            count - 1
            for count in train_counts.values()
            if count > 1
        ),
        "dev_exact_duplicate_surplus": sum(
            count - 1
            for count in dev_counts.values()
            if count > 1
        ),
        "dev_eval_after_dedup": len(dev_eval),
    }

    return knowledge_chunks, dev_eval, stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="清洗 TCM-QG 与 TCM-SD 数据"
    )

    parser.add_argument(
        "--qg",
        type=Path,
        required=True,
        help="TCM-QG train.json 路径",
    )

    parser.add_argument(
        "--sd-zip",
        type=Path,
        required=True,
        help="TCM_SD_train_dev.zip 路径",
    )

    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("rag_cleaned"),
        help="输出目录",
    )

    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    qg_chunks, alignment_issues = clean_tcm_qg(args.qg)

    (
        sd_knowledge_chunks,
        sd_dev_eval,
        sd_stats,
    ) = clean_tcm_sd(args.sd_zip)

    rag_corpus = qg_chunks + sd_knowledge_chunks

    write_jsonl(
        args.out_dir / "tcm_qg_chunks_clean.jsonl",
        qg_chunks,
    )

    write_jsonl(
        args.out_dir
        / "tcm_sd_syndrome_knowledge_clean.jsonl",
        sd_knowledge_chunks,
    )

    write_jsonl(
        args.out_dir / "tcm_sd_dev_eval_clean.jsonl",
        sd_dev_eval,
    )

    write_jsonl(
        args.out_dir / "rag_corpus_clean.jsonl",
        rag_corpus,
    )

    write_jsonl(
        args.out_dir / "tcm_qg_alignment_issues.jsonl",
        alignment_issues,
    )

    stats = {
        "tcm_qg_chunks": len(qg_chunks),
        "tcm_qg_alignment_issues": len(alignment_issues),
        "tcm_sd_knowledge_chunks": len(sd_knowledge_chunks),
        "tcm_sd_dev_eval": len(sd_dev_eval),
        "rag_corpus_total": len(rag_corpus),
        "tcm_sd_audit": sd_stats,
    }

    with (
        args.out_dir / "cleaning_stats.json"
    ).open("w", encoding="utf-8") as file:
        json.dump(
            stats,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
