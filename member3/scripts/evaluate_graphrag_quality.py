from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.graph_search import GraphSearch
from app.graphrag_service import GraphRAGService
from app.llm_client import LLMClient
from app.schemas import GraphRAGQueryRequest


DEFAULT_CASES_PATH = (
    PROJECT_ROOT
    / "data"
    / "evaluation"
    / "graphrag_eval_questions.jsonl"
)

DEFAULT_REPORT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "graphrag_eval_report.json"
)


class EmptyRetriever:
    """离线评测用检索器：只评估图谱路径、社区摘要和 fallback。"""

    def search(
        self,
        query: str,
        top_k: int = 3,
    ):
        return []


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path} 第 {line_number} 行不是有效 JSON"
                ) from exc

    return rows


def contains_all(
    text: str,
    keywords: list[str],
) -> bool:
    return all(
        keyword in text
        for keyword in keywords
    )


def evaluate_case(
    service: GraphRAGService,
    case: dict[str, Any],
    top_k: int,
) -> dict[str, Any]:
    result = service.query(
        GraphRAGQueryRequest(
            query=str(case["query"]),
            top_k=top_k,
            max_hops=2,
        )
    )

    evidence_text = "\n".join(
        f"{item.title}\n{item.content}"
        for item in result.evidence
    )
    graph_text = "\n".join(
        [
            *[
                f"{node.id} {node.label} {node.type}"
                for node in result.graph.nodes
            ],
            *[
                f"{edge.source} {edge.label} {edge.target}"
                for edge in result.graph.edges
            ],
        ]
    )
    answer_text = result.answer

    checks: list[tuple[str, bool]] = []

    expected_source = case.get("expected_source")
    if expected_source:
        checks.append(
            (
                f"source={expected_source}",
                expected_source in evidence_text,
            )
        )

    expected_title_keywords = case.get(
        "expected_title_keywords",
        [],
    )
    if expected_title_keywords:
        checks.append(
            (
                "title_keywords",
                contains_all(
                    evidence_text,
                    expected_title_keywords,
                ),
            )
        )

    expected_graph_keywords = case.get(
        "expected_graph_keywords",
        [],
    )
    if expected_graph_keywords:
        checks.append(
            (
                "graph_keywords",
                contains_all(
                    graph_text + "\n" + answer_text,
                    expected_graph_keywords,
                ),
            )
        )

    expected_evidence_keywords = case.get(
        "expected_evidence_keywords",
        [],
    )
    if expected_evidence_keywords:
        checks.append(
            (
                "evidence_keywords",
                contains_all(
                    evidence_text,
                    expected_evidence_keywords,
                ),
            )
        )

    passed = all(
        ok
        for _name, ok in checks
    )

    return {
        "id": case.get("id"),
        "query": case.get("query"),
        "intent": case.get("intent"),
        "passed": passed,
        "checks": checks,
        "answer_preview": answer_text[:160],
        "evidence_titles": [
            item.title
            for item in result.evidence[:5]
        ],
        "graph_nodes": [
            node.label
            for node in result.graph.nodes[:8]
        ],
    }


def build_service(
    enable_llm: bool,
    use_env_graph: bool,
    no_vector: bool,
) -> GraphRAGService:
    entities_path = PROJECT_ROOT / "data" / "entities.json"
    relations_path = PROJECT_ROOT / "data" / "relations.json"

    if use_env_graph:
        entities_path = Path(
            os.getenv(
                "GRAPH_ENTITIES_PATH",
                str(entities_path),
            )
        )
        relations_path = Path(
            os.getenv(
                "GRAPH_RELATIONS_PATH",
                str(relations_path),
            )
        )

    graph_search = GraphSearch(
        entities_path=entities_path,
        relations_path=relations_path,
    )

    if no_vector:
        vector_search = EmptyRetriever()
    else:
        from app.milvus_search import MilvusVectorSearch

        vector_search = MilvusVectorSearch()

    llm_client = None

    if enable_llm:
        llm_client = LLMClient(
            base_url=os.getenv(
                "LLM_BASE_URL",
                "https://api.deepseek.com",
            ),
            api_key=os.getenv(
                "LLM_API_KEY",
                "",
            ),
            model=os.getenv(
                "LLM_MODEL",
                "deepseek-chat",
            ),
        )

    return GraphRAGService(
        vector_search=vector_search,
        graph_search=graph_search,
        llm_client=llm_client,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="运行成员三 GraphRAG 固定质量评测集。"
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES_PATH,
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--enable-llm",
        action="store_true",
        help="默认只评估检索和 fallback，不调用 LLM。",
    )
    parser.add_argument(
        "--use-env-graph",
        action="store_true",
        help="默认只评估 member3 本地图谱；传入该参数才使用 .env 中的团队图谱路径。",
    )
    parser.add_argument(
        "--no-vector",
        action="store_true",
        help="不连接 Milvus/Embedding，只跑不依赖向量检索的用例。",
    )
    parser.add_argument(
        "--intent",
        default="",
        help="只运行指定 intent 的用例。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="评测 JSON 报告输出路径。",
    )
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")

    cases = read_jsonl(args.cases)

    if args.intent:
        cases = [
            case
            for case in cases
            if case.get("intent") == args.intent
        ]

    skipped_cases: list[dict[str, Any]] = []

    if args.no_vector:
        runnable_cases = []

        for case in cases:
            if case.get("requires_vector"):
                skipped_cases.append(case)
            else:
                runnable_cases.append(case)

        cases = runnable_cases

    service = build_service(
        enable_llm=args.enable_llm,
        use_env_graph=args.use_env_graph,
        no_vector=args.no_vector,
    )

    reports = [
        evaluate_case(
            service=service,
            case=case,
            top_k=args.top_k,
        )
        for case in cases
    ]

    passed_count = sum(
        1
        for report in reports
        if report["passed"]
    )

    print("=" * 80)
    print("GraphRAG Quality Evaluation")
    print("=" * 80)
    print(f"cases : {len(reports)}")
    print(f"passed: {passed_count}")
    print(f"failed: {len(reports) - passed_count}")
    print(f"skipped: {len(skipped_cases)}")
    print()

    for report in reports:
        status = "PASS" if report["passed"] else "FAIL"
        print(f"[{status}] {report['id']} | {report['query']}")

        for name, ok in report["checks"]:
            mark = "ok" if ok else "missing"
            print(f"  - {name}: {mark}")

        print(
            "  evidence: "
            + " | ".join(report["evidence_titles"][:3])
        )
        print()

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    args.output.write_text(
        json.dumps(
            {
                "cases": len(reports),
                "passed": passed_count,
                "failed": len(reports) - passed_count,
                "skipped": [
                    {
                        "id": case.get("id"),
                        "query": case.get("query"),
                        "reason": "requires_vector",
                    }
                    for case in skipped_cases
                ],
                "reports": [
                    {
                        **report,
                        "checks": [
                            {
                                "name": name,
                                "passed": ok,
                            }
                            for name, ok in report["checks"]
                        ],
                    }
                    for report in reports
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"report: {args.output}")

    return 0 if passed_count == len(reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
