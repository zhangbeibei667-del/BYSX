# GraphRAG 数据集调研与接入计划

> 模块：member3 / GraphRAG  
> 项目：基于知识图谱的中医药诊疗智能体  
> 说明：本文件记录候选数据源、用途、优先级和接入方式。默认不将大型第三方原始数据直接提交到本仓库；优先保存来源、许可证、下载说明和适配计划。

## 1. 结论

`Mengqi97/chinese-medical-dataset` 更适合作为“中文医学数据集索引/调研入口”，不是单一可直接用于本项目的统一数据集。

本项目当前最相关的方向分为：
1. RAG 文本语料与检索评测
2. 中医实体识别
3. 中医问答评测
4. 症状—证候关系评测
5. 知识图谱数据

当前优先顺序建议：
- P0：TCM-QG
- P0：现有团队实体/关系数据
- P1：TCM-NER
- P1：TCM-QA
- P1：TCM-SD
- P2：KUAKE-IR
- P2：TCM-MKG
- P2：Huatuo-26M / Huatuo-Lite
- P2：ShenNong-TCM-Dataset
- P3：ZhongJing-TCM-Benchmark

---

## 2. 从 chinese-medical-dataset 中筛出的相关数据

### 2.1 TCM-QG — 中医文献问题生成数据集

**优先级：P0**

来源：
- 索引：https://github.com/Mengqi97/chinese-medical-dataset
- 数据页：https://tianchi.aliyun.com/dataset/86895

用途：
- RAG 文本语料候选
- query / answer 对构造
- 检索结果评测
- 文本切分实验
- 证据片段生成

特点：
- 约 3500 篇语料
- 约 5881 条问答标注
- 文本来源包括《黄帝内经翻译版》、名医百科中医篇、中成药用药资料、慢性病养生保健科普知识等
- 答案来自原文连续片段，适合检索—证据对齐

接入建议：
- 不直接覆盖当前 Mock 文档
- 下载后转换为统一 chunk 格式

示例内部格式：

```json
{
  "chunk_id": "TCMQG_000001",
  "title": "文档标题",
  "content": "切分后的文本片段",
  "source": "TCM-QG",
  "metadata": {
    "doc_id": "原始文档ID"
  }
}
```

许可证/再分发：
- 提交原始数据前必须再次核对数据页许可条款
- 当前仓库只建议提交来源与适配代码，不直接提交原始全量数据

---

### 2.2 TCM-NER — 中药说明书实体识别数据集

**优先级：P1**

来源：
- 索引：https://github.com/Mengqi97/chinese-medical-dataset

用途：
- 改进当前 `extract_entities()`
- 中医实体识别
- 实体类型映射
- 为 GraphRAG 查询实体链接提供候选词典

与本项目统一实体类型的潜在映射：
- 证候 -> `证候`
- 中药功效 -> `功效`
- 药物性味 -> 可作为药材属性
- 人群 -> 禁忌/适用人群
- 药品/中药相关实体 -> `药材` 或扩展类型

注意：
- 不是主要 RAG 文本库
- 更适合实体识别与实体链接

---

### 2.3 KUAKE-IR — 中文医疗段落检索数据集

**优先级：P2**

来源：
- 索引：https://github.com/Mengqi97/chinese-medical-dataset
- CBLUE 数据页：https://tianchi.aliyun.com/dataset/95414

用途：
- 向量检索评测
- BM25 / Vector / Hybrid Retrieval 对比
- Recall@K、MRR、Hit@K 等检索实验

特点：
- 大规模中文医疗段落语料
- 有 query-doc 对应关系
- 适合验证检索器
- 不是专门的中医数据，因此不建议作为本项目核心知识库

---

### 2.4 医疗知识图谱类数据

索引中包括：
- QABasedOnMedicaKnowledgeGraph
- QASystemOnMedicalGraph

**优先级：P2 / 架构参考**

用途：
- 实体/关系文件结构参考
- 图查询方式参考
- Neo4j / 图谱 QA 参考

限制：
- 偏通用医学
- 与本项目“药材、方剂、症状、证候、功效、禁忌、文献”体系不完全一致
- 不建议直接替换团队已有中医实体/关系数据

---

### 2.5 CMB、cMedQA、医疗对话数据

**优先级：P3**

用途：
- 通用中文医学问答补充
- Query 样式扩充
- Agent 对话测试

限制：
- 不是专门中医
- 不适合作为当前 GraphRAG 的主知识库

---

## 3. 其他与本项目高度相关的数据集

### 3.1 TCM-QA-datasets

**优先级：P1**

来源：
https://github.com/yizhen-buaa/TCM-QA-datasets

用途：
- GraphRAG 最终回答评测
- 中医知识与推理问题测试
- 回归测试集

规模：
- 578 单选
- 131 多选
- 96 判断

许可证：
- Apache-2.0

建议：
- 作为 eval 数据
- 不建议直接作为主要 RAG 文本语料

---

