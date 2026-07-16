<template>
  <div class="chat-ai">
    <div class="chat-container">
      <!-- 聊天侧边栏 -->
      <div class="chat-sidebar">
        <div class="sidebar-header">
          <h3>对话历史</h3>
          <el-button type="primary" size="small" @click="newChat">
            <el-icon><Plus /></el-icon>
            新对话
          </el-button>
        </div>
        
        <div class="history-list">
          <div
            v-for="history in chatHistory"
            :key="history.id"
            :class="['history-item', { active: activeHistoryId === history.id }]"
            @click="loadHistory(history.id)"
          >
            <div class="history-preview">
              <p class="history-title">{{ history.title }}</p>
              <p class="history-time">{{ formatTime(history.timestamp) }}</p>
            </div>
            <el-button
              type="danger"
              link
              size="small"
              @click.stop="deleteHistory(history.id)"
            >
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
      
      <!-- 聊天主区域 -->
      <div class="chat-main">
        <div class="chat-header">
          <h2>中医药智能问答</h2>
          <p class="chat-subtitle">输入症状、药材或方剂相关问题，获取基于知识图谱的智能解答</p>
        </div>
        
        <!-- 消息区域 -->
        <div ref="messagesContainer" class="messages-area">
          <div v-if="messages.length === 0" class="empty-state">
            <div class="empty-icon">
              <el-icon><ChatDotRound /></el-icon>
            </div>
            <h3>开始新的对话</h3>
            <p>请输入您的问题，例如：</p>
            <div class="example-questions">
              <el-button
                v-for="example in exampleQuestions"
                :key="example"
                type="info"
                size="small"
                @click="useExampleQuestion(example)"
              >
                {{ example }}
              </el-button>
            </div>
          </div>
          
          <div v-else class="messages-list">
            <ChatBubble
              v-for="message in messages"
              :key="message.id"
              :message="message"
              @favorite="handleFavorite"
              @followup="handleFollowUp"
              @navigate-to-graph="handleNavigateToGraph"
            />
            
            <!-- 正在输入指示器 -->
            <div v-if="isStreaming" class="typing-indicator">
              <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <p>智能体正在思考...</p>
            </div>
          </div>
        </div>
        
        <!-- 输入区域 -->
        <div class="input-area">
          <div class="input-container">
            <el-input
              ref="inputRef"
              v-model="inputMessage"
              type="textarea"
              :rows="3"
              placeholder="请输入您的问题（例如：失眠应该用什么方剂治疗？麻黄汤的组成和功效是什么？）"
              :maxlength="1000"
              resize="none"
              @keydown.enter.exact.prevent="sendMessage"
            />
            
            <div class="input-actions">
              <div class="action-left">
                <el-tooltip content="快捷问题模板" placement="top">
                  <el-button type="info" link @click="showQuickTemplates">
                    <el-icon><MagicStick /></el-icon>
                    模板
                  </el-button>
                </el-tooltip>

                <el-tooltip :content="listening ? '停止语音输入' : '语音输入'" placement="top">
                  <el-button
                    type="info"
                    link
                    :class="{ 'is-listening': listening }"
                    :disabled="isStreaming"
                    @click="toggleVoiceInput"
                  >
                    <el-icon><Microphone /></el-icon>
                    {{ listening ? '停止录音' : '语音输入' }}
                  </el-button>
                </el-tooltip>
                
                <el-tooltip content="朗读最新回答" placement="top">
                  <el-button
                    type="info"
                    link
                    @click="handleGlobalSpeech"
                    :disabled="!hasAssistantMessage"
                  >
                    <el-icon>
                      <VideoPlay v-if="!speaking" />
                      <VideoPause v-else />
                    </el-icon>
                    {{ speaking ? '停止' : '朗读' }}
                  </el-button>
                </el-tooltip>

                <el-tooltip content="清除当前对话" placement="top">
                  <el-button type="warning" link @click="clearChat" :disabled="messages.length === 0">
                    <el-icon><Delete /></el-icon>
                    清除
                  </el-button>
                </el-tooltip>
              </div>
              
              <div class="action-right">
                <el-button
                  type="primary"
                  :loading="isStreaming"
                  :disabled="!inputMessage.trim() || isStreaming"
                  @click="sendMessage"
                >
                  <template #icon>
                    <el-icon><Send /></el-icon>
                  </template>
                  发送
                </el-button>
              </div>
            </div>
          </div>
          
          <!-- 快速模板弹出框 -->
          <el-popover
            v-model:visible="showTemplates"
            placement="top-start"
            width="400"
            trigger="click"
          >
            <template #reference>
              <div class="quick-templates-trigger">
                快速提问模板
                <el-icon><ArrowUp /></el-icon>
              </div>
            </template>
            
            <div class="quick-templates">
              <h4>常用问题模板</h4>
              <div class="template-categories">
                <el-tabs v-model="activeTemplateTab" class="template-tabs">
                  <el-tab-pane label="症状咨询" name="symptoms">
                    <div class="template-list">
                      <div
                        v-for="template in symptomTemplates"
                        :key="template"
                        class="template-item"
                        @click="useTemplate(template)"
                      >
                        {{ template }}
                      </div>
                    </div>
                  </el-tab-pane>
                  
                  <el-tab-pane label="方剂查询" name="prescriptions">
                    <div class="template-list">
                      <div
                        v-for="template in prescriptionTemplates"
                        :key="template"
                        class="template-item"
                        @click="useTemplate(template)"
                      >
                        {{ template }}
                      </div>
                    </div>
                  </el-tab-pane>
                  
                  <el-tab-pane label="药材辨析" name="herbs">
                    <div class="template-list">
                      <div
                        v-for="template in herbTemplates"
                        :key="template"
                        class="template-item"
                        @click="useTemplate(template)"
                      >
                        {{ template }}
                      </div>
                    </div>
                  </el-tab-pane>
                </el-tabs>
              </div>
            </div>
          </el-popover>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Plus,
  Delete,
  ChatDotRound,
  MagicStick,
  Promotion,
  ArrowUp,
  VideoPlay,
  VideoPause,
  Microphone
} from '@element-plus/icons-vue'
import { useChatStore } from '@/store'
import { chatApi } from '@/api'
import ChatBubble from '@/components/Chat/ChatBubble.vue'
import type { AnswerResponse } from '@/types'

