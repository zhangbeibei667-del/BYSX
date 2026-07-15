<template>
  <div :class="['chat-bubble', `role-${message.role}`]">
    <!-- 消息头部 -->
    <div class="message-header">
      <div class="avatar">
        <el-icon v-if="message.role === 'user'" :size="20"><User /></el-icon>
        <el-icon v-else :size="20"><Robot /></el-icon>
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

    <!-- RAG 依据来源面板 -->
    <div
      v-if="message.role === 'assistant' && hasSources"
      class="sources-panel"
    >
      <el-collapse v-model="activeSourceNames">
        <el-collapse-item title="📚 查看依据（RAG溯源）" name="sources">
          <div
            v-for="(source, idx) in message.response?.sources"
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
                📖 {{ source.source_detail }}
              </span>
              <span v-if="source.chapter" class="source-chapter">
                📍 {{ source.chapter }}
              </span>
            </div>

            <blockquote v-if="source.original_text" class="source-quote">
              {{ source.original_text }}
            </blockquote>

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
      
      <!-- 依据文献 -->
      <div v-if="message.response.evidence?.length" class="expansion-section">
        <h4 class="section-title">
          <el-icon><Document /></el-icon>
          依据文献
        </h4>
        <div class="evidence-list">
          <div
            v-for="(item, index) in message.response.evidence"
            :key="`evidence-${index}`"
            class="evidence-item"
          >
            <h6>{{ item.title }}</h6>
            <p>{{ item.content }}</p>
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
  VideoPlay,
  VideoPause
} from '@element-plus/icons-vue'
import type { SourceItem } from '@/types'

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
    safety_notice: string
    sources?: SourceItem[]
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
  '期刊': 'success'
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
  const sources = props.message.response?.sources
  return sources && sources.length > 0
})

const handleEntityClick = (entity: { name: string; type: string; id: string }) => {
  emit('navigateToGraph', entity.name)
}

const expanded = ref(false)
const speaking = ref(false)
const md = new MarkdownIt()

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
.chat-bubble {
  margin: 20px 0;
  border-radius: 12px;
  overflow: hidden;
  background: white;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  
  &.role-user {
    .message-header {
      background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
    }
  }
  
  &.role-assistant {
    .message-header {
      background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%);
    }
  }
  
  .message-header {
    padding: 12px 16px;
    display: flex;
    align-items: center;
    gap: 12px;
    
    .avatar {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: white;
      display: flex;
      align-items: center;
      justify-content: center;
      
      .el-icon {
        color: #666;
      }
    }
    
    .header-info {
      flex: 1;
      
      .username {
        font-weight: bold;
        color: #333;
        margin-right: 12px;
      }
      
      .timestamp {
        color: #666;
        font-size: 12px;
      }
    }
    
    .header-actions {
      display: flex;
      gap: 8px;
    }
  }
  
  .message-content {
    padding: 16px;
    
    .content-text {
      line-height: 1.6;
      color: #333;
      
      :deep(*) {
        margin: 8px 0;
        
        &:first-child {
          margin-top: 0;
        }
        
        &:last-child {
          margin-bottom: 0;
        }
      }
      
      :deep(h1), :deep(h2), :deep(h3), :deep(h4) {
        color: #409eff;
        border-bottom: 1px solid #e4e7ed;
        padding-bottom: 8px;
      }
      
      :deep(ul), :deep(ol) {
        padding-left: 20px;
      }
      
      :deep(code) {
        background: #f5f7fa;
        padding: 2px 6px;
        border-radius: 4px;
        font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Consolas', monospace;
      }
      
      :deep(pre) {
        background: #f5f7fa;
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
          background: #409eff;
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
    border-top: 1px solid #e4e7ed;
    padding: 0;

    :deep(.el-collapse) {
      border: none;
      --el-collapse-header-bg-color: transparent;
      --el-collapse-content-bg-color: #fafafa;
    }

    :deep(.el-collapse-item__header) {
      padding: 14px 20px;
      font-size: 14px;
      font-weight: 500;
      color: #466350;
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

    :deep(.el-collapse-item__content) {
      padding: 16px 20px;
    }

    .source-item {
      padding: 14px 16px;
      margin-bottom: 12px;
      background: #fff;
      border-radius: 8px;
      border: 1px solid rgba(110, 135, 120, 0.1);
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
          color: #2c3630;
          font-size: 14px;
        }
      }

      .source-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        margin-bottom: 8px;
        font-size: 12px;
        color: #6b7a72;

        .source-detail, .source-chapter {
          display: inline-flex;
          align-items: center;
          gap: 2px;
        }
      }

      .source-quote {
        margin: 8px 0 0 0;
        padding: 10px 14px;
        background: rgba(70, 99, 80, 0.04);
        border-left: 3px solid #466350;
        border-radius: 4px;
        font-size: 13px;
        line-height: 1.7;
        color: #4a5c50;
        font-style: italic;
      }

      .source-entities {
        margin-top: 10px;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;

        .entities-label {
          font-size: 12px;
          color: #6b7a72;
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

  .message-expansion {
    border-top: 1px solid #e4e7ed;
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
        color: #409eff;
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
          color: #666;
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
    
    .evidence-list {
      .evidence-item {
        margin-bottom: 12px;
        padding: 12px;
        background: #f5f7fa;
        border-radius: 8px;
        
        &:last-child {
          margin-bottom: 0;
        }
        
        h6 {
          margin: 0 0 8px 0;
          color: #333;
          font-size: 14px;
        }
        
        p {
          margin: 0;
          color: #666;
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
    border-top: 1px solid #e4e7ed;
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