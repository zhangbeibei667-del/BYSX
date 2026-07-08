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
import { ref, onMounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Plus,
  Delete,
  ChatDotRound,
  MagicStick,
  Promotion,
  ArrowUp
} from '@element-plus/icons-vue'
import { useChatStore } from '@/store'
import { simulateStreamResponse } from '@/utils/stream'
import ChatBubble from '@/components/Chat/ChatBubble.vue'
import type { AnswerResponse } from '@/types'

const chatStore = useChatStore()
const messagesContainer = ref<HTMLElement>()
const inputRef = ref()
const inputMessage = ref('')
const showTemplates = ref(false)
const activeTemplateTab = ref('symptoms')
const chatHistory = ref<any[]>([])
const activeHistoryId = ref<string | null>(null)

const messages = computed(() => chatStore.messages)
const isStreaming = computed(() => chatStore.isStreaming)
const currentAnswer = computed(() => chatStore.currentAnswer)

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
  // 模拟加载历史记录
  chatHistory.value = [
    {
      id: '1',
      title: '失眠咨询',
      timestamp: new Date(Date.now() - 3600000).toISOString()
    },
    {
      id: '2',
      title: '方剂查询',
      timestamp: new Date(Date.now() - 7200000).toISOString()
    },
    {
      id: '3',
      title: '药材辨析',
      timestamp: new Date(Date.now() - 86400000).toISOString()
    }
  ]
}

const newChat = () => {
  chatStore.clearChat()
  activeHistoryId.value = null
  inputMessage.value = ''
}

const loadHistory = (historyId: string) => {
  activeHistoryId.value = historyId
  // 这里应该加载实际的历史消息
  const historyMessages = [
    {
      id: '1',
      role: 'user',
      content: '失眠应该用什么方剂治疗？',
      timestamp: new Date().toISOString()
    },
    {
      id: '2',
      role: 'assistant',
      content: '根据您的描述，失眠可从心脾两虚、心肾不交等角度考虑...',
      timestamp: new Date().toISOString(),
      response: {
        answer: '根据您的描述，失眠可从心脾两虚、心肾不交等角度考虑...',
        symptoms: ['失眠', '多梦'],
        syndromes: ['心脾两虚'],
        formulas: ['归脾汤'],
        herbs: ['酸枣仁', '远志'],
        evidence: [
          {
            title: '归脾汤方剂说明',
            content: '归脾汤具有益气补血、健脾养心等功效...'
          }
        ],
        follow_up_questions: [
          '是否伴有食少乏力？',
          '是否有舌淡、脉细等表现？'
        ],
        safety_notice: '本结果仅用于中医药知识学习和教学辅助，不构成医疗诊断或用药建议。'
      }
    }
  ]
  
  chatStore.loadHistory(historyId, historyMessages)
  scrollToBottom()
}

const deleteHistory = (historyId: string) => {
  chatHistory.value = chatHistory.value.filter(h => h.id !== historyId)
  if (activeHistoryId.value === historyId) {
    newChat()
  }
  ElMessage.success('历史记录已删除')
}

const sendMessage = async () => {
  if (!inputMessage.value.trim() || isStreaming.value) return
  
  const userMessage = inputMessage.value.trim()
  
  // 添加用户消息
  chatStore.addMessage('user', userMessage)
  inputMessage.value = ''
  
  // 添加助理消息（占位）
  chatStore.addMessage('assistant', '', undefined)
  chatStore.startStream()
  
  scrollToBottom()
  
  try {
    // 模拟回答（实际应该调用API）
    const mockResponse: AnswerResponse = {
      answer: `根据您的问题"${userMessage}"，我来为您分析：

失眠在中医中可以从多个角度考虑：
1. **心脾两虚**：表现为失眠多梦、心悸健忘、食少乏力
   - 推荐方剂：归脾汤
   - 主要药材：酸枣仁、远志、人参、黄芪
   
2. **心肾不交**：表现为心烦失眠、心悸不安、头晕耳鸣
   - 推荐方剂：黄连阿胶汤
   - 主要药材：黄连、黄芩、阿胶、白芍
   
3. **肝郁化火**：表现为失眠多梦、烦躁易怒、口苦口干
   - 推荐方剂：龙胆泻肝汤
   - 主要药材：龙胆草、栀子、黄芩、柴胡`,
      symptoms: ['失眠', '多梦', '心悸', '健忘'],
      syndromes: ['心脾两虚', '心肾不交', '肝郁化火'],
      formulas: ['归脾汤', '黄连阿胶汤', '龙胆泻肝汤'],
      herbs: ['酸枣仁', '远志', '人参', '黄芪', '黄连', '黄芩'],
      evidence: [
        {
          title: '《中医内科学》失眠章节',
          content: '失眠病位在心，与肝、脾、肾关系密切...'
        },
        {
          title: '《中药学》酸枣仁条目',
          content: '酸枣仁性甘、酸，平，归心、肝、胆经，具有养心益肝、安神、敛汗功效...'
        }
      ],
      follow_up_questions: [
        '是否伴有食少乏力？',
        '是否有舌淡、脉细等表现？',
        '是否经常熬夜或工作压力大？'
      ],
      safety_notice: '本分析基于中医药理论知识，不构成医疗建议。如有实际病症，请咨询专业医师。'
    }
    
    // 模拟流式响应
    await simulateStreamResponse(
      mockResponse,
      (chunk) => {
        chatStore.appendToStream(chunk)
        scrollToBottom()
      },
      () => {
        chatStore.endStream(mockResponse)
        scrollToBottom()
      },
      30
    )
    
    // 保存到历史
    if (!activeHistoryId.value) {
      activeHistoryId.value = Date.now().toString()
      chatHistory.value.unshift({
        id: activeHistoryId.value,
        title: userMessage.slice(0, 20) + (userMessage.length > 20 ? '...' : ''),
        timestamp: new Date().toISOString()
      })
    }
    
  } catch (error) {
    console.error('Error sending message:', error)
    chatStore.endStream()
    ElMessage.error('发送失败，请重试')
  }
}

