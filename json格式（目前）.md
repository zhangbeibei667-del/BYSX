统一关系格式
json
{
  "source_id": "F001",
  "source_name": "归脾汤",
  "relation": "包含",
  "target_id": "H001",
  "target_name": "酸枣仁",
  "evidence": "方剂组成资料"
}
关系类型固定为：包含、主治、提示、对应、具有、禁忌、来源于、记载


统一图谱返回格式
json
{
  "nodes": [
    {"id": "S001", "label": "失眠", "type": "症状"},
    {"id": "Z001", "label": "心脾两虚", "type": "证候"},
    {"id": "F001", "label": "归脾汤", "type": "方剂"},
    {"id": "H001", "label": "酸枣仁", "type": "药材"}
  ],
  "edges": [
    {"source": "S001", "target": "Z001", "label": "提示"},
    {"source": "Z001", "target": "F001", "label": "对应"},
    {"source": "F001", "target": "H001", "label": "包含"}
  ]
}


统一问答结果格式
json
{
  "answer": "根据图谱路径和资料片段，该病例可从心脾两虚角度进行教学分析……",
  "symptoms": ["失眠", "多梦", "心悸", "健忘"],
  "syndromes": ["心脾两虚"],
  "formulas": ["归脾汤"],
  "herbs": ["酸枣仁", "远志", "人参", "黄芪"],
  "graph": {
    "nodes": [],
    "edges": []
  },
  "evidence": [
    {
      "title": "归脾汤方剂说明",
      "content": "归脾汤具有益气补血、健脾养心等功效……"
    }
  ],
  "follow_up_questions": [
    "是否伴有食少乏力？",
    "是否有舌淡、脉细等表现？"
  ],
  "safety_notice": "本结果仅用于中医药知识学习和教学辅助，不构成医疗诊断或用药建议。"
}