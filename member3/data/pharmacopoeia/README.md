# 中药材标准资料库

本目录用于存放 GraphRAG 系统的中药材标准资料库。

当前阶段优先接入香港中药材标准 HKCMMS。该资料库独立于现有 TCM-QG、TCM-SD 文本库和知识图谱数据，用于补充中药材来源、鉴别、检查、含量测定、标准说明等权威辅助资料。

## 数据来源

- 香港中药材标准 HKCMMS
- 发布单位：香港特别行政区政府卫生署中医药规管办公室
- 数据类型：公开中药材标准条目 PDF
- 用途：毕业设计/课程项目中的检索增强与可追溯证据补充

## 数据边界

原始 PDF 文件仅用于本地处理，不提交到公开仓库。仓库中只保留清洗脚本、来源清单、字段结构和必要样例。

## 与现有系统的关系

本资料库不会改变现有 GraphRAG 对外返回格式。系统仍然返回 answer、symptoms、syndromes、formulas、herbs、graph、evidence、follow_up_questions、safety_notice 等字段。

HKCMMS 检索结果将作为 evidence 的补充来源，不新增对外实体类型和关系类型。

## 当前处理状态

- 已生成原始清洗结果：`processed/hkcmms/chunks.jsonl`
- 已生成安全入库集：`processed/hkcmms/index_ready/chunks_for_index.jsonl`
- 已生成 Milvus 增量语料：`processed/hkcmms/index_ready/chunks_for_milvus.jsonl`
- 可入库 chunk 数：1094
- 待人工复核 chunk 数：12

导入当前 RAG：

```powershell
python scripts/milvus_insert.py `
  --input data/pharmacopoeia/processed/hkcmms/index_ready/chunks_for_milvus.jsonl `
  --limit 0
```

每条 HKCMMS evidence 会保留章节、页码、引用、原始 PDF 相对路径和官方 URL，便于回溯核验。
