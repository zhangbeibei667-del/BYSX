# Release 验收清单

## 已完成并验证

- ChatAI、CaseStudy、GraphBrowse 不再生成 mock 医疗结论；接口失败明确提示服务不可用或证据不足。
- 智能问答采用真实 SSE；浏览器语音识别、Agent SSE、浏览器语音播放链路已接通。
- 后台路由进入前调用 `/api/kg/auth/me`，且仅 `admin` 角色可进入；后端管理接口再次校验管理员权限。
- 正式知识图谱包含 2,041 个实体、9,357 条关系；重复 ID、重复关系、悬空关系、空证据和非法关系组合均为 0。
- 文献实体 51 个；四类 SQLite 知识库共 1,600 份资料、3,084 个可定位片段。
- RAG 正式评测 120 条；Agent 端到端评测 60 条。
- 独立 Qdrant、MySQL、Neo4j 容器已在本机运行；原 embedded Qdrant 的 9,518 个向量点已校验后迁移。
- 已提供前后端 Dockerfile、完整 Compose、可选 Hybrid profile 和 GitHub Actions 质量门禁。
- 前端生产构建、后端单元测试、图谱管理测试和知识图谱质量门禁通过。

## 发布前必须由项目成员完成

- [ ] 登录阿里云控制台，吊销聊天中暴露过的旧 Key，并生成新 Key。
- [ ] 只将新 Key 写入未跟踪的 `backend/.env`，设置 `LLM_ENABLED=true`。
- [ ] 运行 `python -m backend.scripts.import_rag_corpus_qdrant --reset`，将当前 3,084 个 SQLite
      文档片段和 7,951 条研究语料统一重建为 11,035 个向量点。
- [ ] 复查 `/api/rag/status`：`query_embedding_available=true`、`corpus_fully_indexed=true`。
- [ ] 邀请教师填写 `evaluation/human_review_template.csv` 中至少 20 条，再运行
      `python -m backend.scripts.evaluate_human_review`。
- [ ] 在能访问 Docker Hub 的网络环境执行 `docker compose build`；本机本次验证因
      `python/node/nginx` 基础镜像授权端点连接超时而未完成镜像构建。

没有完成上述外部步骤前，不能在论文或答辩中宣称“真实云 LLM 链路、完整在线向量索引、
教师人工复核、全新机器镜像构建”均已通过。