const router = useRouter()
const chatStore = useChatStore()
const messagesContainer = ref<HTMLElement>()
const inputRef = ref()
const inputMessage = ref('')
const showTemplates = ref(false)
const activeTemplateTab = ref('symptoms')
const chatHistory = ref<any[]>([])
const activeHistoryId = ref<string | null>(null)
const speaking = ref(false)
const listening = ref(false)
let activeEventSource: EventSource | null = null
let speechRecognition: any = null

const messages = computed(() => chatStore.messages)
const isStreaming = computed(() => chatStore.isStreaming)
const currentAnswer = computed(() => chatStore.currentAnswer)

const hasAssistantMessage = computed(() => {
  return messages.value.some(m => m.role === 'assistant' && !m.loading && m.content)
})

const handleGlobalSpeech = () => {
  if (speaking.value) {
    speaking.value = false
    window.speechSynthesis.cancel()
    return
  }

  const lastAssistantMsg = [...messages.value].reverse().find(
    m => m.role === 'assistant' && !m.loading && m.content
  )
  if (!lastAssistantMsg) {
    ElMessage.warning('暂无回答可朗读')
    return
  }

  speaking.value = true

  const utterance = new SpeechSynthesisUtterance(lastAssistantMsg.content)
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

const exampleQuestions = [
  '失眠应该用什么方剂治疗？',
  '麻黄汤的组成和功效是什么？',
  '人参和黄芪有什么区别？',
  '风寒感冒有哪些症状和方剂？'
]

const symptomTemplates = [
  '我最近总是失眠多梦，应该怎么调理？',
  '咳嗽有痰，痰色白稀，是什么证候？',
  '畏寒怕冷，四肢不温，应该用什么药材？',
  '食欲不振，大便溏泻，中医怎么看？'
]

const prescriptionTemplates = [
  '归脾汤的组成和主治是什么？',
  '小柴胡汤适用于什么情况？',
  '补中益气汤的现代应用有哪些？',
  '麻黄汤和桂枝汤有什么区别？'
]

const herbTemplates = [
  '人参的主要功效和禁忌是什么？',
  '黄芪和党参有什么区别？',
  '当归怎么用于妇科调理？',
  '茯苓的利水效果如何？'
]

onMounted(() => {
  loadChatHistory()
  const Recognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
  if (Recognition) {
    speechRecognition = new Recognition()
    speechRecognition.lang = 'zh-CN'
    speechRecognition.continuous = false
    speechRecognition.interimResults = true
    speechRecognition.onresult = (event: any) => {
      let transcript = ''
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        transcript += event.results[i][0]?.transcript || ''
      }
      if (transcript.trim()) inputMessage.value = transcript.trim()
    }
    speechRecognition.onend = () => { listening.value = false }
    speechRecognition.onerror = (event: any) => {
      listening.value = false
      if (event.error !== 'aborted' && event.error !== 'no-speech') {
        ElMessage.error('语音识别失败，请检查浏览器麦克风权限')
      }
    }
  }
})

