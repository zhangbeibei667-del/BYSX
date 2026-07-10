class StreamingVoiceQATool:
    """Mock streaming voice Q&A tool.

    TODO: Replace with a real speech service later:
    ASR audio input -> streaming LLM answer -> TTS audio stream.
    """

    def build_voice_qa(self, symptoms: list[str], syndromes: list[str], answer: str) -> dict:
        symptom_text = "、".join(symptoms) if symptoms else "待补充症状"
        syndrome_text = "、".join(syndromes) if syndromes else "待进一步分析证候"

        return {
            "enabled": True,
            "mode": "mock",
            "streaming_text": [
                "正在分析病例信息...",
                f"已识别症状：{symptom_text}。",
                f"已匹配相关证候：{syndrome_text}。",
                "正在生成教学辅助分析...",
                "已完成安全审查，可用于前端模拟流式语音播报。",
            ],
            "text_preview": answer[:100] + ("..." if len(answer) > 100 else ""),
        }