const clearChat = () => {
  chatStore.clearChat()
  activeHistoryId.value = null
  ElMessage.success('对话已清除')
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

const handleFavorite = (messageId: string) => {
  // 处理收藏逻辑
  ElMessage.success('已收藏到知识库')
}

const handleFollowUp = (question: string) => {
  inputMessage.value = question
  nextTick(() => {
    inputRef.value?.focus()
  })
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

// 监听消息变化，自动滚动
watch(messages, () => {
  scrollToBottom()
}, { deep: true })
</script>

<style scoped lang="scss">
.chat-ai {
  height: calc(100vh - 104px);
  
  .chat-container {
    display: flex;
    height: 100%;
    background: white;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    
    .chat-sidebar {
      width: 280px;
      border-right: 1px solid #e4e7ed;
      display: flex;
      flex-direction: column;
      
      .sidebar-header {
        padding: 20px;
        border-bottom: 1px solid #e4e7ed;
        display: flex;
        justify-content: space-between;
        align-items: center;
        
        h3 {
          margin: 0;
          color: #303133;
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
            background-color: #f5f7fa;
          }
          
          &.active {
            background-color: #e3f2fd;
            border-left: 3px solid #409eff;
          }
          
          .history-preview {
            flex: 1;
            overflow: hidden;
            
            .history-title {
              margin: 0 0 4px 0;
              color: #303133;
              font-weight: 500;
              white-space: nowrap;
              overflow: hidden;
              text-overflow: ellipsis;
            }
            
            .history-time {
              margin: 0;
              color: #909399;
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
      
      .chat-header {
        padding: 24px 32px;
        border-bottom: 1px solid #e4e7ed;
        
        h2 {
          margin: 0 0 8px 0;
          color: #1a237e;
        }
        
        .chat-subtitle {
          margin: 0;
          color: #606266;
        }
      }
      
      .messages-area {
        flex: 1;
        padding: 24px 32px;
        overflow-y: auto;
        
        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 100%;
          color: #909399;
          
          .empty-icon {
            width: 80px;
            height: 80px;
            background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 24px;
            
            .el-icon {
              font-size: 36px;
              color: #2196f3;
            }
          }
          
          h3 {
            margin: 0 0 16px 0;
            color: #303133;
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
          }
        }
        
        .messages-list {
          .typing-indicator {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 16px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
            margin-top: 20px;
            
            .typing-dots {
              display: flex;
              gap: 4px;
              
              span {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: #409eff;
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
              color: #606266;
            }
          }
        }
      }
      
      .input-area {
        padding: 20px 32px;
        border-top: 1px solid #e4e7ed;
        
        .input-container {
          margin-bottom: 12px;
          
          :deep(.el-textarea__inner) {
            border-radius: 8px;
            resize: none;
          }
          
          .input-actions {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 12px;
            
            .action-left {
              display: flex;
              gap: 16px;
            }
          }
        }
        
        .quick-templates-trigger {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          color: #409eff;
          font-size: 14px;
          cursor: pointer;
          padding: 8px;
          border-radius: 4px;
          background: #f5f7fa;
          transition: background-color 0.3s;
          
          &:hover {
            background-color: #e4e7ed;
          }
        }
        
        .quick-templates {
          .template-tabs {
            :deep(.el-tabs__nav-wrap) {
              margin-bottom: 12px;
            }
            
            :deep(.el-tabs__item) {
              padding: 0 16px;
            }
          }
          
          .template-list {
            max-height: 200px;
            overflow-y: auto;
            
            .template-item {
              padding: 12px;
              margin-bottom: 8px;
              background: #f5f7fa;
              border-radius: 6px;
              cursor: pointer;
              transition: background-color 0.3s;
              font-size: 14px;
              line-height: 1.4;
              
              &:hover {
                background-color: #e4e7ed;
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