onBeforeUnmount(() => {
  activeEventSource?.close()
  speechRecognition?.abort?.()
  window.speechSynthesis?.cancel()
})

const toggleVoiceInput = () => {
  if (!speechRecognition) {
    ElMessage.warning('当前浏览器不支持语音识别，请使用最新版 Chrome 或 Edge')
    return
  }
  if (listening.value) {
    speechRecognition.stop()
    listening.value = false
    return
  }
  try {
    speechRecognition.start()
    listening.value = true
  } catch {
    speechRecognition.abort()
    listening.value = false
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

const loadChatHistory = async () => {
  try {
    const res: any = await chatApi.getHistory(1, 50)
    if (res?.data) {
      chatHistory.value = Array.isArray(res.data) ? res.data.map((item: any) => ({
        id: item.id,
        title: item.question?.slice(0, 20) || '对话记录',
        timestamp: item.createdAt || new Date().toISOString()
      })) : []
      return
    } else if (Array.isArray(res)) {
      chatHistory.value = res.map((item: any) => ({
        id: item.id,
        title: item.question?.slice(0, 20) || '对话记录',
        timestamp: item.createdAt || new Date().toISOString()
      }))
      return
    }
  } catch (apiError) {
    console.log('chatApi.getHistory 未就绪，使用本地数据')
  }

  const saved = localStorage.getItem('tcm_chat_history')
  if (saved) {
    try {
      chatHistory.value = JSON.parse(saved)
      return
    } catch { }
  }

  chatHistory.value = []
}

const newChat = () => {
  saveCurrentChat()
  chatStore.clearChat()
  activeHistoryId.value = null
  inputMessage.value = ''
}

const loadHistory = async (historyId: string) => {
  activeHistoryId.value = historyId

  try {
    const res: any = await chatApi.getHistoryDetail(historyId)
    let messages: any[] | null = null
    if (res?.data?.messages) {
      messages = res.data.messages
    } else if (res?.messages) {
      messages = res.messages
    }
    if (messages && Array.isArray(messages) && messages.length > 0) {
      chatStore.loadHistory(historyId, messages)
      scrollToBottom()
      return
    }
  } catch {
    console.log('chatApi.getHistoryDetail 未就绪，尝试本地恢复')
  }

  const saved = localStorage.getItem(`tcm_chat_messages_${historyId}`)
  if (saved) {
    try {
      const messages = JSON.parse(saved)
      if (Array.isArray(messages) && messages.length > 0) {
        chatStore.loadHistory(historyId, messages)
        scrollToBottom()
        return
      }
    } catch { }
  }

  chatStore.clearChat()
  ElMessage.warning('该对话记录无法加载，请确认后端服务已连接或本地缓存未被清理')
}

const deleteHistory = async (historyId: string) => {
  try {
    await chatApi.deleteHistory(historyId)
  } catch {
    console.log('chatApi.deleteHistory 未就绪，仅本地删除')
  }

  chatHistory.value = chatHistory.value.filter(h => h.id !== historyId)
  localStorage.setItem('tcm_chat_history', JSON.stringify(chatHistory.value))
  localStorage.removeItem(`tcm_chat_messages_${historyId}`)

  if (activeHistoryId.value === historyId) {
    newChat()
  }
  ElMessage.success('历史记录已删除')
}

const sendMessage = async () => {
  if (!inputMessage.value.trim() || isStreaming.value) return

  const userMessage = inputMessage.value.trim()

  chatStore.addMessage('user', userMessage)
  inputMessage.value = ''

  chatStore.addMessage('assistant', '', undefined)
  chatStore.startStream()

  scrollToBottom()

  try {
    const response = await new Promise<AnswerResponse>((resolve, reject) => {
      let settled = false
      const timeout = window.setTimeout(() => {
        if (settled) return
        settled = true
        activeEventSource?.close()
        activeEventSource = null
        reject(new Error('问答服务响应超时'))
      }, 90000)

      activeEventSource?.close()
      activeEventSource = chatApi.askQuestionStream(userMessage, activeHistoryId.value || undefined)

      activeEventSource.onmessage = (event) => {
        if (event.data === '[DONE]') return
        try {
          const payload = JSON.parse(event.data)
          if (payload.type === 'chunk' && payload.content) {
            chatStore.appendToStream(payload.content)
            scrollToBottom()
          } else if (payload.type === 'result' && payload.result && !settled) {
            settled = true
            window.clearTimeout(timeout)
            activeEventSource?.close()
            activeEventSource = null
            chatStore.endStream(payload.result)
            scrollToBottom()
            resolve(payload.result as AnswerResponse)
          } else if (payload.type === 'error' && !settled) {
            settled = true
            window.clearTimeout(timeout)
            reject(new Error(payload.error || '问答服务返回错误'))
          }
        } catch {
          if (!settled) {
            settled = true
            window.clearTimeout(timeout)
            reject(new Error('问答服务返回了无法解析的数据'))
          }
        }
      }

      activeEventSource.onerror = () => {
        if (settled) return
        settled = true
        window.clearTimeout(timeout)
        activeEventSource?.close()
        activeEventSource = null
        reject(new Error('无法连接流式问答服务'))
      }
    })

    const conversationId = (response as any)?.conversation?.id
    if (conversationId) activeHistoryId.value = String(conversationId)

    if (!activeHistoryId.value) {
      activeHistoryId.value = Date.now().toString()
      chatHistory.value.unshift({
        id: activeHistoryId.value,
        title: userMessage.slice(0, 20) + (userMessage.length > 20 ? '...' : ''),
        timestamp: new Date().toISOString()
      })
    } else {
      const existing = chatHistory.value.find(h => h.id === activeHistoryId.value)
      if (existing) {
        existing.timestamp = new Date().toISOString()
      }
    }

    localStorage.setItem('tcm_chat_history', JSON.stringify(chatHistory.value))
    localStorage.setItem(`tcm_chat_messages_${activeHistoryId.value}`, JSON.stringify(messages.value))

    try {
      const title = chatHistory.value.find(h => h.id === activeHistoryId.value)?.title || '对话记录'
      await chatApi.saveHistory({
        id: activeHistoryId.value!,
        title,
        messages: messages.value
      })
    } catch {
      console.log('chatApi.saveHistory 未就绪，仅本地保存')
    }

  } catch (error) {
    console.error('Error sending message:', error)
    chatStore.endStream()
    chatStore.updateLastMessage('问答服务暂时不可用，未生成任何诊疗结论。请检查后端连接后重试。')
    ElMessage.error(error instanceof Error ? error.message : '发送失败，请重试')
  }
}

const clearChat = () => {
  saveCurrentChat()
  chatStore.clearChat()
  activeHistoryId.value = null
  ElMessage.success('对话已清除')
}

const saveCurrentChat = () => {
  if (activeHistoryId.value && messages.value.length > 0) {
    localStorage.setItem(`tcm_chat_messages_${activeHistoryId.value}`, JSON.stringify(messages.value))
  }
}

const showQuickTemplates = () => {
  showTemplates.value = true
}

const useTemplate = (template: string) => {
  inputMessage.value = template
  showTemplates.value = false
  nextTick(() => {
    inputRef.value?.focus()
  })
}

const useExampleQuestion = (question: string) => {
  inputMessage.value = question
  nextTick(() => {
    inputRef.value?.focus()
  })
}

const handleFavorite = async (messageId: string) => {
  try {
    await chatApi.favoriteQuestion(messageId)
  } catch {
    console.log('chatApi.favoriteQuestion 未就绪，仅本地标记')
  }
  ElMessage.success('已收藏到知识库')
}

const handleFollowUp = (question: string) => {
  inputMessage.value = question
  nextTick(() => {
    inputRef.value?.focus()
  })
}

const handleNavigateToGraph = (entityName: string) => {
  router.push({ path: '/graph', query: { search: entityName } })
}

const formatTime = (timestamp: string) => {
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  
  if (diff < 60000) {
    return '刚刚'
  } else if (diff < 3600000) {
    return `${Math.floor(diff / 60000)}分钟前`
  } else if (diff < 86400000) {
    return `${Math.floor(diff / 3600000)}小时前`
  } else {
    return date.toLocaleDateString('zh-CN')
  }
}

watch(messages, () => {
  scrollToBottom()
}, { deep: true })
</script>

<style scoped lang="scss">
// ==================== 国风变量 ====================
$dark-green: #2a4030;
$mid-green: #466350;
$soft-gold: #c8a86e;
$cream-bg: #f7f3eb;
$light-cream: #faf6ef;
$text-dark: #2c3630;
$text-light: #6b7a72;
$card-shadow: 0 2px 16px rgba(42, 64, 48, 0.08);
$card-border: rgba(110, 135, 120, 0.12);
$white: #ffffff;

.chat-ai {
  height: calc(100vh - 64px - 60px);
  margin-top: 50px;
  
  @media (max-width: 1200px) {
    margin-top: -1020px;
  }
  
  .chat-container {
    display: flex;
    height: 100%;
    background: $white;
    border-radius: 14px;
    overflow: hidden;
    box-shadow: $card-shadow;
    
    .chat-sidebar {
      width: 280px;
      border-right: 1px solid $card-border;
      display: flex;
      flex-direction: column;
      background: $light-cream;
      
      .sidebar-header {
        padding: 20px;
        border-bottom: 1px solid $card-border;
        display: flex;
        justify-content: space-between;
        align-items: center;
        
        h3 {
          margin: 0;
          color: $text-dark;
          font-weight: 600;
        }
        
        :deep(.el-button--primary) {
          background: $mid-green;
          border-color: $mid-green;
          border-radius: 8px;
          &:hover { background: $dark-green; border-color: $dark-green; }
        }
      }
      
      .history-list {
        flex: 1;
        overflow-y: auto;
        padding: 8px;
        
        .history-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px;
          border-radius: 8px;
          cursor: pointer;
          transition: background-color 0.3s;
          margin-bottom: 8px;
          
          &:hover {
            background-color: rgba(70, 99, 80, 0.06);
          }
          
          &.active {
            background-color: rgba(70, 99, 80, 0.1);
            border-left: 3px solid $mid-green;
          }
          
          .history-preview {
            flex: 1;
            overflow: hidden;
            
            .history-title {
              margin: 0 0 4px 0;
              color: $text-dark;
              font-weight: 500;
              white-space: nowrap;
              overflow: hidden;
              text-overflow: ellipsis;
            }
            
            .history-time {
              margin: 0;
              color: $text-light;
              font-size: 12px;
            }
          }
        }
      }
    }
    
    .chat-main {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background: $cream-bg;
      
      .chat-header {
        padding: 24px 32px;
        border-bottom: 1px solid $card-border;
        background: $white;
        
        h2 {
          margin: 0 0 8px 0;
          color: $dark-green;
          font-weight: 600;
        }
        
        .chat-subtitle {
          margin: 0;
          color: $text-light;
          font-size: 14px;
        }
      }
      
      .messages-area {
        flex: 1;
        padding: 24px 32px;
        overflow-y: auto;
        background: $cream-bg;
        
        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 100%;
          color: $text-light;
          
          .empty-icon {
            width: 80px;
            height: 80px;
            background: rgba(70, 99, 80, 0.1);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 24px;
            
            .el-icon {
              font-size: 36px;
              color: $mid-green;
            }
          }
          
          h3 {
            margin: 0 0 16px 0;
            color: $text-dark;
          }
          
          p {
            margin: 0 0 20px 0;
          }
          
          .example-questions {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            justify-content: center;
            max-width: 600px;
            
            :deep(.el-button--info) {
              background: rgba(70, 99, 80, 0.08);
              border-color: rgba(70, 99, 80, 0.2);
              color: $dark-green;
              border-radius: 8px;
              &:hover { background: $mid-green; color: #fff; border-color: $mid-green; }
            }
          }
        }
        
        .messages-list {
          .typing-indicator {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 16px;
            background: $white;
            border-radius: 12px;
            box-shadow: $card-shadow;
            margin-top: 20px;
            
            .typing-dots {
              display: flex;
              gap: 4px;
              
              span {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: $mid-green;
                animation: typing 1.4s ease-in-out infinite;
                
                &:nth-child(2) {
                  animation-delay: 0.2s;
                }
                
                &:nth-child(3) {
                  animation-delay: 0.4s;
                }
              }
            }
            
            p {
              margin: 0;
              color: $text-light;
            }
          }
        }
      }
      
      .input-area {
        padding: 20px 32px;
        border-top: 1px solid $card-border;
        background: $white;
        
        .input-container {
          margin-bottom: 12px;
          
          :deep(.el-textarea__inner) {
            border-radius: 10px;
            resize: none;
            border-color: $card-border;
            &:focus { border-color: $mid-green; box-shadow: 0 0 0 2px rgba(70, 99, 80, 0.12); }
          }
          
          .input-actions {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 12px;
            
            .action-left {
              display: flex;
              gap: 16px;
              
              :deep(.el-button.is-link) {
                color: $text-light;
                &:hover { color: $mid-green; }
                &.is-disabled { color: #cbd5e1; }
              }
            }
            
            .action-right {
              :deep(.el-button--primary) {
                background: $mid-green;
                border-color: $mid-green;
                border-radius: 8px;
                &:hover:not(:disabled) { background: $dark-green; border-color: $dark-green; }
                &:disabled { background: rgba(70, 99, 80, 0.3); border-color: rgba(70, 99, 80, 0.3); }
              }
            }
          }
        }
        
        .quick-templates-trigger {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          color: $mid-green;
          font-size: 14px;
          cursor: pointer;
          padding: 8px;
          border-radius: 6px;
          background: $cream-bg;
          transition: background-color 0.3s;
          
          &:hover {
            background-color: rgba(70, 99, 80, 0.1);
          }
        }
        
        .quick-templates {
          :deep(.el-tabs__item) {
            color: $text-light;
            &.is-active { color: $dark-green; }
          }
          :deep(.el-tabs__active-bar) { background: $soft-gold; }
          :deep(.el-tabs__item:hover) { color: $mid-green; }
          
          .template-list {
            max-height: 200px;
            overflow-y: auto;
            
            .template-item {
              padding: 12px;
              margin-bottom: 8px;
              background: $cream-bg;
              border-radius: 6px;
              cursor: pointer;
              transition: background-color 0.3s;
              font-size: 14px;
              line-height: 1.4;
              color: $text-dark;
              
              &:hover {
                background-color: rgba(70, 99, 80, 0.1);
              }
              
              &:last-child {
                margin-bottom: 0;
              }
            }
          }
        }
      }
    }
  }
}

@keyframes typing {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-5px);
  }
}
</style>
