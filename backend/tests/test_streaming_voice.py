import asyncio
import json
import unittest
from unittest.mock import patch

from backend.api import frontend_compat_api


class _StreamingLLM:
    available = True
    provider = "test-provider"
    model = "test-model"

    def stream(self, messages, temperature=0.2):
        del messages, temperature
        yield "现有信息不足以"
        yield "判断具体证候。建议补充"
        yield "病程和伴随表现。"


async def _collect_stream(response):
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    return "".join(chunks)


class StreamingVoiceTests(unittest.TestCase):
    def test_clinical_sse_releases_checked_complete_sentences(self):
        prepared = {
            "answer": "fallback",
            "query": "我最近失眠多梦，应该怎么调理？",
            "mode": "graph-rag",
            "generation": {"mode": "retrieval-only"},
            "conversation": {},
            "graph": {"nodes": [], "edges": []},
            "evidence": [],
        }
        with (
            patch.object(frontend_compat_api, "prepare_chat", return_value=prepared),
            patch.object(frontend_compat_api, "get_llm_client", return_value=_StreamingLLM()),
            patch.object(
                frontend_compat_api.RAGRetrievalTool,
                "build_generation_messages",
                return_value=[{"role": "user", "content": prepared["query"]}],
            ),
        ):
            response = frontend_compat_api.ask_chat_token_stream(prepared["query"])
            body = asyncio.run(_collect_stream(response))

        events = []
        for frame in body.split("\n\n"):
            if not frame.startswith("data: {"):
                continue
            events.append(json.loads(frame.removeprefix("data: ")))

        chunks = [event for event in events if event.get("type") == "chunk"]
        final = next(event for event in events if event.get("type") == "result")
        self.assertEqual(len(chunks), 2)
        self.assertTrue(all(event.get("sentence") is True for event in chunks))
        self.assertTrue(all(event["content"].endswith("。") for event in chunks))
        self.assertEqual(final["content"], "".join(event["content"] for event in chunks))
        self.assertEqual(
            final["result"]["generation"]["mode"],
            "llm-clinical-safe-sentence-stream",
        )
        self.assertEqual(final["result"]["generation"]["usage"]["streamed_sentences"], 2)


if __name__ == "__main__":
    unittest.main()