### 3.2 TCM-SD / ZY-BERT

**优先级：P1**

来源：
https://github.com/Borororo/ZY-BERT

用途：
- 症状 -> 证候
- 辨证任务评测
- 反向关系查询测试
- 实体/证候召回实验

特点：
- 54,152 条真实临床记录
- 覆盖 148 个证候

许可证：
- CC BY-NC-SA 4.0

注意：
- 非商业限制
- 使用时遵守许可要求

---

### 3.3 TCM-MKG

**优先级：P2**

来源：
https://zenodo.org/records/15395588

用途：
- 知识图谱扩展
- 药材、成分、疾病、靶点等多维关系
- 图谱字段与关系模式参考

特点：
- 结构化表格形式
- 汇集 30+ 数据资源
- 适合成员 1 / 2 与 GraphRAG 联调

建议：
- 当前 member3 不直接全量接入
- 先做字段映射与小样本适配

---

### 3.4 Huatuo-26M / Huatuo-Lite

**优先级：P2**

来源：
https://github.com/FreedomIntelligence/Huatuo-26M

用途：
- 通用中文医疗问答
- 额外 RAG 外部知识
- Query 扩充
- 回答生成测试

特点：
- 2600 万级 QA
- 包含百科、知识库、咨询等来源
- 项目明确展示其可作为 RAG 外部知识

许可证：
- Apache-2.0

限制：
- 数据规模很大
- 不是专门中医
- 不建议当前阶段全量下载或提交 Git

---

### 3.5 ShenNong-TCM-Dataset

**优先级：P2**

来源：
https://github.com/michael-wzhu/ShenNong-TCM-LLM

用途：
- 中医 Query 扩充
- 中医指令数据
- Agent / GraphRAG 问答测试

特点：
- 基于中医药知识图谱构造
- entity-centric self-instruct
- 11 万+中医药指令数据

注意：
- 更偏 SFT / 指令数据
- 不等同于权威事实语料
- 使用和再分发前需核对数据许可条款

---

### 3.6 ZhongJing-TCM-Benchmark

**优先级：P3**

来源：
https://github.com/pariskang/ZhongJing-TCM-Benchmark

用途：
- 中医 LLM / GraphRAG benchmark
- 多类别问题测试
- 回归评测

特点：
- 12,000 个临床相关问题
- 175 个主题
- 9 类中医知识类别
- 单选、多选、开放问题

建议：
- 后期作为评测集
- 不作为主要 RAG 文本库

---

## 4. GraphRAG 架构参考

### 4.1 OpenTCM

来源：
https://arxiv.org/abs/2504.20118

用途：
- GraphRAG 架构参考
- 中医知识图谱 + LLM 结合方式参考
- 图谱证据与文本证据融合参考

注意：
- 论文中的语料/图谱规模不代表可直接自由下载或再分发
- 主要用于架构与方法参考

---

### 4.2 TCMM / TCM Knowledge Graph

来源：
https://github.com/AI-HPC-Research-Team/TCM_knowledge_graph

用途：
- 大规模中医知识图谱处理流程参考
- 实体/关系模式参考
- 数据融合流程参考

特点：
- 20 类实体
- 46 类关系
- 3,447,023 条记录

注意：
- 项目依赖多个外部数据库
- 不能默认所有上游数据都允许重新分发

---

## 5. 当前 member3 的接入计划

### 阶段 A：当前

保留：
- `member3/data/entities.json`
- `member3/data/relations.json`
- `member3/data/docs/`

用途：
- Mock MVP
- FastAPI 联调
- DeepSeek 融合生成
- GraphRAG 流程验证

### 阶段 B：下一步

优先接入：
1. TCM-QG 小样本文本
2. 真实 Embedding
3. Milvus
4. TCM-QA 评测
5. TCM-SD 症状—证候测试

### 阶段 C：团队整合

接入：
- 团队 `entities_relations` 分支
- 统一共享图谱
- GraphRAG 查询接口
- Agent / 前端联调

---

## 6. Git 仓库建议

当前提交：
- 本调研文档
- 数据适配代码
- 小型、可再分发的示例数据
- `.env.example`
- 数据来源说明

当前不要提交：
- 大型第三方原始数据集
- 未明确允许再分发的数据
- `.env`
- DeepSeek API Key
- Milvus 本地数据库文件
- 下载缓存

建议目录：

```text
member3/
├── app/
├── data/
│   ├── docs/
│   ├── entities.json
│   └── relations.json
├── DATASETS.md
├── README.md
└── requirements.txt
```

## 7. 最终推荐

对于当前四周课程项目，最现实的组合是：
- 图谱：团队成员整理的 entities / relations
- RAG 文本：TCM-QG 优先
- 实体识别：TCM-NER 作为后续增强
- 评测：TCM-QA + TCM-SD
- 检索器实验：KUAKE-IR
- 扩展知识图谱：TCM-MKG
- 通用医疗补充：Huatuo-Lite
