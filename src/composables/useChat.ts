import { ref } from 'vue'

// 聊天相关组合函数 - 待完善
export function useChat() {
  const messages = ref<Array<{role: string, content: string}>>([])
  const isStreaming = ref(false)
  const inputText = ref('')

  const sendMessage = async () => {
    if (!inputText.value.trim()) return
    
    const userMessage = inputText.value.trim()
    messages.value.push({ role: 'user', content: userMessage })
    inputText.value = ''
    isStreaming.value = true

    try {
      // TODO: 调用流式API
      console.log('发送消息:', userMessage)
    } finally {
      isStreaming.value = false
    }
  }

  const clearHistory = () => {
    messages.value = []
  }

  const saveConversation = () => {
    // TODO: 保存对话
    console.log('保存对话')
  }

  return {
    messages,
    isStreaming,
    inputText,
    sendMessage,
    clearHistory,
    saveConversation
  }
}