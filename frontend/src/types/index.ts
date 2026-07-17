// 统一关系格式
export interface GraphRelation {
  source_id: string
  source_name: string
  relation: '包含' | '主治' | '提示' | '对应' | '具有' | '禁忌' | '来源于' | '记载'
  target_id: string
  target_name: string
  evidence?: string
}

// 统一图谱节点格式
export interface GraphNode {
  id: string
  label: string
  type: '药材' | '方剂' | '症状' | '证候' | '功效' | '禁忌' | '文献'
  properties?: Record<string, any>
}

// 统一图谱边格式
export interface GraphEdge {
  source: string
  target: string
  label: string
  properties?: Record<string, any>
}

// 统一图谱返回格式
export interface GraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

// 问答证据格式
export interface AnswerEvidence {
  title: string
  content: string
  citation?: string
  source?: string
}

export interface ClinicalDimension {
  label: string
  values: string[]
  observed: boolean
  confidence: 'self_reported' | 'low' | 'missing' | string
}

export interface DifferentialEvidence {
  candidate: string
  source_title: string
  support: string[]
  differences: string[]
  missing: string[]
}

// 统一问答结果格式
export interface AnswerResponse {
  answer: string
  symptoms: string[]
  syndromes: string[]
  formulas: string[]
  herbs: string[]
  graph: GraphResponse
  evidence: AnswerEvidence[]
  follow_up_questions: string[]
  needs_clarification?: boolean
  safety_notice: string
  sources?: SourceItem[]  // RAG 引用资料来源
  answer_mode?: 'concise' | 'teaching' | 'deep'
  evidence_confidence?: string
  generation?: {
    mode: string
    provider?: string
    model?: string
    calls?: number
  }
  agent_plan?: {
    agent?: string
    tools: string[]
    evidence_fusion?: string
    intent?: string
    planner?: string
    reason?: string
    model?: string
  }
  agent_steps?: Array<{
    name: string
    status: 'completed' | 'awaiting_input' | 'insufficient' | string
    summary: string
    output?: any
  }>
  sql_result?: {
    rows?: Array<Record<string, any>>
    row_count?: number
    status?: string
    read_only?: boolean
    text_to_sql?: {
      question?: string
      generated_sql?: string
      rows?: Array<Record<string, any>>
      row_count?: number
      status?: string
      generator?: string
      model_used?: string
    }
  }
  formula_explanations?: Array<{
    name: string
    composition: string[]
    effects: string[]
    main_indications: string[]
    notes: string
  }>
  voice_qa?: {
    enabled?: boolean
    mode?: string
    asr?: { engine?: string; language?: string; interim_results?: boolean }
    tts?: { engine?: string; language?: string; stream_by_sentence?: boolean }
    streaming_text?: string[]
  }
  evidence_summary?: {
    graph_relations: number
    knowledge_base_documents: number
    sources_available: number
  }
  clinical_dimensions?: Record<string, ClinicalDimension>
  differential_evidence?: DifferentialEvidence[]
}

// RAG 引用来源项
export interface SourceItem {
  title?: string         // 文献标题
  type?: string          // 文献类型（药典/教材/古籍/科普/期刊）
  source_detail?: string // 来源详情
  original_text?: string // 原文片段
  chapter?: string       // 页码/章节
  score?: number | null
  metric_label?: string
  status_label?: string
  contains_treatment?: boolean
  related_entities?: Array<{  // 关联实体列表
    id: string
    name: string
    type: string
  }>
}

// 实体类型
export type EntityType = 'herb' | 'prescription' | 'symptom' | 'syndrome' | 'document'

// 实体基类
export interface BaseEntity {
  id: string
  name: string
  description?: string
  createdAt: string
  updatedAt: string
}

// 药材实体
export interface HerbEntity extends BaseEntity {
  category: string
  properties: {
    nature_and_flavor: string // 性味
    channel_tropism: string // 归经
    efficacy: string // 功效
    indications: string // 主治
    usage_dosage: string // 用法用量
    contraindications: string // 禁忌
    processing_method?: string // 炮制方法
  }
}

// 方剂实体
export interface PrescriptionEntity extends BaseEntity {
  category: string
  properties: {
    composition: string // 组成
    preparation: string // 制法
    functions: string // 功用
    indications: string // 主治
    usage_dosage: string // 用法用量
    contraindications: string // 禁忌
    modern_application?: string // 现代应用
  }
}

// 症状实体
export interface SymptomEntity extends BaseEntity {
  category: string
  properties: {
    body_part?: string // 部位
    nature?: string // 性质
    associated_symptoms?: string // 伴随症状
    differentiation?: string // 辨证要点
  }
}

// 证候实体
export interface SyndromeEntity extends BaseEntity {
  category: string
  properties: {
    pathogenesis?: string // 病机
    clinical_manifestations?: string // 临床表现
    treatment_principle?: string // 治则
    commonly_used_formulas?: string // 常用方剂
  }
}

// 文献实体
export interface DocumentEntity extends BaseEntity {
  type: '药典' | '教材' | '古籍' | '科普' | '期刊' // 文献类型
  content: string // 文献内容
  source?: string // 来源出处
  source_detail?: string // 来源详情（如"《中国药典》2020版 第一卷"）
  original_text?: string // 原文片段（RAG回答中展示使用）
  chapter?: string // 页码/章节（如"P123"或"第五章"）
  fileName?: string // 附件文件名
  fileUrl?: string // 附件URL
  relatedEntities?: Array<{
    id: string
    name: string
    type: string
  }> // 关联的图谱实体
}

// 问答记录实体
export interface RecordEntity {
  id: string
  question: string // 用户问题
  answer: string // Agent回答
  herbs?: string[] // 关联药材
  formulas?: string[] // 关联方剂
  symptoms?: string[] // 关联症状
  syndromes?: string[] // 关联证候
  evidence?: Array<{
    title: string
    content: string
  }> // 引用文献片段
  isFavorite: boolean // 是否收藏
  createdAt: string // 提问时间
}
