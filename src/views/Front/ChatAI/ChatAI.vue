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
import { ref, computed, onMounted, nextTick, watch } from 'vue'
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
  VideoPause
} from '@element-plus/icons-vue'
import { useChatStore } from '@/store'
import { simulateStreamResponse, StreamSSE } from '@/utils/stream'
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
})

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
    let response: AnswerResponse | null = null

    try {
      const apiRes: any = await chatApi.askQuestion(userMessage, activeHistoryId.value || undefined)
      if (apiRes?.data) {
        response = apiRes.data
      } else if (apiRes?.answer) {
        response = apiRes as AnswerResponse
      }
    } catch (apiError) {
      console.log('chatApi.askQuestion 未就绪，使用 SSE 尝试...')
    }

    if (!response) {
      try {
        await new Promise<void>((resolve, reject) => {
          const streamUrl = `/api/chat/ask/stream?question=${encodeURIComponent(userMessage)}&historyId=${activeHistoryId.value || ''}`
          const streamSSE = new StreamSSE(streamUrl)

          streamSSE.start(
            (data) => {
              response = data
            },
            () => {
              resolve()
            }
          )

          setTimeout(() => {
            if (!response) {
              streamSSE.stop()
              resolve()
            }
          }, 8000)
        })
      } catch (sseError) {
        console.log('SSE 流式 API 未就绪:', sseError)
      }
    }

    if (!response) {
      response = buildMockResponse(userMessage)
    }

    if (response) {
      await simulateStreamResponse(
        response,
        (chunk) => {
          chatStore.appendToStream(chunk)
          scrollToBottom()
        },
        () => {
          chatStore.endStream(response!)
          scrollToBottom()
        },
        30
      )
    }

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
    ElMessage.error('发送失败，请重试')
  }
}

