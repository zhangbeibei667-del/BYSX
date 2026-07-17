<template>
  <div :class="['chat-bubble', `role-${message.role}`]">
    <!-- 消息头部 -->
    <div class="message-header">
      <div class="avatar">
        <el-icon v-if="message.role === 'user'" :size="20"><User /></el-icon>
        <el-icon v-else :size="20"><Service /></el-icon>
      </div>

      <div class="header-info">
        <span class="username">{{ message.role === 'user' ? '我' : '中医药智能体' }}</span>
        <span class="timestamp">{{ formatTime(message.timestamp) }}</span>
      </div>
      <div class="header-actions">
        <el-button
          v-if="message.role === 'assistant' && message.response"
          type="info"
          link
          size="small"
          @click="toggleExpand"
        >
          <el-icon>
            <Expand v-if="!expanded" />
            <Fold v-else />
          </el-icon>
          {{ expanded ? '收起' : '详情' }}
        </el-button>
        <el-button
          v-if="message.role === 'assistant' && !message.loading"
          type="primary"
          link
          size="small"
          @click="handleCopy"
        >
          <el-icon><CopyDocument /></el-icon>
          复制
        </el-button>
        <el-button
          v-if="message.role === 'assistant' && !message.loading"
          type="warning"
          link
          size="small"
          @click="handleFavorite"
        >
          <el-icon>
            <StarFilled v-if="message.favorite" />
            <Star v-else />
          </el-icon>
          {{ message.favorite ? '已收藏' : '收藏' }}
        </el-button>
      </div>
    </div>
    
    <!-- 消息内容 / 加载状态 同级平级 -->
    <div v-if="!message.loading" class="message-content">
      <div class="content-text" v-html="renderedContent" />
    </div>
    <div v-else class="loading-content">
      <!-- 加载状态 -->
      <div class="loading-dots">
        <span></span>
        <span></span>
        <span></span>
      </div>
    </div>

    <div
      v-if="message.role === 'assistant' && message.response?.needs_clarification && message.response.follow_up_questions?.length"
      class="inline-followups"
    >
      <div class="inline-followups-title">为了进一步辨证，请补充：</div>
      <el-button
        v-for="(question, index) in message.response.follow_up_questions"
        :key="`inline-question-${index}`"
        type="info"
        plain
        size="small"
        @click="handleFollowUp(question)"
      >
        {{ question }}
      </el-button>
    </div>

    <!-- RAG 依据来源面板 -->
    <div
      v-if="message.role === 'assistant' && hasSources"
      class="sources-panel"
    >
      <el-collapse v-model="activeSourceNames">
        <el-collapse-item name="sources">
          <template #title>
            <span class="sources-title">
              <el-icon><Document /></el-icon>
              <span>查看依据</span>
            </span>
          </template>
          <div v-if="message.response?.generation" class="generation-meta">
            <span>回答方式：{{ answerModeLabel }}</span>
            <span v-if="message.response.generation.model">
              生成模型：{{ message.response.generation.model }}
            </span>
            <span v-if="message.response.evidence_confidence">
              证据强度：{{ confidenceLabel }}
            </span>
          </div>
          <div
            v-for="(source, idx) in displaySources"
            :key="`source-${idx}`"
            class="source-item"
          >
            <div class="source-header">
              <el-tag
                :type="getSourceTypeColor(source.type)"
                size="small"
                effect="dark"
              >
                {{ source.type || '文献' }}
              </el-tag>
              <span class="source-title">{{ source.title || '未命名文献' }}</span>
            </div>

            <div class="source-meta" v-if="source.source_detail || source.chapter">
              <span v-if="source.source_detail" class="source-detail">
                <el-icon><Reading /></el-icon>
                {{ source.source_detail }}
              </span>
              <span v-if="source.chapter" class="source-chapter">
                <el-icon><Location /></el-icon>
                {{ source.chapter }}
              </span>
            </div>

            <blockquote v-if="source.original_text" class="source-quote">
              {{ source.original_text }}
            </blockquote>

            <el-alert
              v-if="source.contains_treatment"
              class="source-treatment-notice"
              title="原文含传统治法或方药记载，仅作证据溯源，不构成对当前用户的治疗建议。"
              type="warning"
              :closable="false"
              show-icon
            />

            <div v-if="source.score !== undefined && source.score !== null" class="source-score">
              {{ source.metric_label || '检索相关度' }}：{{ formatScore(source.score) }}
            </div>
            <div v-else-if="source.status_label" class="source-status">
              证据状态：{{ source.status_label }}
            </div>

            <div
              v-if="source.related_entities && source.related_entities.length"
              class="source-entities"
            >
              <span class="entities-label">关联实体：</span>
              <el-tag
                v-for="(entity, ei) in source.related_entities"
                :key="`entity-${ei}`"
                :type="getEntityColor(entity.type)"
                size="small"
                effect="plain"
                class="entity-clickable"
                @click="handleEntityClick(entity)"
              >
                [{{ entity.type }}] {{ entity.name }}
              </el-tag>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>
    
    <!-- 扩展信息 -->
    <div v-if="expanded && message.response" class="message-expansion">
      <!-- 相关实体 -->
      <div v-if="hasRelatedEntities" class="expansion-section">
        <h4 class="section-title">
          <el-icon><Connection /></el-icon>
          相关实体
        </h4>
        <div class="entities-grid">
          <div v-if="message.response.symptoms.length" class="entity-group">
            <h5>症状</h5>
            <div class="entity-tags">
              <el-tag
                v-for="(symptom, index) in message.response.symptoms"
                :key="`symptom-${index}`"
                type="warning"
                size="small"
              >
                {{ symptom }}
              </el-tag>
            </div>
          </div>
          
          <div v-if="message.response.syndromes.length" class="entity-group">
            <h5>证候</h5>
            <div class="entity-tags">
              <el-tag
                v-for="(syndrome, index) in message.response.syndromes"
                :key="`syndrome-${index}`"
                type="danger"
                size="small"
              >
                {{ syndrome }}
              </el-tag>
            </div>
          </div>
          
          <div v-if="message.response.formulas.length" class="entity-group">
            <h5>方剂</h5>
            <div class="entity-tags">
              <el-tag
                v-for="(formula, index) in message.response.formulas"
                :key="`formula-${index}`"
                type="primary"
                size="small"
              >
                {{ formula }}
              </el-tag>
            </div>
          </div>
          
          <div v-if="message.response.herbs.length" class="entity-group">
            <h5>药材</h5>
            <div class="entity-tags">
              <el-tag
                v-for="(herb, index) in message.response.herbs"
                :key="`herb-${index}`"
                type="success"
                size="small"
              >
                {{ herb }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>

      <div v-if="clinicalDimensionList.length" class="expansion-section">
        <h4 class="section-title">
          <el-icon><Connection /></el-icon>
          四诊信息结构化
        </h4>
        <div class="clinical-dimensions">
          <div
            v-for="dimension in clinicalDimensionList"
            :key="dimension.key"
            class="clinical-dimension"
            :class="{ missing: !dimension.observed }"
          >
            <span class="dimension-label">{{ dimension.label }}</span>
            <span class="dimension-value">
              {{ dimension.observed ? dimension.values.join('、') : '待补充' }}
            </span>
            <el-tag v-if="dimension.confidence === 'low'" size="small" type="warning">低精度自述</el-tag>
          </div>
        </div>
      </div>

      <div v-if="message.response.differential_evidence?.length" class="expansion-section">
        <h4 class="section-title">
          <el-icon><Connection /></el-icon>
          候选证候证据对照
        </h4>
        <div class="differential-grid">
          <div
            v-for="(item, index) in message.response.differential_evidence"
            :key="`differential-${index}`"
            class="differential-card"
          >
            <div class="differential-title">
              <strong>{{ item.candidate }}</strong>
              <span>{{ item.source_title }}</span>
            </div>
            <div class="differential-row support">
              <span>支持</span>
              <p>{{ item.support.length ? item.support.join('、') : '暂无直接支持' }}</p>
            </div>
            <div class="differential-row difference">
              <span>差异</span>
              <p>{{ item.differences.length ? item.differences.join('；') : '未发现同维度冲突' }}</p>
            </div>
            <div class="differential-row missing">
              <span>缺失</span>
              <p>{{ item.missing.length ? item.missing.join('、') : '暂无' }}</p>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 追问建议 -->
      <div v-if="message.response.follow_up_questions?.length" class="expansion-section">
        <h4 class="section-title">
          <el-icon><ChatLineSquare /></el-icon>
          追问建议
        </h4>
        <div class="follow-up-questions">
          <el-button
            v-for="(question, index) in message.response.follow_up_questions"
            :key="`question-${index}`"
            type="info"
            size="small"
            @click="handleFollowUp(question)"
          >
            {{ question }}
          </el-button>
        </div>
      </div>
      
      <div v-if="message.response.agent_steps?.length" class="expansion-section">
        <h4 class="section-title">
          <el-icon><Connection /></el-icon>
          诊疗教学 Agent 执行过程
        </h4>
        <div class="agent-trace">
          <div
            v-for="(step, index) in message.response.agent_steps"
            :key="`agent-step-${index}`"
            class="agent-step"
          >
            <el-tag :type="step.status === 'completed' ? 'success' : step.status === 'awaiting_input' ? 'warning' : 'info'" size="small">
              {{ step.status === 'completed' ? '已完成' : step.status === 'awaiting_input' ? '待补充' : '证据有限' }}
            </el-tag>
            <div>
              <strong>{{ step.name }}</strong>
              <p>{{ step.summary }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- 安全提示 -->
      <div class="expansion-section safety-notice">
        <el-alert
          :title="message.response.safety_notice"
          type="info"
          :closable="false"
          show-icon
        />
      </div>
    </div>
    
    <!-- 语音播放 -->
    <div v-if="message.role === 'assistant' && !message.loading" class="message-actions">
      <el-button
        type="info"
        link
        size="small"
        @click="handleSpeech"
        :loading="speaking"
      >
        <el-icon>
          <VideoPlay v-if="!speaking" />
          <VideoPause v-else />
        </el-icon>
        {{ speaking ? '播放中...' : '语音朗读' }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import MarkdownIt from 'markdown-it'
import {
  User,
  Service,
  Expand,
  Fold,
  CopyDocument,
  Star,
  StarFilled,
  Connection,
  ChatLineSquare,
  Document,
  Reading,
  Location,
  VideoPlay,
  VideoPause
} from '@element-plus/icons-vue'
import type { ClinicalDimension, DifferentialEvidence, SourceItem } from '@/types'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  loading?: boolean
  favorite?: boolean
  response?: {
    symptoms: string[]
    syndromes: string[]
    formulas: string[]
    herbs: string[]
    evidence?: Array<{ title: string; content: string }>
    follow_up_questions?: string[]
    needs_clarification?: boolean
    safety_notice: string
    sources?: SourceItem[]
    answer_mode?: 'concise' | 'teaching' | 'deep'
    evidence_confidence?: string
    generation?: { mode: string; provider?: string; model?: string; calls?: number }
    agent_steps?: Array<{ name: string; status: string; summary: string }>
    clinical_dimensions?: Record<string, ClinicalDimension>
    differential_evidence?: DifferentialEvidence[]
  }
}

interface Props {
  message: Message
}

const props = defineProps<Props>()
const emit = defineEmits<{
  favorite: [id: string]
  followup: [question: string]
  navigateToGraph: [entityName: string]
}>()

// 文献类型 → el-tag type 映射（与 DocManage 保持一致）
const sourceTypeColorMap: Record<string, string> = {
  '药典': 'danger',
  '教材': 'primary',
  '古籍': 'warning',
  '科普': 'info',
  '期刊': 'success',
  '证候知识': 'primary',
  '图谱关系': 'success',
  '图谱实体': 'warning'
}
const getSourceTypeColor = (t?: string): string => sourceTypeColorMap[t || ''] || ''

// 实体类型 → el-tag type 映射
const entityColorMap: Record<string, string> = {
  '药材': 'success',
  '方剂': 'primary',
  '症状': 'danger',
  '证候': 'warning'
}
const getEntityColor = (t?: string): string => entityColorMap[t || ''] || 'info'

const activeSourceNames = ref<string[]>([])

const hasSources = computed(() => {
  return displaySources.value.length > 0 || Boolean(props.message.response?.generation)
})

const displaySources = computed<SourceItem[]>(() => {
  const sources = props.message.response?.sources || []
  if (sources.length) {
    return sources.map(source => {
      const relation = source.type === '图谱关系' || source.original_text?.startsWith('知识图谱关系：')
      const entity = source.type === '图谱实体' || source.source_detail?.startsWith('图谱实体/')
      if (relation) {
        return { ...source, type: '图谱关系', score: null, metric_label: undefined, status_label: '已验证关系' }
      }
      if (entity) {
        return { ...source, type: '图谱实体', score: null, metric_label: undefined, status_label: '命中图谱实体' }
      }
      return { ...source, score: source.score === undefined || source.score === null ? source.score : Math.max(0, Math.min(1, source.score)) }
    })
  }
  return (props.message.response?.evidence || []).map(item => ({
    title: item.title,
    original_text: item.content,
    type: '文献'
  }))
})

const answerModeLabel = computed(() => ({
  concise: '简洁回答',
  teaching: '教学解释',
  deep: '深入分析'
}[props.message.response?.answer_mode || 'concise']))

const confidenceLabel = computed(() => ({
  high: '较高',
  medium: '中等',
  insufficient: '不足'
}[props.message.response?.evidence_confidence || ''] || props.message.response?.evidence_confidence))

const formatScore = (score?: number | null) => {
  if (score === undefined || score === null || !Number.isFinite(score)) return '-'
  return `${Math.round(Math.max(0, Math.min(1, score)) * 100)}%`
}

const handleEntityClick = (entity: { name: string; type: string; id: string }) => {
  emit('navigateToGraph', entity.name)
}

const expanded = ref(false)
const speaking = ref(false)
const md = new MarkdownIt()

const clinicalDimensionList = computed(() => Object.entries(props.message.response?.clinical_dimensions || {}).map(
  ([key, value]) => ({ key, ...value })
))

const hasRelatedEntities = computed(() => {
  const resp = props.message.response
  return resp && (
    resp.symptoms.length > 0 ||
    resp.syndromes.length > 0 ||
    resp.formulas.length > 0 ||
    resp.herbs.length > 0
  )
})

const renderedContent = computed(() => {
  if (props.message.role === 'user') {
    return md.renderInline(props.message.content)
  }
  return md.render(props.message.content)
})

const formatTime = (timestamp: string) => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

const toggleExpand = () => {
  expanded.value = !expanded.value
}

const handleCopy = async () => {
  try {
    await navigator.clipboard.writeText(props.message.content)
    ElMessage.success('已复制到剪贴板')
  } catch (error) {
    console.error('复制失败:', error)
    ElMessage.error('复制失败')
  }
}

const handleFavorite = () => {
  emit('favorite', props.message.id)
}

const handleFollowUp = (question: string) => {
  emit('followup', question)
}

const handleSpeech = () => {
  if (speaking.value) {
    // 停止语音
    speaking.value = false
    window.speechSynthesis.cancel()
  } else {
    // 开始语音
    speaking.value = true
    
    const utterance = new SpeechSynthesisUtterance(props.message.content)
    utterance.lang = 'zh-CN'
    utterance.rate = 0.9
    utterance.pitch = 1
    utterance.volume = 1
    
    utterance.onend = () => {
      speaking.value = false
    }
    
    utterance.onerror = () => {
      speaking.value = false
      ElMessage.error('语音播放失败')
    }
    
    window.speechSynthesis.speak(utterance)
  }
}
</script>

<style scoped lang="scss">
$dark-green: #2a4030;
$mid-green: #466350;
$soft-gold: #c8a86e;
$cream-bg: #f7f3eb;
$text-dark: #2c3630;
$text-body: #46544d;
$text-light: #6b7a72;
$user-green: #f0f6f0;
$user-green-deep: #e7f0e7;
$assistant-white: #fffefb;
$assistant-white-deep: #fbf7ee;

.chat-bubble {
  width: fit-content;
  max-width: min(720px, 74%);
  margin: 16px 0;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid rgba(110, 135, 120, 0.14);
  background: white;
  box-shadow: 0 3px 12px rgba(42, 64, 48, 0.06);
  
  &.role-user {
    margin-left: auto;
    margin-right: 24px;
    background: $user-green;
    border-color: rgba(70, 99, 80, 0.16);

    .message-header {
      background: $user-green-deep;
      border-bottom: 1px solid rgba(70, 99, 80, 0.1);
    }

    .avatar {
      background: rgba(255, 255, 255, 0.78);

      .el-icon {
        color: $mid-green;
      }
    }
  }
  
  &.role-assistant {
    margin-left: 24px;
    margin-right: auto;
    background: $assistant-white;
    border-color: rgba(110, 135, 120, 0.14);

    .message-header {
      background: $assistant-white-deep;
      border-bottom: 1px solid rgba(110, 135, 120, 0.1);
    }

    .avatar {
      background: rgba(255, 255, 255, 0.78);

      .el-icon {
        color: $mid-green;
      }
    }
  }
  
  .message-header {
    padding: 10px 14px;
    display: flex;
    align-items: center;
    gap: 10px;
    
    .avatar {
      width: 30px;
      height: 30px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.82);
      display: flex;
      align-items: center;
      justify-content: center;
      
      .el-icon {
        color: $text-light;
      }
    }
    
    .header-info {
      flex: 1;
      
      .username {
        font-weight: bold;
        color: $text-dark;
        margin-right: 10px;
        font-size: 13px;
      }
      
      .timestamp {
        color: $text-light;
        font-size: 11px;
      }
    }
    
    .header-actions {
      display: flex;
      gap: 8px;
    }
  }
  
  .message-content {
    padding: 13px 15px;
    
    .content-text {
      font-size: 14px;
      line-height: 1.6;
      color: $text-body;
      
      :deep(*) {
        margin: 6px 0;
        
        &:first-child {
          margin-top: 0;
        }
        
        &:last-child {
          margin-bottom: 0;
        }
      }
      
      :deep(h1), :deep(h2), :deep(h3), :deep(h4) {
        color: $dark-green;
        border-bottom: 1px solid rgba(110, 135, 120, 0.14);
        padding-bottom: 8px;
        font-size: 15px;
      }
      
      :deep(ul), :deep(ol) {
        padding-left: 20px;
      }
      
      :deep(code) {
        background: rgba(70, 99, 80, 0.08);
        padding: 2px 6px;
        border-radius: 4px;
        font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Consolas', monospace;
      }
      
      :deep(pre) {
        background: rgba(255, 255, 255, 0.58);
        padding: 12px;
        border-radius: 8px;
        overflow-x: auto;
        
        code {
          background: transparent;
          padding: 0;
        }
      }
    }
    
    .loading-content {
      display: flex;
      justify-content: center;
      align-items: center;
      height: 60px;
      
      .loading-dots {
        display: flex;
        gap: 8px;
        
        span {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: $mid-green;
          animation: loading 1.4s ease-in-out infinite;
          
          &:nth-child(2) {
            animation-delay: 0.2s;
          }
          
          &:nth-child(3) {
            animation-delay: 0.4s;
          }
        }
      }
    }
  }
  
  .sources-panel {
    border-top: 1px solid rgba(110, 135, 120, 0.14);
    padding: 0;

    :deep(.el-collapse) {
      border: none;
      --el-collapse-header-bg-color: transparent;
      --el-collapse-content-bg-color: #fff9ed;
    }

    :deep(.el-collapse-item__header) {
      padding: 14px 20px;
      font-size: 14px;
      font-weight: 500;
      color: $mid-green;
      border: none;
      background: rgba(70, 99, 80, 0.04);
      transition: background 0.2s;

      &:hover {
        background: rgba(70, 99, 80, 0.08);
      }
    }

    :deep(.el-collapse-item__wrap) {
      border: none;
    }

    .sources-title {
      display: inline-flex;
      align-items: center;
      gap: 6px;

      .el-icon {
        font-size: 15px;
        color: $soft-gold;
      }
    }

    :deep(.el-collapse-item__content) {
      padding: 16px 20px;
    }

    .generation-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 18px;
      margin-bottom: 12px;
      padding: 10px 14px;
      border-radius: 8px;
      background: rgba(70, 99, 80, 0.06);
      color: #52645a;
      font-size: 12px;
    }

    .source-item {
      padding: 14px 16px;
      margin-bottom: 12px;
      background: #fff;
      border-radius: 8px;
      border: 1px solid rgba(110, 135, 120, 0.14);
      transition: box-shadow 0.2s;

      &:hover {
        box-shadow: 0 2px 8px rgba(42, 64, 48, 0.06);
      }

      &:last-child {
        margin-bottom: 0;
      }

      .source-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 8px;

        .source-title {
          font-weight: 500;
          color: $text-dark;
          font-size: 14px;
        }
      }

      .source-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        margin-bottom: 8px;
        font-size: 12px;
        color: $text-light;

        .source-detail, .source-chapter {
          display: inline-flex;
          align-items: center;
          gap: 4px;

          .el-icon {
            font-size: 13px;
            color: $soft-gold;
          }
        }
      }

      .source-quote {
        margin: 8px 0 0 0;
        padding: 10px 14px;
        background: rgba(70, 99, 80, 0.04);
        border-left: 3px solid $mid-green;
        border-radius: 4px;
        font-size: 13px;
        line-height: 1.7;
        color: $text-body;
        font-style: italic;
      }

      .source-score, .source-status {
        margin-top: 8px;
        color: #7a887f;
        font-size: 12px;
      }

      .source-treatment-notice {
        margin-top: 10px;

        :deep(.el-alert__title) {
          font-size: 12px;
          line-height: 1.5;
        }
      }

      .source-entities {
        margin-top: 10px;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;

        .entities-label {
          font-size: 12px;
          color: $text-light;
        }

        .entity-clickable {
          cursor: pointer;
          transition: transform 0.15s, box-shadow 0.15s;

          &:hover {
            transform: translateY(-1px);
            box-shadow: 0 1px 4px rgba(42, 64, 48, 0.15);
          }
        }
      }
    }
  }

  .inline-followups {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 0 20px 16px;

    .inline-followups-title {
      flex-basis: 100%;
      color: #52645a;
      font-size: 13px;
      font-weight: 500;
    }

    :deep(.el-button) {
      height: auto;
      max-width: 100%;
      margin-left: 0;
      padding: 7px 10px;
      white-space: normal;
      text-align: left;
      line-height: 1.45;
    }
  }

  .message-expansion {
    border-top: 1px solid rgba(110, 135, 120, 0.14);
    padding: 16px;
    
    .expansion-section {
      margin-bottom: 20px;
      
      &:last-child {
        margin-bottom: 0;
      }
      
      .section-title {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 0 0 12px 0;
        color: $mid-green;
        font-size: 15px;
        
        .el-icon {
          font-size: 18px;
        }
      }
    }
    
    .entities-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      
      .entity-group {
        h5 {
          margin: 0 0 8px 0;
          color: $text-light;
          font-size: 14px;
        }
        
        .entity-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }
      }
    }
    
    .follow-up-questions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .clinical-dimensions {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 8px;

      .clinical-dimension {
        display: flex;
        align-items: center;
        gap: 8px;
        min-height: 38px;
        padding: 8px 10px;
        border: 1px solid #dfe8e2;
        border-radius: 7px;
        background: #f7faf8;

        &.missing {
          background: #fafafa;
          color: #8b948f;
        }

        .dimension-label {
          color: #405448;
          font-size: 12px;
          font-weight: 600;
        }

        .dimension-value {
          flex: 1;
          font-size: 13px;
        }
      }
    }

    .differential-grid {
      display: grid;
      gap: 10px;

      .differential-card {
        overflow: hidden;
        border: 1px solid #e1e7e3;
        border-radius: 8px;

        .differential-title {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          padding: 9px 12px;
          background: #f4f7f5;

          strong {
            color: #31483a;
          }

          span {
            color: #859087;
            font-size: 12px;
          }
        }

        .differential-row {
          display: grid;
          grid-template-columns: 52px 1fr;
          gap: 8px;
          padding: 8px 12px;
          border-top: 1px solid #eef1ef;

          > span {
            width: fit-content;
            padding: 1px 6px;
            border-radius: 4px;
            font-size: 12px;
          }

          p {
            margin: 0;
            color: #5b675f;
            font-size: 13px;
            line-height: 1.5;
          }

          &.support > span { background: #e8f4eb; color: #39734a; }
          &.difference > span { background: #fff3e4; color: #a26618; }
          &.missing > span { background: #f1f2f1; color: #6e7771; }
        }
      }
    }

    .agent-trace {
      display: grid;
      gap: 8px;

      .agent-step {
        display: grid;
        grid-template-columns: 64px 1fr;
        align-items: start;
        gap: 10px;
        padding: 10px 12px;
        border: 1px solid #e5e9e6;
        border-radius: 7px;
        background: #f8faf8;

        strong {
          color: #34483c;
          font-size: 13px;
        }

        p {
          margin: 3px 0 0;
          color: #6f7d75;
          font-size: 12px;
          line-height: 1.5;
        }
      }
    }
    
    .evidence-list {
      .evidence-item {
        margin-bottom: 12px;
        padding: 12px;
        background: rgba(255, 255, 255, 0.56);
        border: 1px solid rgba(110, 135, 120, 0.12);
        border-radius: 8px;
        
        &:last-child {
          margin-bottom: 0;
        }
        
        h6 {
          margin: 0 0 8px 0;
          color: $text-dark;
          font-size: 14px;
        }
        
        p {
          margin: 0;
          color: $text-light;
          font-size: 13px;
          line-height: 1.5;
        }
      }
    }
    
    .safety-notice {
      margin-top: 16px;
      
      :deep(.el-alert) {
        padding: 8px 16px;
        
        .el-alert__title {
          font-size: 13px;
        }
      }
    }
  }
  
  .message-actions {
    padding: 0 16px 12px 16px;
    border-top: 1px solid rgba(110, 135, 120, 0.14);
    padding-top: 12px;
  }
}

@keyframes loading {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-10px);
  }
}
</style>
