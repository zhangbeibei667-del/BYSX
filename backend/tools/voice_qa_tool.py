class StreamingVoiceQATool:
    """Describe the real browser Web Speech streaming contract."""

    def build_voice_qa(self, symptoms: list[str], syndromes: list[str], answer: str) -> dict:
        return {
            "enabled": True,
            "mode": "browser-web-speech",
            "asr": {"engine": "Web Speech Recognition", "language": "zh-CN", "interim_results": True},
            "tts": {"engine": "SpeechSynthesis", "language": "zh-CN", "stream_by_sentence": True},
            "streaming_text": self._sentences(answer),
            "text_preview": answer[:160] + ("..." if len(answer) > 160 else ""),
        }

    @staticmethod
    def _sentences(text: str) -> list[str]:
        import re
        return [item.strip() for item in re.split(r"(?<=[。！？!?])", text) if item.strip()]
