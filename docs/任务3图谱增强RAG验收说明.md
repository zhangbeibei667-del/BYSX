# 任务 3：图谱增强 RAG 验收说明

## 完成状态

任务 3 按当前设计任务书及既定验收项完成度为 **100%**。正式在线入口统一为 `backend.services.rag_service.RAGService`，member3 仅保留语料清洗、Milvus 导入、离线实验和旧接口兼容功能。

## 统一服务与接口

- `POST /api/rag/search`：图谱增强 RAG 检索与回答。
- `GET /api/rag/quality`：图谱、语料、向量库质量报告。
- `GET /api/rag/status`：SQLite、Qdrant、Milvus、LLM 的真实运行状态。
- `POST /api/graphrag/query`：member3 旧接口，由兼容适配器转发到统一 RAGService。

回答包含相关实体、图谱边、`reasoning_paths`、文本证据、引用、证据等级和 `evidence_confidence_score`。关系型问题若没有目标关系，或问题主体不在正式图谱中，返回“证据不足”，不会调用 mock 规则补结论。

## 四类正式语料

SQLite 首次启动自动初始化，初始化过程幂等：

| 类别 | 文档 | 分块 | 来源与可追溯方式 |
|---|---:|---:|---|
| 教材 | 1 | 100 | 方剂学实体、关系及关系证据 |
| 药典 | 1 | 705 | 中药实体、文献关系及药典来源索引 |
| 方剂说明 | 1 | 100 | 方剂组成、主治、来源关系 |
| 科普资料 | 1 | 662 | 证候、功效、禁忌关系生成的知识卡 |

正式源文件同时纳入完整性校验：

- `member3/data/processed/rag_corpus_clean.jsonl`：7,951 条；
- `member3/data/pharmacopoeia/processed/hkcmms/index_ready/chunks_for_milvus.jsonl`：1,094 条；
- 状态报告保存文件大小、记录数和 SHA-256，能够检测源文件被替换或损坏。

## 检索后端状态

- SQLite 本地向量混合检索：ready；始终可用。
- Qdrant embedded-local：ready；集合 `tcm_documents_v3`，1,568 个向量点，384 维 hash-bigram-v1，无需下载模型。
- Milvus：当前环境未启用，状态明确为 `disabled`；1,094 条可导入产物已经验证存在。设置 `MILVUS_ENABLED=true` 后，状态接口会连接服务、检查 collection 和实际 row_count。
- LLM：当前环境未配置 Key，状态明确为 `disabled`；系统使用有引用的本地证据回答，不生成无依据结论。

这里的“100%”表示所有功能均有可运行实现、自动初始化、状态检查和本地完整降级链路；不把未配置的外部服务伪报为已部署。

## 评测

运行：

```bash
python -m backend.scripts.evaluate_rag_delivery
```

评测集 `evaluation/rag_delivery_eval.jsonl` 共 20 条，当前通过 20 条，通过率 100%。详细结果见 `docs/任务3_RAG评测报告.json`。

## 复现命令

```bash
python -m backend.scripts.build_classified_corpus
python -m backend.scripts.reindex_document_vectors
python -m backend.scripts.evaluate_rag_delivery
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