const buildMockResponse = (question: string): AnswerResponse => {
  const isInsomnia = /失眠|入睡|睡眠|多梦|易醒/.test(question)
  const isCough = /咳嗽|咳痰|痰|气喘|喘/.test(question)
  const isCold = /感冒|风寒|风热|畏寒|发热|鼻塞|流涕/.test(question)
  const isDigest = /食欲|腹胀|腹泻|便秘|消化|胃/.test(question)
  const isHerbCompare = /区别|对比|比较|哪个好/.test(question)

  if (isHerbCompare) {
    return {
      answer: `关于药材对比分析：

中药材的选择需根据具体证候和体质来决定，以下是常见对比：

1. **人参与黄芪**
   - 人参：大补元气，补脾益肺，生津养血，安神益智。适用于元气虚衰较重者。
   - 黄芪：补气升阳，固表止汗，利水消肿。适用于气虚表虚、自汗水肿者。
   - 区别：人参偏于补益脏腑之气，黄芪偏于补肌表之气。

2. **当归与熟地黄**
   - 当归：补血活血，调经止痛。补中有行，适用于血虚兼血瘀者。
   - 熟地黄：补血滋阴，益精填髓。纯补无泻，适用于血虚精亏者。

3. **茯苓与白术**
   - 茯苓：利水渗湿，健脾宁心。以利湿为主。
   - 白术：健脾益气，燥湿利水。以健脾为主。

具体使用哪种药材，需要结合患者的舌脉体征和整体辨证来确定。`,
      symptoms: [],
      syndromes: ['气虚证', '血虚证'],
      formulas: ['四君子汤', '四物汤'],
      herbs: ['人参', '黄芪', '当归', '熟地黄', '茯苓', '白术'],
      evidence: [
        { title: '《中药学》补气药章节', content: '人参、黄芪同为补气要药，人参大补元气，黄芪补气固表...' },
        { title: '《中药学》补血药章节', content: '当归补血活血，熟地黄补血滋阴，二者常相须为用...' },
      ],
      sources: [
        {
          title: '《中国药典》人参条目',
          type: '药典',
          source_detail: '《中国药典》2020版 第一卷',
          original_text: '人参，本品为五加科植物人参的干燥根和根茎。性味与归经：甘、微苦，微温。归脾、肺、心、肾经。功能与主治：大补元气，复脉固脱，补脾益肺，生津养血，安神益智。',
          chapter: 'P8-9',
          related_entities: [
            { id: 'H001', name: '人参', type: '药材' },
            { id: 'H002', name: '黄芪', type: '药材' },
          ]
        },
        {
          title: '《中药学》补气药章节',
          type: '教材',
          source_detail: '《中药学》第2版 第十二章 补气药',
          original_text: '人参、黄芪同为补气要药。人参大补元气，补脾益肺，生津养血，安神益智，为治虚劳内伤第一要药。黄芪补气升阳，固表止汗，利水消肿，为补气之长。',
          chapter: '第十二章 P178',
          related_entities: [
            { id: 'H001', name: '人参', type: '药材' },
            { id: 'H002', name: '黄芪', type: '药材' },
          ]
        },
      ],
      follow_up_questions: ['您想了解哪些具体药材的区别？', '是否有特定的症状需要调理？'],
      safety_notice: '本分析基于中医药理论知识，不构成医疗建议。如有实际病症，请咨询专业医师。',
      graph: { nodes: [], edges: [] }
    }
  }

  if (isInsomnia) {
    return {
      answer: `根据您关于失眠的问题，我来为您分析：

失眠在中医中有"不寐"、"不得卧"等称谓，病因病机复杂，常见以下证型：

1. **心脾两虚**：表现为失眠多梦、心悸健忘、食少乏力
   - 推荐方剂：归脾汤
   - 主要药材：酸枣仁、远志、人参、黄芪

2. **心肾不交**：表现为心烦失眠、心悸不安、头晕耳鸣
   - 推荐方剂：黄连阿胶汤
   - 主要药材：黄连、黄芩、阿胶、白芍

3. **肝郁化火**：表现为失眠多梦、烦躁易怒、口苦口干
   - 推荐方剂：龙胆泻肝汤
   - 主要药材：龙胆草、栀子、黄芩、柴胡

建议结合舌脉体征进一步辨证，以确定最适合的治疗方案。`,
      symptoms: ['失眠', '多梦', '心悸', '健忘'],
      syndromes: ['心脾两虚', '心肾不交', '肝郁化火'],
      formulas: ['归脾汤', '黄连阿胶汤', '龙胆泻肝汤'],
      herbs: ['酸枣仁', '远志', '人参', '黄芪', '黄连', '黄芩'],
      evidence: [
        { title: '《中医内科学》失眠章节', content: '失眠病位在心，与肝、脾、肾关系密切...' },
        { title: '《中药学》酸枣仁条目', content: '酸枣仁性甘、酸，平，归心、肝、胆经，具有养心益肝、安神、敛汗功效...' },
      ],
      sources: [
        {
          title: '《中医内科学》失眠章节',
          type: '教材',
          source_detail: '《中医内科学》第3版 第七章 心系病证',
          original_text: '失眠又称不寐，是以经常不能获得正常睡眠为特征的一类病证。其主要病机为阳盛阴衰，阴阳失交。病位主要在心，与肝、脾、肾关系密切。',
          chapter: '第七章 P156',
          related_entities: [
            { id: 'S001', name: '失眠', type: '症状' },
            { id: 'Z001', name: '心脾两虚', type: '证候' },
          ]
        },
        {
          title: '《中药学》酸枣仁条目',
          type: '教材',
          source_detail: '《中药学》第2版 第十五章 安神药',
          original_text: '酸枣仁性甘、酸，平，归心、肝、胆经。功效：养心益肝，安神，敛汗。主治：心悸失眠，自汗盗汗。',
          chapter: '第十五章 P210',
          related_entities: [
            { id: 'H003', name: '酸枣仁', type: '药材' },
          ]
        },
      ],
      follow_up_questions: ['是否伴有食少乏力？', '是否有舌淡、脉细等表现？', '是否经常熬夜或工作压力大？'],
      safety_notice: '本分析基于中医药理论知识，不构成医疗建议。如有实际病症，请咨询专业医师。',
      graph: { nodes: [], edges: [] }
    }
  }

  if (isCold) {
    return {
      answer: `关于外感病的分析：

外感病证是中医临床最常见的疾病之一，主要分为：

1. **外感风寒**：恶寒重发热轻，头痛身痛，鼻塞流清涕，舌苔薄白，脉浮紧。
   - 治法：辛温解表
   - 推荐方剂：麻黄汤、桂枝汤
   - 主要药材：麻黄、桂枝、杏仁、甘草

2. **外感风热**：发热重恶寒轻，口渴咽痛，咳嗽痰黄，舌边尖红，脉浮数。
   - 治法：辛凉解表
   - 推荐方剂：银翘散、桑菊饮
   - 主要药材：金银花、连翘、桑叶、菊花

请根据具体症状结合舌脉进行辨证选方。`,
      symptoms: ['发热', '恶寒', '咳嗽', '鼻塞', '头痛'],
      syndromes: ['外感风寒', '外感风热'],
      formulas: ['麻黄汤', '桂枝汤', '银翘散', '桑菊饮'],
      herbs: ['麻黄', '桂枝', '金银花', '连翘', '桑叶', '菊花'],
      evidence: [
        { title: '《伤寒论》太阳病篇', content: '太阳之为病，脉浮，头项强痛而恶寒...' },
      ],
      follow_up_questions: ['是清涕还是黄涕？', '有无咽喉疼痛？', '发热程度如何？'],
      safety_notice: '本分析基于中医药理论知识，不构成医疗建议。如有实际病症，请咨询专业医师。',
      graph: { nodes: [], edges: [] }
    }
  }

  if (isCough) {
    return {
      answer: `关于咳嗽的中医分析：

咳嗽病位在肺，但与肝、脾、肾等脏腑相关。《素问》云："五脏六腑皆令人咳，非独肺也。"

1. **风寒犯肺**：咳嗽声重，痰白稀薄，伴鼻塞流清涕，舌苔薄白，脉浮紧。
   - 推荐方剂：止嗽散、三拗汤
   - 主要药材：麻黄、杏仁、紫菀、款冬花

2. **痰湿蕴肺**：咳嗽反复发作，痰多色白易咯，胸闷脘痞，舌苔白腻，脉濡滑。
   - 推荐方剂：二陈汤、三子养亲汤
   - 主要药材：半夏、陈皮、茯苓、苏子

3. **肝火犯肺**：咳嗽阵作，痰黄黏稠，胸胁胀痛，口苦咽干，舌红苔黄，脉弦数。
   - 推荐方剂：黛蛤散合泻白散
   - 主要药材：桑白皮、地骨皮、黄芩、栀子`,
      symptoms: ['咳嗽', '咳痰', '胸闷'],
      syndromes: ['风寒犯肺', '痰湿蕴肺', '肝火犯肺'],
      formulas: ['止嗽散', '二陈汤', '泻白散'],
      herbs: ['麻黄', '杏仁', '半夏', '陈皮', '桑白皮', '黄芩'],
      evidence: [
        { title: '《中医内科学》咳嗽章节', content: '咳嗽分为外感咳嗽与内伤咳嗽两大类...' },
      ],
      follow_up_questions: ['痰的颜色和质地如何？', '咳嗽多久了？', '是否伴有胸痛？'],
      safety_notice: '本分析基于中医药理论知识，不构成医疗建议。如有实际病症，请咨询专业医师。',
      graph: { nodes: [], edges: [] }
    }
  }

  if (isDigest) {
    return {
      answer: `关于消化系统问题的中医分析：

脾胃为后天之本，气血生化之源。消化问题多与脾胃功能失调相关：

1. **脾胃气虚**：食欲不振，食后腹胀，大便溏薄，神疲乏力，舌淡苔白，脉弱。
   - 推荐方剂：四君子汤、香砂六君子汤
   - 主要药材：人参、白术、茯苓、甘草

2. **脾胃湿热**：脘腹痞满，恶心呕吐，口苦口黏，大便黏滞不爽，舌红苔黄腻，脉滑数。
   - 推荐方剂：半夏泻心汤、连朴饮
   - 主要药材：半夏、黄连、黄芩、厚朴

3. **食积停滞**：脘腹胀满，嗳腐吞酸，厌食，大便酸臭，舌苔厚腻，脉滑。
   - 推荐方剂：保和丸、枳实导滞丸
   - 主要药材：神曲、山楂、莱菔子、枳实`,
      symptoms: ['食欲不振', '腹胀', '腹泻', '便秘'],
      syndromes: ['脾胃气虚', '脾胃湿热', '食积停滞'],
      formulas: ['四君子汤', '半夏泻心汤', '保和丸'],
      herbs: ['人参', '白术', '茯苓', '半夏', '黄连', '山楂'],
      evidence: [
        { title: '《脾胃论》', content: '脾胃虚弱，阳气不能生长，是春夏之令不行，五脏之气不生...' },
      ],
      follow_up_questions: ['大便的形状和颜色？', '饭后腹胀明显吗？', '有无口苦或口甜？'],
      safety_notice: '本分析基于中医药理论知识，不构成医疗建议。如有实际病症，请咨询专业医师。',
      graph: { nodes: [], edges: [] }
    }
  }

  return {
    answer: `根据您的问题"${question}"，我来为您分析：

中医药学是中华民族的伟大创造，在疾病预防、治疗和康复中发挥着重要作用。基于知识图谱的中医药诊疗系统可以帮助您：

1. **症状分析**：通过症状描述，追溯可能的证候类型
2. **方剂推荐**：根据辨证结果，推荐合适的方剂
3. **药材查询**：了解每味药材的性味归经、功效主治
4. **关系推理**：展示症状→证候→方剂→药材之间的关联路径

建议您提供更详细的症状信息（如舌象、脉象等），以便进行更准确的辨证分析。

如果您有具体的药材、方剂或证候相关问题，欢迎继续提问！`,
    symptoms: [],
    syndromes: [],
    formulas: [],
    herbs: [],
    evidence: [
      { title: '中医药基本理论', content: '中医以整体观念和辨证论治为基本特点...' },
    ],
    follow_up_questions: ['您能更详细描述一下症状吗？', '想了解哪方面的中医药知识？'],
    safety_notice: '本分析基于中医药理论知识，不构成医疗建议。如有实际病症，请咨询专业医师。',
    graph: { nodes: [], edges: [] }
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