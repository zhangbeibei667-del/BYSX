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
          <div v-if="chatHistory.length === 0" class="history-empty">
            暂无对话记录
          </div>
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
                <el-select
                  v-model="answerMode"
                  size="small"
                  class="answer-mode-select"
                  :disabled="isStreaming"
                  aria-label="回答模式"
                >
                  <el-option label="简洁回答" value="concise" />
                  <el-option label="教学解释" value="teaching" />
                  <el-option label="深入分析" value="deep" />
                </el-select>

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

                <el-checkbox
                  v-model="autoSendVoice"
                  class="voice-option"
                  :disabled="isStreaming"
                >
                  识别后发送
                </el-checkbox>

                <el-checkbox
                  v-model="autoSpeakStream"
                  class="voice-option"
                >
                  边答边读
                </el-checkbox>
                
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
                    <el-icon><Promotion /></el-icon>
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
            width="420"
            trigger="click"
            popper-class="quick-templates-popper"
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
import { useRouter, useRoute } from 'vue-router'
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
const route = useRoute()
const chatStore = useChatStore()
const messagesContainer = ref<HTMLElement>()
const inputRef = ref()
const inputMessage = ref('')
const answerMode = ref<'concise' | 'teaching' | 'deep'>(
  (localStorage.getItem('tcm_answer_mode') as 'concise' | 'teaching' | 'deep') || 'concise'
)
const showTemplates = ref(false)
const activeTemplateTab = ref('symptoms')
const chatHistory = ref<any[]>([])
const activeHistoryId = ref<string | null>(null)
const speaking = ref(false)
const listening = ref(false)
const autoSendVoice = ref(localStorage.getItem('tcm_voice_auto_send') === 'true')
const autoSpeakStream = ref(localStorage.getItem('tcm_voice_auto_speak') === 'true')
let activeEventSource: EventSource | null = null
let speechRecognition: any = null
let recognitionShouldSubmit = false
let finalVoiceTranscript = ''
let speechBuffer = ''
const speechQueue: string[] = []
let activeUtterance: SpeechSynthesisUtterance | null = null

const messages = computed(() => chatStore.messages)
const isStreaming = computed(() => chatStore.isStreaming)
const currentAnswer = computed(() => chatStore.currentAnswer)

const hasAssistantMessage = computed(() => {
  return messages.value.some(m => m.role === 'assistant' && !m.loading && m.content)
})

