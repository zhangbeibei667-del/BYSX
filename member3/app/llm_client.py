from __future__ import annotations

import httpx


class LLMClient:
    """
    DeepSeek / OpenAI-compatible Chat Completions 客户端。

    默认项目关闭真实 LLM 调用。
    填写 .env 后即可启用，不需要把 API Key 写死在源码中。
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
    ) -> None:
        if not api_key:
            raise ValueError("LLM_API_KEY 为空")

        self.url = f"{base_url.rstrip('/')}/chat/completions"
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是中医药知识学习与教学辅助助手。"
                        "必须依据提供的文本证据和图谱证据回答，"
                        "不得输出真实医疗诊断或个体化用药建议。"
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.2,
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                self.url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            body = response.json()

        return body["choices"][0]["message"]["content"].strip()
