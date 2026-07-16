import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AnswerResponse } from '@/types'
import { clearCaptchaVerified } from '@/utils/captcha'

// 角色类型
export type UserRole = 'guest' | 'user' | 'admin'

// 用户信息
export interface UserInfo {
  id: number | string
  username: string
  role: UserRole
}

// 用户状态存储
export const useUserStore = defineStore('user', () => {
  const isAuthenticated = ref(false)
  const userInfo = ref<UserInfo>({
    id: '',
    username: '',
    role: 'guest'
  })

  const isAdmin = computed(() => userInfo.value.role === 'admin')

  const login = (token: string, userData: UserInfo) => {
    localStorage.setItem('admin_token', token)
    localStorage.setItem('user_info', JSON.stringify(userData))
    isAuthenticated.value = true
    userInfo.value = userData
  }

  const logout = () => {
    localStorage.removeItem('admin_token')
    localStorage.removeItem('user_info')
    clearCaptchaVerified()
    isAuthenticated.value = false
    userInfo.value = { id: '', username: '', role: 'guest' }
  }

  const checkAuth = () => {
    const token = localStorage.getItem('admin_token')
    if (token) {
      isAuthenticated.value = true
      // 从 localStorage 恢复用户信息
      const stored = localStorage.getItem('user_info')
      if (stored) {
        try {
          userInfo.value = JSON.parse(stored)
        } catch {
          userInfo.value = { id: '', username: '', role: 'guest' }
        }
      }
    }
  }

  return {
    isAuthenticated,
    userInfo,
    isAdmin,
    login,
    logout,
    checkAuth
  }
})

// 聊天状态存储
export const useChatStore = defineStore('chat', () => {
  const messages = ref<Array<{
    id: string
    role: 'user' | 'assistant'
    content: string
    timestamp: string
    loading?: boolean
    response?: AnswerResponse
  }>>([])
  
  const currentAnswer = ref<string>('')
  const isStreaming = ref(false)
  const activeHistoryId = ref<string | null>(null)
  
  const addMessage = (role: 'user' | 'assistant', content: string, response?: AnswerResponse) => {
    const id = Date.now().toString()
    const timestamp = new Date().toISOString()
    
    messages.value.push({
      id,
      role,
      content,
      timestamp,
      response
    })
  }
  
  const updateLastMessage = (content: string, response?: AnswerResponse) => {
    if (messages.value.length > 0) {
      const lastMsg = messages.value[messages.value.length - 1]
      lastMsg.content = content
      lastMsg.response = response
      lastMsg.loading = false
    }
  }
  
  const startStream = () => {
    isStreaming.value = true
    currentAnswer.value = ''
  }
  
  const appendToStream = (chunk: string) => {
    currentAnswer.value += chunk
    if (messages.value.length > 0) {
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg.role === 'assistant') {
        lastMsg.content = currentAnswer.value
        lastMsg.loading = true
      }
    }
  }
  
  const endStream = (response?: AnswerResponse) => {
    isStreaming.value = false
    if (currentAnswer.value) {
      updateLastMessage(currentAnswer.value, response)
      currentAnswer.value = ''
    }
  }
  
  const clearChat = () => {
    messages.value = []
    currentAnswer.value = ''
    isStreaming.value = false
    activeHistoryId.value = null
  }
  
  const loadHistory = (historyId: string, historyMessages: any[]) => {
    activeHistoryId.value = historyId
    messages.value = historyMessages
  }
  
  return {
    messages,
    currentAnswer,
    isStreaming,
    activeHistoryId,
    addMessage,
    updateLastMessage,
    startStream,
    appendToStream,
    endStream,
    clearChat,
    loadHistory
  }
})

// 图谱状态存储
export const useGraphStore = defineStore('graph', () => {
  const nodes = ref<any[]>([])
  const edges = ref<any[]>([])
  const selectedNode = ref<any>(null)
  const selectedNodes = ref<any[]>([])
  const graphLayout = ref('force')
  const zoomLevel = ref(1)
  
  const setGraphData = (data: { nodes: any[]; edges: any[] }) => {
    nodes.value = data.nodes
    edges.value = data.edges
  }
  
  const selectNode = (node: any) => {
    selectedNode.value = node
  }
  
  const clearSelection = () => {
    selectedNode.value = null
    selectedNodes.value = []
  }
  
  const filterByType = (type: string) => {
    return nodes.value.filter(node => node.type === type)
  }
  
  const findConnectedNodes = (nodeId: string) => {
    const connectedEdges = edges.value.filter(
      edge => edge.source === nodeId || edge.target === nodeId
    )
    const connectedNodeIds = connectedEdges.map(edge => 
      edge.source === nodeId ? edge.target : edge.source
    )
    return nodes.value.filter(node => connectedNodeIds.includes(node.id))
  }
  
  return {
    nodes,
    edges,
    selectedNode,
    selectedNodes,
    graphLayout,
    zoomLevel,
    setGraphData,
    selectNode,
    clearSelection,
    filterByType,
    findConnectedNodes
  }
})

// 后台管理状态存储
export const useAdminStore = defineStore('admin', () => {
  const currentEntityType = ref<'herb' | 'prescription' | 'symptom' | 'syndrome' | 'relation'>('herb')
  const tableData = ref<any[]>([])
  const tableLoading = ref(false)
  const totalItems = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(20)
  const searchQuery = ref('')
  
  const setTableData = (data: any[], total: number) => {
    tableData.value = data
    totalItems.value = total
  }
  
  const setLoading = (loading: boolean) => {
    tableLoading.value = loading
  }
  
  const setEntityType = (type: any) => {
    currentEntityType.value = type
    resetPagination()
  }
  
  const resetPagination = () => {
    currentPage.value = 1
    searchQuery.value = ''
  }
  
  return {
    currentEntityType,
    tableData,
    tableLoading,
    totalItems,
    currentPage,
    pageSize,
    searchQuery,
    setTableData,
    setLoading,
    setEntityType,
    resetPagination
  }
})
