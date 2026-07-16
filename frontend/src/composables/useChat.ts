import { ref } from 'vue'
import { chatApi } from '@/api'
import type { AnswerResponse } from '@/types'

export function useChat() {
  const messages = ref<Array<{ role: 'user' | 'assistant', content: string, response?: AnswerResponse }>>([])
  const isStreaming = ref(false)
  const inputText = ref('')
  const error = ref<string | null>(null)
  let activeSource: EventSource | null = null

  const sendMessage = async () => {
    if (!inputText.value.trim()) return
    
    const userMessage = inputText.value.trim()
    messages.value.push({ role: 'user', content: userMessage })
    inputText.value = ''
    isStreaming.value = true
    error.value = null
    messages.value.push({ role: 'assistant', content: '' })

    activeSource?.close()
    activeSource = chatApi.askQuestionStream(userMessage)
    const assistant = messages.value[messages.value.length - 1]

    activeSource.onmessage = (event) => {
      if (event.data === '[DONE]') {
        activeSource?.close()
        activeSource = null
        isStreaming.value = false
        return
      }
      try {
        const payload = JSON.parse(event.data)
        if (payload.type === 'chunk') assistant.content += payload.content || ''
        if (payload.type === 'result' && payload.result) assistant.response = payload.result
      } catch {
        error.value = '流式响应格式错误'
      }
    }
    activeSource.onerror = () => {
      activeSource?.close()
      activeSource = null
      isStreaming.value = false
      error.value = '问答服务连接失败，请稍后重试'
    }
  }

  const clearHistory = () => {
    messages.value = []
  }

  const saveConversation = async (id: string, title: string) => {
    await chatApi.saveHistory({ id, title, messages: messages.value })
  }

  return {
    messages,
    isStreaming,
    inputText,
    error,
    sendMessage,
    clearHistory,
    saveConversation
  }
}