const normalizeSpeechText = (text: string) => text
  .replace(/```[\s\S]*?```/g, ' ')
  .replace(/https?:\/\/\S+/g, ' ')
  .replace(/\[\d+(?:[，,、\s]+\d+)*\]/g, '')
  .replace(/[*_#>`~|]/g, '')
  .replace(/\s+/g, ' ')
  .trim()

const stopSpeechQueue = () => {
  speechBuffer = ''
  speechQueue.splice(0)
  activeUtterance = null
  speaking.value = false
  window.speechSynthesis?.cancel()
}

const speakNext = () => {
  if (activeUtterance || speechQueue.length === 0) {
    if (!activeUtterance && speechQueue.length === 0) speaking.value = false
    return
  }

  const content = speechQueue.shift()
  if (!content) return speakNext()

  const utterance = new SpeechSynthesisUtterance(content)
  activeUtterance = utterance
  speaking.value = true
  utterance.lang = 'zh-CN'
  utterance.rate = 0.92
  utterance.pitch = 1
  utterance.volume = 1
  utterance.onend = () => {
    activeUtterance = null
    speakNext()
  }
  utterance.onerror = () => {
    activeUtterance = null
    speakNext()
  }
  window.speechSynthesis.speak(utterance)
}

const enqueueSpeech = (text: string, flush = false) => {
  speechBuffer += text
  const sentencePattern = /^([\s\S]*?[。！？!?；;\n]+)/
  let match = speechBuffer.match(sentencePattern)
  while (match) {
    const sentence = normalizeSpeechText(match[1])
    speechBuffer = speechBuffer.slice(match[1].length)
    if (sentence) speechQueue.push(sentence)
    match = speechBuffer.match(sentencePattern)
  }
  if (flush && speechBuffer.trim()) {
    const remainder = normalizeSpeechText(speechBuffer)
    speechBuffer = ''
    if (remainder) speechQueue.push(remainder)
  }
  speakNext()
}

const handleGlobalSpeech = () => {
  if (speaking.value) return stopSpeechQueue()

  const lastAssistantMsg = [...messages.value].reverse().find(
    m => m.role === 'assistant' && !m.loading && m.content
  )
  if (!lastAssistantMsg) {
    ElMessage.warning('暂无回答可朗读')
    return
  }

  stopSpeechQueue()
  enqueueSpeech(lastAssistantMsg.content, true)
}

const exampleQuestions = [
  '请解释风寒感冒常见证候、相关方剂和依据来源',
  '麻黄汤的组成、功效和适用证候是什么',
  '人参和黄芪在功效与使用注意上有什么区别',
  '失眠多梦可以从哪些证候角度进行中医药知识分析'
]

const symptomTemplates = [
  '请根据失眠多梦，整理可能相关的证候、常见方剂和依据片段',
  '咳嗽痰白清稀时，中医常从哪些证候角度分析',
  '畏寒肢冷和精神疲乏分别可能关联哪些证候和药材',
  '食欲不振、大便溏薄时，可以查询哪些脾胃相关知识',
  '请把口干、烦躁、睡眠差相关的中医概念按实体关系说明'
]

const prescriptionTemplates = [
  '归脾汤的组成、功效、主治和相关药材有哪些',
  '小柴胡汤常见适用证候是什么，请给出依据来源',
  '补中益气汤和归脾汤在功效侧重点上有什么区别',
  '麻黄汤和桂枝汤的组成、证候和使用思路如何区分',
  '请按组成、功效、主治、注意事项解释六味地黄丸'
]

const herbTemplates = [
  '人参的来源、功效、使用注意和相关方剂有哪些',
  '黄芪和党参在功效、归经和应用场景上如何区分',
  '当归常见功效是什么，通常和哪些证候或方剂相关',
  '茯苓的利水渗湿、健脾作用可以如何理解',
  '请比较金银花和连翘的功效异同，并列出依据片段'
]

onMounted(() => {
  loadChatHistory()
  const historyId = route.query.historyId
  if (typeof historyId === 'string' && historyId) {
    loadHistory(historyId)
  }
  const Recognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
  if (Recognition) {
    speechRecognition = new Recognition()
    speechRecognition.lang = 'zh-CN'
    speechRecognition.continuous = false
    speechRecognition.interimResults = true
    speechRecognition.onresult = (event: any) => {
      let finalText = ''
      let interimText = ''
      for (let i = 0; i < event.results.length; i += 1) {
        const transcript = event.results[i][0]?.transcript || ''
        if (event.results[i].isFinal) finalText += transcript
        else interimText += transcript
      }
      finalVoiceTranscript = finalText.trim()
      const visibleText = `${finalText}${interimText}`.trim()
      if (visibleText) inputMessage.value = visibleText
    }
    speechRecognition.onend = () => {
      listening.value = false
      const textToSubmit = (finalVoiceTranscript || inputMessage.value).trim()
      const shouldSubmit = recognitionShouldSubmit && autoSendVoice.value && Boolean(textToSubmit)
      recognitionShouldSubmit = false
      finalVoiceTranscript = ''
      if (shouldSubmit && !isStreaming.value) {
        inputMessage.value = textToSubmit
        nextTick(() => sendMessage())
      }
    }
    speechRecognition.onerror = (event: any) => {
      listening.value = false
      recognitionShouldSubmit = false
      if (event.error !== 'aborted' && event.error !== 'no-speech') {
        ElMessage.error('语音识别失败，请检查浏览器麦克风权限')
      }
    }
  }
})

onBeforeUnmount(() => {
  activeEventSource?.close()
  recognitionShouldSubmit = false
  speechRecognition?.abort?.()
  stopSpeechQueue()
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
    finalVoiceTranscript = ''
    recognitionShouldSubmit = true
    speechRecognition.start()
    listening.value = true
  } catch {
    recognitionShouldSubmit = false
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

const normalizeHistoryItem = (item: any) => {
  const messages = Array.isArray(item?.messages) ? item.messages : []
  const firstUser = messages.find((message: any) => message?.role === 'user')
  const lastAssistant = [...messages].reverse().find((message: any) => message?.role === 'assistant')
  const title = item?.title || item?.question || firstUser?.content || '对话记录'

  return {
    ...item,
    id: String(item?.id || Date.now()),
    title: title.slice(0, 24) + (title.length > 24 ? '...' : ''),
    preview: item?.preview || item?.answer || lastAssistant?.content || '',
    timestamp: item?.timestamp || item?.updatedAt || item?.createdAt || new Date().toISOString(),
    messageCount: item?.messageCount || messages.length || 1,
    messages
  }
}

const getHistoryListFromResponse = (res: any) => {
  if (Array.isArray(res)) return res
  if (Array.isArray(res?.data)) return res.data
  if (Array.isArray(res?.data?.list)) return res.data.list
  if (Array.isArray(res?.data?.items)) return res.data.items
  if (Array.isArray(res?.list)) return res.list
  if (Array.isArray(res?.items)) return res.items
  return []
}

const readLocalChatHistory = () => {
  const saved = localStorage.getItem('tcm_chat_history') || localStorage.getItem('tcm_chat_histories')
  if (!saved) return []
  try {
    const parsed = JSON.parse(saved)
    return Array.isArray(parsed) ? parsed.map(normalizeHistoryItem) : []
  } catch {
    return []
  }
}

const saveLocalChatHistory = () => {
  const payload = JSON.stringify(chatHistory.value)
  localStorage.setItem('tcm_chat_history', payload)
  localStorage.setItem('tcm_chat_histories', payload)
}

const loadChatHistory = async () => {
  try {
    const res: any = await chatApi.getHistory(1, 50)
    const list = getHistoryListFromResponse(res)
    if (list.length > 0) {
      chatHistory.value = list.map(normalizeHistoryItem)
      saveLocalChatHistory()
      return
    }
  } catch (apiError) {
    console.log('chatApi.getHistory 未就绪，使用本地数据')
  }

  chatHistory.value = readLocalChatHistory()
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
      chatStore.loadHistory(historyId, messages.map((item: any, index: number) => ({
        id: item.id || `${historyId}-${index}`,
        role: item.role,
        content: item.content || '',
        timestamp: item.timestamp || new Date().toISOString(),
        response: item.response
      })))
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
  saveLocalChatHistory()
  localStorage.removeItem(`tcm_chat_messages_${historyId}`)

  if (activeHistoryId.value === historyId) {
    newChat()
  }
  ElMessage.success('历史记录已删除')
}

const sendMessage = async () => {
  if (!inputMessage.value.trim() || isStreaming.value) return

  const userMessage = inputMessage.value.trim()

  if (autoSpeakStream.value) stopSpeechQueue()

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
      activeEventSource = chatApi.askQuestionStream(
        userMessage, activeHistoryId.value || undefined, answerMode.value
      )

      activeEventSource.onmessage = (event) => {
        if (event.data === '[DONE]') return
        try {
          const payload = JSON.parse(event.data)
          if (payload.type === 'chunk' && payload.content) {
            chatStore.appendToStream(payload.content)
            if (autoSpeakStream.value) {
              enqueueSpeech(payload.content, payload.sentence === true)
            }
            scrollToBottom()
          } else if (payload.type === 'result' && payload.result && !settled) {
            settled = true
            window.clearTimeout(timeout)
            activeEventSource?.close()
            activeEventSource = null
            if (autoSpeakStream.value) enqueueSpeech('', true)
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
    }

    const existing = chatHistory.value.find(h => h.id === activeHistoryId.value)
    const lastAssistantMessage = [...messages.value].reverse().find((message: any) => message.role === 'assistant')
    if (existing) {
      existing.title = existing.title || userMessage.slice(0, 24)
      existing.preview = lastAssistantMessage?.content || existing.preview || ''
      existing.timestamp = new Date().toISOString()
      existing.messageCount = messages.value.length
      existing.messages = messages.value
    } else {
      chatHistory.value.unshift({
        id: activeHistoryId.value,
        title: userMessage.slice(0, 24) + (userMessage.length > 24 ? '...' : ''),
        preview: lastAssistantMessage?.content || '',
        timestamp: new Date().toISOString(),
        messageCount: messages.value.length,
        messages: messages.value
      })
    }

    saveLocalChatHistory()
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
    if (autoSpeakStream.value) stopSpeechQueue()
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

watch(answerMode, (mode) => {
  localStorage.setItem('tcm_answer_mode', mode)
})

watch(autoSendVoice, (enabled) => {
  localStorage.setItem('tcm_voice_auto_send', String(enabled))
})

watch(autoSpeakStream, (enabled) => {
  localStorage.setItem('tcm_voice_auto_speak', String(enabled))
  if (!enabled) stopSpeechQueue()
})
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
$card-shadow: 0 6px 24px rgba(42, 64, 48, 0.08);
$card-border: rgba(110, 135, 120, 0.14);
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
    border: 1px solid $card-border;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: $card-shadow;
    
    .chat-sidebar {
      width: 280px;
      border-right: 1px solid $card-border;
      display: flex;
      flex-direction: column;
      background: #fbf7ee;
      
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
          background: $dark-green;
          border-color: $dark-green;
          border-radius: 8px;
          &:hover { background: $mid-green; border-color: $mid-green; }
        }
      }
      
      .history-list {
        flex: 1;
        overflow-y: auto;
        padding: 12px 10px;

        .history-empty {
          margin: 12px 4px;
          padding: 18px 12px;
          border: 1px dashed rgba(110, 135, 120, 0.18);
          border-radius: 10px;
          color: $text-light;
          text-align: center;
          font-size: 12px;
          background: rgba(255, 254, 251, 0.46);
        }
        
        .history-item {
          position: relative;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          padding: 10px 8px 10px 14px;
          border-radius: 9px;
          cursor: pointer;
          transition: background-color 0.2s, color 0.2s, box-shadow 0.2s;
          margin-bottom: 7px;
          border: 1px solid transparent;
          background: transparent;

          &::before {
            content: '';
            position: absolute;
            left: 6px;
            top: 12px;
            bottom: 12px;
            width: 3px;
            border-radius: 3px;
            background: transparent;
            transition: background-color 0.2s;
          }
          
          &:hover {
            background-color: rgba(255, 254, 251, 0.72);
            box-shadow: inset 0 0 0 1px rgba(110, 135, 120, 0.1);

            &::before {
              background: rgba(70, 99, 80, 0.28);
            }
          }
          
          &.active {
            background-color: #fffefb;
            box-shadow: inset 0 0 0 1px rgba(200, 168, 110, 0.24);

            &::before {
              background: $soft-gold;
            }
          }
          
          .history-preview {
            flex: 1;
            overflow: hidden;
            
            .history-title {
              margin: 0 0 4px 0;
              color: $text-dark;
              font-weight: 500;
              font-size: 12px;
              line-height: 1.35;
              white-space: nowrap;
              overflow: hidden;
              text-overflow: ellipsis;
            }
            
            .history-time {
              margin: 0;
              color: $text-light;
              font-size: 11px;
              line-height: 1.2;
            }
          }

          :deep(.el-button.is-link) {
            opacity: 0;
            padding: 4px;
            color: rgba(107, 122, 114, 0.72);
            transition: opacity 0.2s, color 0.2s;

            &:hover {
              color: #b13e3e;
            }
          }

          &:hover :deep(.el-button.is-link) {
            opacity: 1;
          }
        }
      }
    }
    
    .chat-main {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background: #f8f4ec;
      font-size: 14px;
      
      .chat-header {
        padding: 24px 32px;
        border-bottom: 1px solid $card-border;
        background: #fffdf8;
        
        h2 {
          margin: 0 0 8px 0;
          color: $dark-green;
          font-weight: 600;
          font-size: 22px;
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
        background: #f8f4ec;
        
        .messages-list {
          padding: 2px 0 8px;
        }

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
            background: rgba(70, 99, 80, 0.08);
            border: 1px solid rgba(70, 99, 80, 0.12);
            border-radius: 18px;
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
            font-size: 18px;
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
              &:hover { background: $dark-green; color: #fff; border-color: $dark-green; }
            }
          }
        }
        
        .messages-list {
          .typing-indicator {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 16px;
            background: #fffdf8;
            border: 1px solid $card-border;
            border-radius: 10px;
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
        background: #fffdf8;
        
        .input-container {
          margin-bottom: 12px;
          
          :deep(.el-textarea__inner) {
            font-size: 14px;
            border-radius: 8px;
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
              align-items: center;
              gap: 16px;

              .answer-mode-select {
                width: 112px;
              }

              .voice-option {
                margin-right: 0;
                color: $text-light;
                font-size: 12px;

                :deep(.el-checkbox__label) {
                  padding-left: 5px;
                  font-size: 12px;
                }
              }
              
              :deep(.el-button.is-link) {
                color: $text-light;
                &:hover { color: $mid-green; }
                &.is-disabled { color: #cbd5e1; }
              }
            }
            
            .action-right {
              :deep(.el-button--primary) {
                background: $dark-green;
                border-color: $dark-green;
                border-radius: 8px;
                &:hover:not(:disabled) { background: $mid-green; border-color: $mid-green; }
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
          font-size: 13px;
          cursor: pointer;
          width: fit-content;
          margin: 0 auto;
          padding: 7px 14px;
          border: 1px solid rgba(70, 99, 80, 0.12);
          border-radius: 8px;
          background: rgba(247, 243, 235, 0.78);
          transition: background-color 0.25s, border-color 0.25s, color 0.25s;
          
          &:hover {
            color: $dark-green;
            border-color: rgba(70, 99, 80, 0.22);
            background-color: rgba(70, 99, 80, 0.08);
          }
        }
        
        .quick-templates {
          h4 {
            margin: 0 0 10px;
            color: $text-dark;
            font-size: 15px;
            font-weight: 600;
          }

          :deep(.el-tabs__item) {
            color: $text-light;
            &.is-active { color: $dark-green; }
          }
          :deep(.el-tabs__active-bar) { background: $soft-gold; }
          :deep(.el-tabs__item:hover) { color: $mid-green; }
          
          .template-list {
            max-height: 240px;
            overflow-y: auto;
            
            .template-item {
              padding: 11px 12px;
              margin-bottom: 8px;
              background: #fffefb;
              border: 1px solid rgba(110, 135, 120, 0.1);
              border-radius: 8px;
              cursor: pointer;
              transition: background-color 0.25s, border-color 0.25s, color 0.25s;
              font-size: 13px;
              line-height: 1.55;
              color: $text-dark;
              
              &:hover {
                color: $dark-green;
                border-color: rgba(70, 99, 80, 0.2);
                background-color: rgba(70, 99, 80, 0.07);
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

:global(.quick-templates-popper) {
  border: 1px solid rgba(110, 135, 120, 0.14) !important;
  border-radius: 10px !important;
  background: #fbf7ee !important;
  box-shadow: 0 8px 28px rgba(42, 64, 48, 0.12) !important;
}

:global(.quick-templates-popper .el-popper__arrow::before) {
  background: #fbf7ee !important;
  border-color: rgba(110, 135, 120, 0.14) !important;
}

:global(.quick-templates-popper .quick-templates h4) {
  margin: 0 0 10px;
  color: #2c3630;
  font-size: 14px;
  font-weight: 600;
}

:global(.quick-templates-popper .el-tabs__header) {
  margin-bottom: 10px;
}

:global(.quick-templates-popper .el-tabs__item) {
  height: 34px;
  padding: 0 18px;
  color: #6b7a72;
  font-size: 13px;
}

:global(.quick-templates-popper .el-tabs__item.is-active),
:global(.quick-templates-popper .el-tabs__item:hover) {
  color: #2a4030;
}

:global(.quick-templates-popper .el-tabs__active-bar) {
  background: #c8a86e;
}

:global(.quick-templates-popper .template-list) {
  max-height: 248px;
  overflow-y: auto;
}

:global(.quick-templates-popper .template-item) {
  display: block;
  padding: 9px 10px;
  margin-bottom: 7px;
  border: 1px solid rgba(110, 135, 120, 0.12);
  border-radius: 8px;
  background: #fffefb;
  color: #46544d;
  font-size: 13px;
  line-height: 1.45;
  cursor: pointer;
  transition: background-color 0.2s, border-color 0.2s, color 0.2s;
}

:global(.quick-templates-popper .template-item:hover) {
  color: #2a4030;
  border-color: rgba(70, 99, 80, 0.24);
  background: rgba(70, 99, 80, 0.06);
}

:global(.quick-templates-popper .template-item:last-child) {
  margin-bottom: 0;
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
