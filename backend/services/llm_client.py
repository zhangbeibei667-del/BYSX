from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from pathlib import Path


def load_local_env() -> None:
    """Load a local .env without overwriting process-level configuration."""
    candidates = [Path(__file__).resolve().parents[1] / ".env", Path(__file__).resolve().parents[2] / ".env"]
    for path in candidates:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()


class LLMClient:
    """Small OpenAI-compatible DeepSeek client; secrets never leave environment configuration."""

    def __init__(self) -> None:
        self.enabled = os.getenv("LLM_ENABLED", "false").lower() == "true"
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
        self.api_key = os.getenv("LLM_API_KEY", "").strip()
        self.model = os.getenv("LLM_MODEL", "deepseek-v4-flash")
        self.provider = "aliyun-bailian" if "dashscope.aliyuncs.com" in self.base_url else "deepseek"
        self.timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
        self.last_error = ""
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self.enabled and bool(self.api_key)

    def status(self) -> dict:
        return {"provider": self.provider, "enabled": self.enabled, "configured": bool(self.api_key),
                "available": self.available, "base_url": self.base_url, "model": self.model,
                "last_error": self.last_error}

    def complete(self, messages: list[dict], temperature: float = 0.2,
                 response_format: dict | None = None) -> dict | None:
        if not self.available:
            return None
        payload = {"model": self.model, "messages": messages, "temperature": temperature, "stream": False}
        if response_format:
            payload["response_format"] = response_format
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"].strip()
            with self._lock:
                self.last_error = ""
            return {"content": content, "model": data.get("model", self.model), "usage": data.get("usage", {}),
                    "provider": self.provider}
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
            message = f"{type(exc).__name__}: {exc}"
            if isinstance(exc, urllib.error.HTTPError):
                try:
                    message += " " + exc.read().decode("utf-8")[:500]
                except Exception:
                    pass
            with self._lock:
                self.last_error = message
            return None


_CLIENT: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = LLMClient()
    return _CLIENT
