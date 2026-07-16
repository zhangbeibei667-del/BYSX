import axios from 'axios'
import { ElMessage } from 'element-plus'
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
  (response) => {
    const body = response.data
    if (body && typeof body === 'object' && typeof body.code === 'number') {
      if (body.code === 0 || body.code === 200) {
        return body.code === 0 ? { ...body, code: 200 } : body
      }
      // 图谱管理接口使用 HTTP 200 + 业务 code 表示失败。必须转成 rejected
      // Promise，否则注册页会把“用户名已存在”等失败结果显示成注册成功。
      const applicationError: any = new Error(body.msg || body.message || '请求失败')
      applicationError.response = { ...response, status: body.code, data: body }
      return Promise.reject(applicationError)
    }
    return body
  },
  (error) => {
    if (error.response?.status === 401) {
      ElMessage.error('登录已过期，请重新登录')
      localStorage.removeItem('admin_token')
      localStorage.removeItem('user_info')
      // 动态导入 router 避免循环依赖
      import('@/router').then(({ default: router }) => {
        router.push('/login')
      })
    }
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

// 通用响应包裹结构
interface ApiResponse<T> {
  code: number
  msg?: string
  data: T
}

// ===== 认证接口：统一接入图谱管理 JWT =====
export const authApi = {
  login: (data: { username: string; password: string }) => api.post<ApiResponse<{ token: string; user: { id: number; username: string; role: string } }>>('/kg/auth/login', data),
  register: (data: { username: string; password: string }) => api.post<ApiResponse<{ id: number; username: string; role: string }>>('/kg/auth/register', data),
  getCurrentUser: () => api.get<ApiResponse<{ id: number; username: string; role: string; last_login?: string }>>('/kg/auth/me'),
  changePassword: (data: { oldPassword: string; newPassword: string }) => api.post('/kg/auth/change-password', { old_password: data.oldPassword, new_password: data.newPassword }),
  logout: async () => ({ code: 200 })
}

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
  
  // 获取问答历史列表
  getHistory: (page = 1, pageSize = 20) => {
    return api.get('/chat/history', { params: { page, pageSize } })
  },

  // 获取单个对话的完整消息
  getHistoryDetail: (id: string) => {
    return api.get(`/chat/history/${id}`)
  },

  // 保存/更新对话（含完整消息列表，用于服务端持久化）
  saveHistory: (data: { id: string; title: string; messages: any[] }) => {
    return api.post('/chat/history/save', data)
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
  // 获取用于画布展示的 100 节点关系子图
  getFullGraph: () => {
    return api.get<GraphResponse>('/graph/full', { params: { limit: 300 } })
  },

  // 获取真实全量统计及路径查询的全部实体选项
  getOverview: () => {
    return api.get<{
      nodeCount: number
      relationCount: number
      entities: Array<{ id: string; label: string; type: string }>
    }>('/graph/overview')
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
  list: async (params: any) => {
    const limit = params?.pageSize || 20
    const offset = Math.max(0, (params?.page || 1) - 1) * limit
    const result: any = await api.get('/documents', { params: { limit: Math.min(limit, 100), offset } })
    const typeMap: Record<string, string> = { '科普资料': '科普', '论文': '期刊' }
    const items = (result.items || []).map((item: any) => ({ ...item, id: String(item.id), name: item.title, type: typeMap[item.category] || item.category, fileName: item.file_path?.split(/[\\/]/).pop() || '', fileUrl: '', relatedEntities: [] }))
    return { code: 200, data: { list: items, total: offset + items.length + (items.length === limit ? 1 : 0) } }
  },
  create: (data: any) => api.post('/documents', { title: data.name, source: data.source || '', content: data.content || '', category: data.type === '科普' ? '科普资料' : data.type === '期刊' ? '论文' : data.type || '未分类' }),
  update: (id: string, data: any) => api.put(`/documents/${id}`, { title: data.name, source: data.source || '', content: data.content || '', category: data.type === '科普' ? '科普资料' : data.type === '期刊' ? '论文' : data.type || '未分类' }),
  delete: (id: string) => api.delete(`/documents/${id}`),
  batchDelete: (ids: string[]) => Promise.all(ids.map(id => api.delete(`/documents/${id}`))),
  upload: (file: File, source = '', category = '未分类') => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/documents/upload', formData, {
      params: { source, category },
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  export: async () => {
    const result: any = await api.get('/documents', { params: { limit: 100, offset: 0 } })
    const rows = [['id','title','category','source'], ...(result.items || []).map((x:any) => [x.id,x.title,x.category,x.source])]
    return new Blob(['\ufeff' + rows.map((row:any[]) => row.map(v => `"${String(v ?? '').replace(/"/g,'""')}"`).join(',')).join('\n')], { type: 'text/csv;charset=utf-8' })
  }
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
  list: async (params: any) => {
    const result: any = await api.get('/agent/conversations', { params: { page: params?.page || 1, page_size: params?.pageSize || 20 } })
    const favorites: string[] = JSON.parse(localStorage.getItem('record_favorites') || '[]')
    const list = (result.list || []).map((x:any) => { const user=x.messages?.find((m:any)=>m.role==='user'); const assistant=[...(x.messages||[])].reverse().find((m:any)=>m.role==='assistant'); return { id:x.id, question:user?.content||x.title, answer:assistant?.content||'', isFavorite:favorites.includes(x.id), createdAt:x.timestamp, herbs:[], formulas:[], symptoms:[], syndromes:[] } })
    return { code: 200, data: { list, total: result.total || 0 } }
  },
  detail: (id: string) => api.get(`/agent/conversations/${id}`),
  delete: (id: string) => api.delete(`/agent/conversations/${id}`),
  batchDelete: (ids: string[]) => Promise.all(ids.map(id => api.delete(`/agent/conversations/${id}`))),
  toggleFavorite: async (id: string) => { const items: string[] = JSON.parse(localStorage.getItem('record_favorites') || '[]'); const next=items.includes(id)?items.filter(x=>x!==id):[...items,id];localStorage.setItem('record_favorites',JSON.stringify(next));return { toggled:true } },
  export: async (_params?: any) => { const result:any=await recordApi.list({page:1,pageSize:100}); const rows=[['question','answer','createdAt'],...result.data.list.map((x:any)=>[x.question,x.answer,x.createdAt])]; return new Blob(['\ufeff'+rows.map((row:any[])=>row.map(v=>`"${String(v??'').replace(/"/g,'""')}"`).join(',')).join('\n')],{type:'text/csv;charset=utf-8'}) },
  getStats: async () => { const result:any=await recordApi.list({page:1,pageSize:100}); const favorites=result.data.list.filter((x:any)=>x.isFavorite).length; return { code:200, data:{ today:0, thisWeek:0, total:result.data.total, favorites } } }
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
