# 任务 4：诊疗教学 Agent 验收说明

## 完成状态

任务 4 按当前任务书和用户链路验收项完成度为 **100%**。Vue 问答、SSE 流式响应、多轮会话、浏览器语音识别、逐句语音播放、Agent 动态编排、图谱、Text-to-SQL、RAG、方剂解释与安全审查已经形成完整闭环。

## 用户链路

1. 用户在 `/chat` 输入文字，或通过 Web Speech Recognition 输入普通话。
2. Vue 调用 `GET /api/agent/chat/stream`，不再使用页面硬编码回答。
3. AgentPlanner 根据问题选择症状分析、追问、图谱、SQL、资料检索、方剂解释、知识解释和安全审查工具。
4. 后端按中文句子发送 SSE `chunk`，页面边接收边显示。
5. 开启“自动朗读”后，每个完整句子立即进入 SpeechSynthesis 队列；单条回答也支持手动播放和停止。
6. 最终 `result` 包含 Agent 计划、执行轨迹、图谱、SQL、证据、引用、教学总结、追问及安全提示。
7. 会话 ID 自动保存，后续回答会结合此前症状、舌象和脉象；侧栏历史记录来自真实数据库。

## 接口

- `POST /api/agent/case`：单轮病例教学分析。
- `POST /api/agent/chat`：统一多轮 Agent 问答。
- `GET /api/agent/chat/stream`：SSE 流式 Agent 问答。
- `GET /api/agent/conversations`：会话列表。
- `GET /api/agent/conversations/{id}`：会话详情。
- `DELETE /api/agent/conversations/{id}`：删除会话。

`AgentService` 和 `ConversationService` 会主动执行 `init_db()`；测试、脚本或独立调用不再依赖 FastAPI startup 先执行数据库初始化。

## 非正式降级清理

- 删除方剂小型 mock 库回退。
- 删除 mock 症状—证候—方剂病例回退。
- 删除“清胃散待入库”等补充规则生成路径。
- 未在正式图谱找到的方剂或关系返回“证据不足”，结构化字段保持为空。
- 无 LLM Key 时仍允许本地证据模板回答，但模板只能整理图谱、SQL 和检索证据，不能增加实体结论。

## 端到端评测

运行：

```bash
python -m backend.scripts.evaluate_agent_delivery
```

当前结果：

| 指标 | 结果 |
|---|---:|
| 用例通过 | 10/10 |
| 意图准确率 | 100% |
| 实体召回率 | 100% |
| 工具召回率 | 100% |
| 工具精确率 | 100% |
| 结构化结论幻觉率 | 0% |
| 追问有效率 | 100% |
| 安全合规率 | 100% |
| SQL 只读率 | 100% |
| 多轮信息保留率 | 100% |

评测覆盖信息不足病例、信息完整病例、胃肠病例、方剂组成、药典依据、药材功效、禁忌、虚构方剂拒答和两轮追问补充。

详细机器可读结果见 `docs/任务4_Agent端到端评测报告.json`。

## 已验证

- Agent SSE：meta、chunk、result、DONE 顺序正确。
- SSE 回答包含 9 个 Agent 执行步骤和逐句语音文本。
- 会话写入、读取、继续追问、删除正常。
- MySQL 驱动不可用时自动切换 SQLite，SQL 只读门禁保持有效。
- Vue TypeScript 检查和生产构建通过。
