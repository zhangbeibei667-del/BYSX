from backend.mock_data.tcm_mock_data import SAFETY_NOTICE


class SafetyReviewAgent:
    """Review wording and attach a fixed safety notice."""

    RISKY_REPLACEMENTS = {
        "确诊": "教学判断",
        "必须服用": "可在教学场景中了解",
        "治疗保证": "学习参考",
        "保证治愈": "用于知识学习",
        "处方": "方剂知识",
    }

    def run(self, answer: str) -> dict:
        print("[SafetyReviewAgent] start")
        reviewed_answer = answer
        for risky_word, safe_word in self.RISKY_REPLACEMENTS.items():
            reviewed_answer = reviewed_answer.replace(risky_word, safe_word)

        if SAFETY_NOTICE not in reviewed_answer:
            reviewed_answer = f"{reviewed_answer}{SAFETY_NOTICE}"

        result = {
            "answer": reviewed_answer,
            "safety_notice": SAFETY_NOTICE,
        }
        print("[SafetyReviewAgent] completed")
        return result
