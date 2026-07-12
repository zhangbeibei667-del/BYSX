from backend.tools.voice_qa_tool import StreamingVoiceQATool


class StreamingVoiceQAAgent:
    """Prepare the browser ASR and streaming TTS contract."""

    def __init__(self, voice_tool: StreamingVoiceQATool | None = None) -> None:
        self.voice_tool = voice_tool or StreamingVoiceQATool()

    def run(self, symptom_result: dict, graph_result: dict, explanation_result: dict) -> dict:
        print("[StreamingVoiceQAAgent] start")
        result = {
            "voice_qa": self.voice_tool.build_voice_qa(
                symptoms=symptom_result.get("symptoms", []),
                syndromes=graph_result.get("syndromes", []),
                answer=explanation_result.get("answer", ""),
            )
        }
        print("[StreamingVoiceQAAgent] completed")
        return result
