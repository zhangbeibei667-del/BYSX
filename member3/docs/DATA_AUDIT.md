# TCM GraphRAG 数据审计与清洗报告

## 1. 输入数据

### TCM-QG
- 原始记录数：5881
- 清洗后 RAG chunk 数：5881
- 唯一 ID 数：5881
- 问答标注总数：18478
- 空文本数：0
- 答案无法在清洗后原文中精确定位：19

处理策略：
- ID 统一转字符串
- 去除 BOM / 零宽字符
- 规范换行、Tab、重复空白
- 去除首尾异常 ASCII 双引号
- 一条原始 `text` 保留为一个 chunk
- Q/A 保留在 metadata
- 不因少量答案对齐问题删除原始文献文本

### TCM-SD
ZIP 内文件：
- train.json：43180 条
- dev.json：5486 条
- syndrome_knowledge.json：1027 条
- syndrome_vocab.txt：148 个标准证候

质量检查：
- train 标准证候数：148
- dev 标准证候数：148
- train/dev 共享 user_id：19
- train 内完全重复病例签名（重复余量）：4328
- dev 内完全重复病例签名（重复余量）：318
- 清洗后 dev 评测记录数：5168

## 2. 关键设计决定

### 主 RAG 语料
使用：
1. TCM-QG 文献文本
2. TCM-SD `syndrome_knowledge.json`

原因：
- TCM-QG 适合文献检索与证据召回
- syndrome_knowledge 是结构化证候知识，适合 GraphRAG 文本侧补充
- TCM-SD train/dev 是病例记录，不直接混入知识库，避免“病例语料”和“知识语料”混杂

### 评测数据
使用：
- TCM-SD dev
- 已删除 `user_id`
- 已去完全重复病例
- 保留标准证候标签用于后续检索/回答评测

## 3. 输出文件

- `tcm_qg_chunks_clean.jsonl`
  - TCM-QG 清洗后的 RAG chunk
- `tcm_sd_syndrome_knowledge_clean.jsonl`
  - TCM-SD 证候知识 RAG chunk
- `rag_corpus_clean.jsonl`
  - 两者合并后的主 RAG corpus
- `tcm_sd_dev_eval_clean.jsonl`
  - 去 user_id、去重复后的评测集
- `tcm_qg_alignment_issues.jsonl`
  - 少量 Q/A 无法精确对齐原文的问题清单
- `clean_tcm_rag_data.py`
  - 可重复执行的清洗脚本

## 4. 下一步

推荐直接：
1. 对 `rag_corpus_clean.jsonl` 生成 Embedding
2. 写入 Milvus
3. 将当前 Hash `VectorSearch` 替换为 Milvus 检索
4. 用 `tcm_sd_dev_eval_clean.jsonl` 做回归测试

主语料 chunk 总数：7951
