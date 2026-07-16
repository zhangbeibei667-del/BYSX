# 中医药知识图谱管理模块 (Task 2)

## 目录结构

```
server/
├── main.py              # FastAPI 入口，路由注册，CORS，静态文件挂载
├── config.py            # 配置中心：4 种存储后端切换，MySQL/Neo4j 连接，JWT 密钥
├── api.py               # HTTP 接口层：RESTful 路由，统一 {code, msg, data} 响应
├── auth.py              # JWT 鉴权：签发/验证/过期，bcrypt 密码哈希，admin/user 角色
├── schemas.py           # 数据契约：Entity/Relation/GraphData 模型，动态类型发现与校验
├── service.py           # 业务逻辑：实体/关系校验、ID 分配、批量导入合并、图谱查询、审计
├── store_base.py        # 存储抽象：GraphStore ABC 接口 + 默认实现（replace_relation 等）
├── store_memory.py      # 内存存储：JSON 文件持久化，零依赖，开发/测试用
├── store_mysql.py       # MySQL 实现：InnoDB 事务，递归 CTE 图查询，审计日志，用户管理
├── store_neo4j.py       # Neo4j 实现：Cypher 图遍历，UNWIND 批量写入
├── store_hybrid.py      # 混合存储：MySQL + Neo4j 双写，两阶段提交，读写分离路由
├── graph_tools.py       # 对内工具：search_entities / get_subgraph / explain_path 等函数
├── import_data.py       # 一键导入：读取 entities/ 和 relations/ 下 CSV/JSON 批量入库
├── init_admin.py        # 管理员初始化：启动时自动创建 admin 账号
├── test_functional.py   # 功能测试：35 个用例覆盖 CRUD/图谱/导入/HybridStore 事务
├── API文档.md           # 详细 API 文档（含请求/响应示例）
└── README.md            # 本文件
```

## 架构

```
api.py (HTTP 接口层) → service.py (业务逻辑层) → store_*.py (存储层)
        ↕                       ↕
     auth.py              graph_tools.py (对内工具)
```

| 层 | 文件 | 职责 |
|----|------|------|
| HTTP 接口 | `api.py` | RESTful 路由，统一 `{code, msg, data}` 响应，JWT 鉴权 |
| 认证 | `auth.py` | JWT 签发/验证，bcrypt 密码哈希，admin/user 角色 |
| 业务逻辑 | `service.py` | 实体/关系校验、ID 分配、批量导入、图谱格式转换、审计日志 |
| 数据模型 | `schemas.py` | Pydantic 实体/关系/图谱契约，动态类型发现，自动 ID 前缀 |
| 存储抽象 | `store_base.py` | `GraphStore` ABC 接口 |
| MySQL | `store_mysql.py` | 关系库实现，递归 CTE 图查询，操作审计，用户管理 |
| Neo4j | `store_neo4j.py` | 图数据库实现，Cypher 图遍历，UNWIND 批量写入 |
| 混合存储 | `store_hybrid.py` | MySQL+Neo4j 双写，两阶段提交，读写分离 |
| 内存存储 | `store_memory.py` | 零依赖开发/测试用 |
| 配置 | `config.py` | 环境变量驱动，4 种后端可切换 |
| 工具 | `graph_tools.py` | 对内暴露的图谱查询函数，支持进程内调用和 HTTP 调用 |
| 导入 | `import_data.py` | 一键从 `entities/` `relations/` 导入 CSV/JSON |
| 可视化 | `../view/graph_viewer.html` | ECharts 力导向图，完整管理控制台 |

## 实体类型与关系类型

### 实体类型（10 种）（颜色仅用于我用于测试的图谱可视化页面

| 类型 | ID前缀 | 颜色 | 数量 |
|------|--------|------|------|
| 药材 | H | `#5e8c61` | 705 |
| 方剂 | F | `#b4763f` | 100 |
| 症状 | S | `#a8443a` | 260 |
| 证候 | Z | `#4a6fa5` | 262 |
| 功效 | G | `#7a6ba8` | 100 |
| 禁忌 | J | `#3f4a52` | 288 |
| 文献 | W | `#8a8256` | 15 |
| 疾病 | D | `#8b5a9e` | 80 |
| 归经 | — | `#2e8b7b` | 12 |
| 性味 | — | `#c8873a` | 24 |

