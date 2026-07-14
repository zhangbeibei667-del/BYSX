from __future__ import annotations

import httpx


class LLMClient:
    """
    DeepSeek / OpenAI-compatible Chat Completions 客户端。

    API Key 通过 .env / 环境变量注入，
    不写死在源码中。
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
    ) -> None:
        clean_base_url = base_url.strip().rstrip("/")
        clean_api_key = api_key.strip()
        clean_model = model.strip()

        if not clean_base_url:
            raise ValueError(
                "LLM_BASE_URL 为空"
            )

        if not clean_api_key:
            raise ValueError(
                "LLM_API_KEY 为空"
            )

        if not clean_model:
            raise ValueError(
                "LLM_MODEL 为空"
            )

        self.url = (
            f"{clean_base_url}/chat/completions"
        )

        self.api_key = clean_api_key
        self.model = clean_model

    def generate(
        self,
        prompt: str,
    ) -> str:
        clean_prompt = prompt.strip()

        if not clean_prompt:
            raise ValueError(
                "prompt 为空"
            )

        headers = {
            "Authorization": (
                f"Bearer {self.api_key}"
            ),
            "Content-Type": (
                "application/json"
            ),
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
                    "content": clean_prompt,
                },
            ],
            "temperature": 0.2,
        }

        with httpx.Client(
            timeout=60.0
        ) as client:
            response = client.post(
                self.url,
                headers=headers,
                json=payload,
            )

        # 不再只给一个模糊 HTTPStatusError。
        if response.is_error:
            detail = (
                response.text[:500]
                .replace("\r", " ")
                .replace("\n", " ")
            )

            raise RuntimeError(
                "LLM API 请求失败："
                f"HTTP {response.status_code}; "
                f"response={detail}"
            )

        body = response.json()

        try:
            content = (
                body["choices"][0]
                ["message"]["content"]
            )

        except (
            KeyError,
            IndexError,
            TypeError,
        ) as exc:
            raise RuntimeError(
                "LLM API 返回结构异常："
                f"{str(body)[:500]}"
            ) from exc

        answer = str(content).strip()

        if not answer:
            raise RuntimeError(
                "LLM API 返回空答案"
            )

        return answer