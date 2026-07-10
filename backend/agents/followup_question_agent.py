class FollowUpQuestionAgent:
    """Generate teaching-oriented follow-up questions when case details are limited."""

    def run(self, symptom_result: dict) -> dict:
        print("[FollowUpQuestionAgent] start")
        symptoms = symptom_result.get("symptoms", [])
        tongue = symptom_result.get("tongue", [])
        pulse = symptom_result.get("pulse", [])

        questions = []
        gastrointestinal = {
            "胃肠不适", "胃痛", "腹胀", "恶心", "呕吐",
            "腹泻", "便溏", "反酸", "嗳气", "食欲不振",
        }
        if gastrointestinal.intersection(symptoms):
            questions.append("具体不适是胃痛、腹胀、恶心、反酸、腹泻还是便秘？")
            questions.append("症状与进食、情绪或受凉是否有关，大便和食欲有何变化？")
        if len(symptoms) < 3:
            if not gastrointestinal.intersection(symptoms):
                questions.append("还伴有哪些主要症状，症状之间是否同时出现？")
            questions.append("症状持续多久，是否有劳累、情绪或饮食等诱因？")
        if not tongue:
            questions.append("是否有舌象信息，例如舌质颜色、舌苔厚薄和颜色？")
        if not pulse:
            questions.append("是否有脉象信息，例如脉细、脉弱、脉弦或脉数？")
        if len(symptoms) >= 3 and tongue and pulse:
            questions.append("是否需要进一步补充睡眠、饮食、二便、寒热等教学分析信息？")

        result = {"follow_up_questions": questions[:4]}
        print("[FollowUpQuestionAgent] completed")
        return result