> 新增实体类型自动分配 ASCII 字母前缀和颜色，无需改代码。

### 关系类型（9 种）

| 关系 | 典型用法 |
|------|---------|
| 包含 | 方剂→药材 |
| 主治 | 方剂/药材→症状/证候/疾病 |
| 提示 | 症状→证候 |
| 对应 | 证候→方剂 |
| 具有 | 药材/方剂→功效 |
| 禁忌 | 药材/方剂→禁忌/证候 |
| 来源于 | 实体→文献 |
| 记载 | 文献→实体 |
| 归经 | 药材/方剂→归经 |

> 新关系类型和组合自动接受（打印一次警告，不拒绝）。

## API 接口

Base URL: `http://localhost:8000/api`

### 认证

| 方法 | 路径 | 权限 |
|------|------|------|
| POST | `/auth/register` | 无 |
| POST | `/auth/login` | 无 |
| GET | `/auth/me` | 登录 |
| POST | `/auth/change-password` | 登录 |

### 元数据 & 统计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/meta` | 实体类型、关系类型、关系域约束 |
| GET | `/stats` | 实体/关系计数，按类型分布 |

### 实体 CRUD

| 方法 | 路径 | 权限 |
|------|------|------|
| GET | `/entities?type=&keyword=&page=&size=` | 登录 |
| GET | `/entities/{id}` | 登录 |
| POST | `/entities` | admin |
| PUT | `/entities/{id}` | admin |
| DELETE | `/entities/{id}` | admin |
| DELETE | `/entities/batch` | admin |

### 关系 CRUD

| 方法 | 路径 | 权限 |
|------|------|------|
| GET | `/relations?source_id=&relation=&page=&size=` | 登录 |
| POST | `/relations` | admin |
| PUT | `/relations?old_source=&old_relation=&old_target=` | admin |
| DELETE | `/relations?source_id=&relation=&target_id=` | admin |
| DELETE | `/relations/batch` | admin |

### 图谱检索

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/graph/subgraph?id=&depth=&limit=` | 从实体展开子图 |
| GET | `/graph/neighbors?id=&relation=&limit=` | 单跳邻居 |
| GET | `/graph/search?keyword=&type=&depth=` | 关键词搜索 |
| GET | `/graph/path?source_id=&target_id=&max_depth=` | 路径查询 |

### 导入导出

| 方法 | 路径 | 权限 |
|------|------|------|
| GET | `/import/template?kind=entity` | 登录 |
| GET | `/import/template?kind=relation` | 登录 |
| POST | `/import/entities` | admin |
| POST | `/import/relations` | admin |

### 审计 & 回滚

| 方法 | 路径 | 权限 |
|------|------|------|
| GET | `/admin/audit-log?user_id=&action=&page=&size=` | 登录 |
| GET | `/admin/audit-log/{log_id}` | 登录 |
| POST | `/admin/rollback/{log_id}` | admin |
| POST | `/admin/rollback-batch` | admin |
| GET | `/admin/import-batches?page=&size=` | 登录 |

### 用户管理

| 方法 | 路径 | 权限 |
|------|------|------|
| GET | `/admin/users` | admin |
| POST | `/admin/users` | admin |

## 配置

通过环境变量控制：

```bash
# 存储后端: memory | mysql | neo4j | hybrid (默认)
STORE_BACKEND=hybrid

# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=tcm

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# JWT
JWT_SECRET=your_random_secret
JWT_EXPIRE_HOURS=24
```

## 运行

### 1. 启动 MySQL 和 Neo4j

### 2. 导入数据

```bash
# 确保 entities/ 和 relations/ 目录在项目根目录
python -m server.import_data
```

### 3. 启动服务

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 访问

| 地址 | 说明 |
|------|------|
| `http://localhost:8000/graph` | Vue 图谱浏览 |
| `http://localhost:8000/admin/relations` | Vue 关系管理 |
| `http://localhost:8000/kg-viewer` | 独立完整图谱管理器 |
| `http://localhost:8000/docs` | Swagger 交互文档 |
| `http://localhost:8000/api/health` | 健康检查 |

默认管理员用户名为 `admin`。首次启动若未设置 `ADMIN_PASSWORD`，随机初始密码保存在 `data/.admin_initial_password`。
