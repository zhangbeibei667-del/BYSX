import axios from 'axios'
import type {
  GraphResponse,
  AnswerResponse,
  GraphRelation,
  HerbEntity,
  PrescriptionEntity,
  SymptomEntity,
  SyndromeEntity
} from '@/types'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('admin_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

// 问答接口
export const chatApi = {
  // 发送问题
  askQuestion: (question: string, historyId?: string) => {
    return api.post<AnswerResponse>('/chat/ask', { question, historyId })
  },
  
  // 流式问答
  askQuestionStream: (question: string, historyId?: string) => {
    return new EventSource(`/api/chat/ask/stream?question=${encodeURIComponent(question)}&historyId=${historyId || ''}`)
  },
  
  // 获取问答历史
  getHistory: (page = 1, pageSize = 20) => {
    return api.get('/chat/history', { params: { page, pageSize } })
  },
  
  // 删除历史记录
  deleteHistory: (id: string) => {
    return api.delete(`/chat/history/${id}`)
  },
  
  // 收藏问答
  favoriteQuestion: (id: string) => {
    return api.post(`/chat/favorite/${id}`)
  }
}

// 图谱接口
export const graphApi = {
  // 获取完整图谱
  getFullGraph: () => {
    return api.get<GraphResponse>('/graph/full')
  },
  
  // 搜索实体
  searchEntities: (keyword: string, types?: string[]) => {
    return api.get<GraphResponse>('/graph/search', { params: { keyword, types } })
  },
  
  // 获取实体详情
  getEntityDetail: (id: string) => {
    return api.get(`/graph/entity/${id}`)
  },
  
  // 查询关系路径
  findRelationPath: (sourceId: string, targetId: string) => {
    return api.get<GraphResponse>('/graph/path', { params: { sourceId, targetId } })
  },
  
  // 获取关联实体
  getRelatedEntities: (id: string, depth = 2) => {
    return api.get<GraphResponse>(`/graph/related/${id}`, { params: { depth } })
  }
}

// 新增文献相关的 API（用于 ChatAI 回答中的溯源卡片）
export const literatureApi = {
  // 获取文献详情（用于回答溯源）
  getDetail: (id: string) => api.get(`/literature/${id}`),

  // 根据实体查询关联文献
  getByEntity: (entityId: string) => api.get(`/literature/entity/${entityId}`),

  // 搜索文献
  search: (keyword: string, params?: any) => api.get('/literature/search', { params: { keyword, ...params } })
}

// 文献管理接口
export const documentApi = {
  list: (params: any) => api.get('/admin/documents', { params }),
  create: (data: any) => api.post('/admin/documents', data),
  update: (id: string, data: any) => api.put(`/admin/documents/${id}`, data),
  delete: (id: string) => api.delete(`/admin/documents/${id}`),
  batchDelete: (ids: string[]) => api.delete('/admin/documents/batch', { data: { ids } }),
  upload: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/admin/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  export: () => api.get('/admin/documents/export', { responseType: 'blob' })
}

// 实体管理接口
export const entityApi = {
  // 药材管理
  herbs: {
    list: (params: any) => api.get<HerbEntity[]>('/admin/herbs', { params }),
    create: (data: Partial<HerbEntity>) => api.post('/admin/herbs', data),
    update: (id: string, data: Partial<HerbEntity>) => api.put(`/admin/herbs/${id}`, data),
    delete: (id: string) => api.delete(`/admin/herbs/${id}`),
    batchDelete: (ids: string[]) => api.delete('/admin/herbs/batch', { data: { ids } }),
    import: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return api.post('/admin/herbs/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    },
    export: () => api.get('/admin/herbs/export', { responseType: 'blob' })
  },
  
  // 方剂管理
  prescriptions: {
    list: (params: any) => api.get<PrescriptionEntity[]>('/admin/prescriptions', { params }),
    create: (data: Partial<PrescriptionEntity>) => api.post('/admin/prescriptions', data),
    update: (id: string, data: Partial<PrescriptionEntity>) => api.put(`/admin/prescriptions/${id}`, data),
    delete: (id: string) => api.delete(`/admin/prescriptions/${id}`),
    batchDelete: (ids: string[]) => api.delete('/admin/prescriptions/batch', { data: { ids } }),
    import: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return api.post('/admin/prescriptions/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    },
    export: () => api.get('/admin/prescriptions/export', { responseType: 'blob' })
  },
  
  // 症状管理
  symptoms: {
    list: (params: any) => api.get<SymptomEntity[]>('/admin/symptoms', { params }),
    create: (data: Partial<SymptomEntity>) => api.post('/admin/symptoms', data),
    update: (id: string, data: Partial<SymptomEntity>) => api.put(`/admin/symptoms/${id}`, data),
    delete: (id: string) => api.delete(`/admin/symptoms/${id}`),
    batchDelete: (ids: string[]) => api.delete('/admin/symptoms/batch', { data: { ids } }),
    import: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return api.post('/admin/symptoms/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    },
    export: () => api.get('/admin/symptoms/export', { responseType: 'blob' })
  },

  // 证候管理
  syndromes: {
    list: (params: any) => api.get<SyndromeEntity[]>('/admin/syndromes', { params }),
    create: (data: Partial<SyndromeEntity>) => api.post('/admin/syndromes', data),
    update: (id: string, data: Partial<SyndromeEntity>) => api.put(`/admin/syndromes/${id}`, data),
    delete: (id: string) => api.delete(`/admin/syndromes/${id}`),
    batchDelete: (ids: string[]) => api.delete('/admin/syndromes/batch', { data: { ids } }),
    import: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return api.post('/admin/syndromes/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    },
    export: () => api.get('/admin/syndromes/export', { responseType: 'blob' })
  }
}

// 关系管理接口
export const relationApi = {
  // 获取关系列表
  list: (params: any) => api.get<GraphRelation[]>('/admin/relations', { params }),
  
  // 创建关系
  create: (data: Omit<GraphRelation, 'source_name' | 'target_name'>) => api.post('/admin/relations', data),
  
  // 删除关系
  delete: (id: string) => api.delete(`/admin/relations/${id}`),
  
  // 批量删除
  batchDelete: (ids: string[]) => api.delete('/admin/relations/batch', { data: { ids } })
}

// 病例接口
export const caseApi = {
  // 创建病例
  create: (data: any) => api.post('/case/create', data),
  
  // 分析病例
  analyze: (caseId: string) => api.post<AnswerResponse>(`/case/analyze/${caseId}`),
  
  // 获取病例列表
  list: (params: any) => api.get('/case/list', { params }),
  
  // 获取病例详情
  detail: (id: string) => api.get(`/case/${id}`)
}

// 问答记录管理接口
export const recordApi = {
  list: (params: any) => api.get('/admin/records', { params }),
  detail: (id: string) => api.get(`/admin/records/${id}`),
  delete: (id: string) => api.delete(`/admin/records/${id}`),
  batchDelete: (ids: string[]) => api.delete('/admin/records/batch', { data: { ids } }),
  toggleFavorite: (id: string) => api.post(`/admin/records/${id}/favorite`),
  export: (params?: any) => api.get('/admin/records/export', { params, responseType: 'blob' }),
  getStats: () => api.get('/admin/records/stats')
}

// 统计接口
export const statsApi = {
  // 获取平台统计数据
  getPlatformStats: () => api.get<{
    totalHerbs: number
    totalPrescriptions: number
    totalSymptoms: number
    totalSyndromes: number
    totalRelations: number
    totalQuestions: number
    totalCases: number
  }>('/stats/platform'),
  
  // 获取热门实体统计
  getPopularEntities: (type: 'herbs' | 'prescriptions' | 'symptoms', limit = 10) => {
    return api.get(`/stats/popular/${type}`, { params: { limit } })
  },
  
  // 获取每日问答统计
  getDailyQuestions: (days = 7) => {
    return api.get('/stats/daily-questions', { params: { days } })
  },
  
  // 获取实体分类统计
  getCategoryStats: () => {
    return api.get('/stats/categories')
  }
}

export default api