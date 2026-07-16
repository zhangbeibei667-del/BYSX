基于知识图谱的中医药诊疗智能体

设计任务主要设计参数
核心目标：面向中医药知识学习、方剂查询、症状证候关联分析和教学辅助问答场景，构建知识图谱增强的中医药智能体。系统需支持中药、方剂、症状、证候、功效等实体管理，结合 RAG 与 Agent 实现可解释问答、关系推理、前端展示和后台维护。
任务 1：构建中医药知识图谱，设计药材、方剂、症状、证候、功效、禁忌、文献等实体和关系。
任务 2：实现图谱管理模块，支持实体录入、关系维护、批量导入、图谱检索和可视化展示。
任务 3：实现图谱增强 RAG，将教材、药典条目、方剂说明和科普资料与图谱关系结合生成回答。
任务 4：实现诊疗教学 Agent，调用图谱查询、图谱数据 SQL Agent、文献检索、症状追问、方剂说明、知识解释和流式语音中医药问答工具。
任务 5：实现前端与后台，支持问答、图谱浏览、病例教学输入、药材管理、方剂管理、症状管理和证候管理。

设计内容设计要求
1. 需求分析：梳理中医药知识查询、图谱维护、教学问答和病例学习流程。
2. 架构设计：采用前后端分离架构，后端提供图数据库/关系库管理、检索服务、模型服务和 Agent 服务。
3. 知识图谱实现：完成实体类型、关系类型、属性字段、导入模板和查询接口设计。
4. RAG 实现：将文本资料与图谱实体关联，回答中能够展示相关实体、关系路径和依据片段。
5. 大模型实现：设计药材解释、方剂解释、证候分析、追问建议和学习总结提示词。
6. Agent 实现：封装图谱查询、图谱数据 SQL Agent、资料检索、追问生成、解释生成、流式语音中医药问答和结果整理工具。
7. 前端实现：完成智能问答、图谱可视化、实体详情、病例教学和历史记录页面。
8. 后台实现：完成药材、方剂、症状、证候、病例、资料和问答记录等业务对象管理。

## 启动方式

本地开发：

```powershell
docker compose -f docker-compose.storage.yml up -d
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
cd frontend
npm ci
npm run dev
```

浏览器访问 `http://127.0.0.1:3000`。正式容器化部署使用：

```powershell
Copy-Item backend/.env.example backend/.env
# 在 backend/.env 中填写新生成的密钥，不要提交该文件
docker compose up -d --build
```

默认启动前端、统一后端和独立 Qdrant。需要同时启动 MySQL 与 Neo4j 时使用
`docker compose --profile hybrid up -d --build`，并将 `STORE_BACKEND` 设置为 `hybrid`。

## 发布质量检查

```powershell
python -m backend.scripts.check_kg_quality
python -m backend.scripts.build_extended_evaluation_sets
python -m backend.scripts.evaluate_rag_formal
python -m backend.scripts.evaluate_agent_delivery
cd frontend
npm run build
```

GitHub Actions 会执行后端测试、前端构建、悬空关系检查、RAG/Agent 评测、密钥扫描和
Compose 配置检查。教师复核请填写 `evaluation/human_review_template.csv`，再运行
`python -m backend.scripts.evaluate_human_review`。

## 密钥规则

- 仓库只提交 `.env.example`，真实密钥只放在被 Git 忽略的 `backend/.env`。
- 聊天或日志中暴露过的 Key 必须在云控制台吊销后重新生成，不能仅从文件中删除。
- 新 Key 配置完成后运行 `python -m backend.scripts.import_rag_corpus_qdrant --reset`，
  使 SQLite 文档块和 7,951 条研究语料全部使用同一向量模型重建索引。
