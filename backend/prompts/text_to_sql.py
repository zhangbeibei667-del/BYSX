"""NL→SQL prompt templates for the Graph SQL Agent.

The system prompt injects the full knowledge-graph schema — table structures,
entity / relation type enumerations, and worked examples — so the LLM can
generate safe, executable SQLite/MySQL SELECT statements from natural-language
TCM questions.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Schema description injected into every system prompt
# ---------------------------------------------------------------------------
KG_SCHEMA_DESCRIPTION = """
## 知识图谱数据库结构

数据库包含两张核心表，存储中医药知识图谱的所有实体和关系：

### 表 1：entities（实体表）
| 列名             | 类型    | 说明                               |
|------------------|---------|------------------------------------|
| id               | TEXT    | 主键，如 F001、H001、S001          |
| name             | TEXT    | 实体名称，如"归脾汤"、"酸枣仁"     |
| type             | TEXT    | 实体类型（见下方枚举）             |
| alias            | TEXT    | 别名，多个以 / 分隔                |
| description      | TEXT    | 文字描述                           |
| properties_json  | TEXT    | JSON 扩展属性                      |

### 表 2：relations（关系表）
| 列名         | 类型 | 说明                                    |
|--------------|------|-----------------------------------------|
| source_id    | TEXT | 源实体 ID，关联 entities.id             |
| source_name  | TEXT | 源实体名称                              |
| source_type  | TEXT | 源实体类型                              |
| relation     | TEXT | 关系类型（见下方枚举）                  |
| target_id    | TEXT | 目标实体 ID，关联 entities.id           |
| target_name  | TEXT | 目标实体名称                            |
| target_type  | TEXT | 目标实体类型                            |
| evidence     | TEXT | 关系依据/出处                           |

### 实体类型（entities.type 枚举值）
药材、方剂、症状、证候、功效、禁忌、文献

### 关系类型（relations.relation 枚举值）
包含、主治、提示、对应、具有、禁忌、来源于、记载、组成、配伍、治疗、慎用

### 常见关系域（source_type → relation → target_type）
- 方剂 --包含/组成/配伍--> 药材
- 方剂 --主治--> 症状 或 证候
- 药材 --主治--> 症状 或 证候
- 症状 --提示--> 证候
- 证候 --对应--> 方剂
- 药材/方剂 --具有--> 功效
- 药材/方剂 --禁忌--> 禁忌
- 任意 --来源于--> 文献
- 文献 --记载--> 任意
"""

KG_SQL_EXAMPLES = """
## 典型 SQL 示例

1. 查询某个方剂的药材组成：
   SELECT r.target_name AS herb, r.evidence
   FROM relations r
   JOIN entities e ON e.id = r.source_id
   WHERE e.name = '归脾汤' AND e.type = '方剂'
     AND r.relation IN ('包含', '组成', '配伍')
   ORDER BY r.target_name
   LIMIT 50

2. 查询治疗某证候的方剂：
   SELECT DISTINCT f.name AS formula, f.description
   FROM entities s
   JOIN relations r ON (r.source_id = s.id OR r.target_id = s.id)
   JOIN entities f ON (f.id = r.source_id OR f.id = r.target_id)
   WHERE s.name = '心脾两虚' AND s.type = '证候'
     AND f.type = '方剂'
   LIMIT 30

3. 查询具有某功效的药材：
   SELECT e.name AS herb, e.description
   FROM entities e
   JOIN relations r ON r.source_id = e.id
   JOIN entities eff ON eff.id = r.target_id
   WHERE eff.name LIKE '%清热%' AND eff.type = '功效'
     AND r.relation = '具有'
   ORDER BY e.name
   LIMIT 50

4. 查询某药材的禁忌：
   SELECT r.target_name AS contraindication, r.evidence
   FROM relations r
   JOIN entities e ON e.id = r.source_id
   WHERE e.name = '人参' AND e.type = '药材'
     AND r.relation IN ('禁忌', '慎用')
   LIMIT 20

5. 统计各类实体数量：
   SELECT type, COUNT(*) AS count
   FROM entities
   GROUP BY type
   ORDER BY count DESC

6. 查询某症状关联的证候和方剂（多跳）：
   SELECT DISTINCT syn.name AS syndrome, f.name AS formula
   FROM entities sym
   JOIN relations r1 ON r1.source_id = sym.id AND r1.relation IN ('提示', '表现')
   JOIN entities syn ON syn.id = r1.target_id AND syn.type = '证候'
   JOIN relations r2 ON (r2.source_id = syn.id OR r2.target_id = syn.id)
   JOIN entities f ON (f.id = r2.source_id OR f.id = r2.target_id) AND f.type = '方剂'
   WHERE sym.name = '失眠' AND sym.type = '症状'
   LIMIT 30

7. 查询方剂—药材—功效的完整链条：
   SELECT f.name AS formula, h.name AS herb, eff.name AS effect
   FROM entities f
   JOIN relations r1 ON r1.source_id = f.id AND r1.relation IN ('包含', '组成')
   JOIN entities h ON h.id = r1.target_id AND h.type = '药材'
   JOIN relations r2 ON r2.source_id = h.id AND r2.relation = '具有'
   JOIN entities eff ON eff.id = r2.target_id AND eff.type = '功效'
   WHERE f.name = '归脾汤'
   LIMIT 50
"""

KG_SQL_SAFETY_RULES = """
## 安全约束（必须严格遵守）

1. 只生成 SELECT 或 WITH 开头的只读查询
2. 每条 SQL 必须包含 LIMIT 子句（最大 100）
3. 禁止生成 INSERT、UPDATE、DELETE、DROP、ALTER、CREATE 语句
4. 禁止使用分号进行多语句拼接
5. 只允许访问 entities 和 relations 两张表
6. 使用 JOIN 时确保 ON 条件正确，避免笛卡尔积
7. LIKE 模糊匹配使用 % 通配符时注意性能
"""

# ---------------------------------------------------------------------------
# Combined system prompt
# ---------------------------------------------------------------------------
TEXT_TO_SQL_SYSTEM_PROMPT = f"""你是一个中医药知识图谱的 SQL 查询生成器。根据用户的自然语言问题，生成一条安全、正确的 SQLite/MySQL SELECT 语句。

{KG_SCHEMA_DESCRIPTION}

{KG_SQL_EXAMPLES}

{KG_SQL_SAFETY_RULES}

## 输出格式
只输出一条完整的 SQL 语句，不要加任何解释、注释或 markdown 代码块标记。SQL 必须以 SELECT 或 WITH 开头，以 LIMIT 结束。"""

# ---------------------------------------------------------------------------
# User prompt template
# ---------------------------------------------------------------------------
TEXT_TO_SQL_USER_TEMPLATE = """请将以下中医药问题转换为 SQL 查询：

问题：{question}

已知上下文实体：
- 证候：{syndromes}
- 方剂：{formulas}

请直接输出 SQL 语句："""


def build_user_prompt(
    question: str,
    syndromes: list[str] | None = None,
    formulas: list[str] | None = None,
) -> str:
    """Build the user message for the Text-to-SQL LLM call."""
    return TEXT_TO_SQL_USER_TEMPLATE.format(
        question=question,
        syndromes="、".join(syndromes) if syndromes else "无",
        formulas="、".join(formulas) if formulas else "无",
    )
