<template>
  <div class="history-page">
    <!-- ==================== 左侧：分类导航栏（30%） ==================== -->
    <aside class="left-sidebar">
      <!-- 💬 问答历史 -->
      <div
        class="sidebar-card"
        :class="{ active: activeTab === 'chat' }"
        @click="switchTab('chat')"
      >
        <div class="sc-header">
          <span class="sc-icon">💬</span>
          <span class="sc-title">问答历史</span>
          <span class="sc-count">{{ chatHistories.length }}</span>
        </div>
        <div class="sc-preview">
          <div v-if="chatHistories.length === 0" class="sc-empty">暂无对话记录</div>
          <div
            v-for="group in chatGroups.slice(0, 2)"
            :key="group.label"
            class="sc-group"
          >
            <span class="sc-group-label">{{ group.label }}</span>
            <div
              v-for="item in group.items.slice(0, 2)"
              :key="item.id"
              class="sc-item"
              @click.stop="selectChatItem(item)"
            >
              <span class="sci-title">{{ truncateText(item.title || item.question, 18) }}</span>
              <span class="sci-count">{{ item.messageCount || item.messages?.length || 1 }}条</span>
              <span class="sci-time">{{ formatTime(item.timestamp || item.createdAt) }}</span>
            </div>
          </div>
        </div>
        <div v-if="chatHistories.length > 0" class="sc-footer">
          <el-button text type="danger" size="small" @click.stop="handleClearAllChats">
            清空全部
          </el-button>
        </div>
      </div>

      <!-- ⭐ 我的收藏 -->
      <div
        class="sidebar-card"
        :class="{ active: activeTab === 'favorite' }"
        @click="switchTab('favorite')"
      >
        <div class="sc-header">
          <span class="sc-icon">⭐</span>
          <span class="sc-title">我的收藏</span>
          <span class="sc-count">{{ favorites.length }}</span>
        </div>
        <div class="sc-preview">
          <div v-if="favorites.length === 0" class="sc-empty">暂无收藏内容</div>
          <div
            v-for="fav in favorites.slice(0, 4)"
            :key="fav.id"
            class="sc-item sc-fav-item"
          >
            <span class="sci-type-tag" :class="fav.type">
              {{ fav.type === 'chat' ? '💬' : '🎯' }}
            </span>
            <span class="sci-title">{{ truncateText(fav.title, 14) }}</span>
            <span class="sci-time">{{ formatTime(fav.time) }}</span>
          </div>
        </div>
      </div>

      <!-- 📋 教学病例 -->
      <div
        class="sidebar-card"
        :class="{ active: activeTab === 'case' }"
        @click="switchTab('case')"
      >
        <div class="sc-header">
          <span class="sc-icon">📋</span>
          <span class="sc-title">教学病例</span>
          <span class="sc-count">{{ cases.length }}</span>
        </div>
        <div class="sc-preview">
          <div v-if="cases.length === 0" class="sc-empty">暂无教学病例</div>
          <div
            v-for="c in cases.slice(0, 3)"
            :key="c.id"
            class="sc-item"
          >
            <span class="sci-title">{{ c.name || '未命名' }}</span>
            <span class="sci-syndrome">{{ (c.syndromes || []).join('、') || '待分析' }}</span>
            <span class="sci-time">{{ formatTime(c.createdAt || c.date) }}</span>
          </div>
        </div>
      </div>
    </aside>

    <!-- ==================== 右侧：内容展示区（70%） ==================== -->
    <main class="right-content">
      <!-- ===== 问答历史视图 ===== -->
      <div v-if="activeTab === 'chat'" class="content-panel">
        <div class="panel-toolbar">
          <el-input
            v-model="chatSearch"
            placeholder="搜索对话内容..."
            clearable
            :prefix-icon="Search"
            class="toolbar-search"
          />
          <el-select v-model="chatSort" style="width: 140px">
            <el-option label="按时间排序" value="time" />
            <el-option label="按热度排序" value="hot" />
          </el-select>
        </div>

        <!-- 加载骨架 -->
        <div v-if="chatLoading" class="skeleton-list">
          <div v-for="i in 4" :key="i" class="skeleton-card">
            <div class="sk-line sk-title"></div>
            <div class="sk-line sk-text"></div>
            <div class="sk-line sk-text short"></div>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-else-if="filteredChats.length === 0" class="empty-state">
          <el-empty description="暂无对话记录">
            <el-button type="primary" @click="goToChat">去提问 →</el-button>
          </el-empty>
        </div>

        <!-- 对话列表 -->
        <div v-else class="chat-list">
          <div
            v-for="item in paginatedChats"
            :key="item.id"
            class="chat-card"
          >
            <div class="chat-card-left">
              <h4 class="chat-title">{{ item.title || item.question || '未命名对话' }}</h4>
              <p class="chat-preview">{{ truncateText(item.preview || item.answer || item.content, 80) }}</p>
            </div>
            <div class="chat-card-right">
              <span class="chat-msg-count">{{ item.messageCount || item.messages?.length || 1 }} 条消息</span>
              <span class="chat-time">{{ formatTime(item.timestamp || item.createdAt) }}</span>
              <div class="chat-actions">
                <el-button text type="primary" size="small" @click="continueChat(item)">
                  继续对话
                </el-button>
                <el-button text type="danger" size="small" @click="handleDeleteChat(item)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
          </div>

          <!-- 分页 -->
          <div v-if="filteredChats.length > chatPageSize" class="pagination-row">
            <el-pagination
              v-model:current-page="chatPage"
              :page-size="chatPageSize"
              :total="filteredChats.length"
              layout="prev, pager, next"
              small
              background
            />
          </div>
        </div>
      </div>

      <!-- ===== 收藏视图 ===== -->
      <div v-if="activeTab === 'favorite'" class="content-panel">
        <div class="panel-toolbar">
          <el-input
            v-model="favSearch"
            placeholder="搜索收藏内容..."
            clearable
            :prefix-icon="Search"
            class="toolbar-search"
          />
          <div class="toolbar-batch">
            <el-button text size="small" @click="toggleSelectAllFavorites">
              {{ isAllFavsSelected ? '取消全选' : '全选' }}
            </el-button>
            <el-button
              type="danger"
              text
              size="small"
              :disabled="selectedFavCount === 0"
              @click="batchUnfavorite"
            >
              批量删除 ({{ selectedFavCount }})
            </el-button>
            <el-button text size="small" @click="exportFavorites">
              导出 CSV
            </el-button>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-if="favorites.length === 0" class="empty-state">
          <el-empty description="暂无收藏内容">
            <el-button type="primary" @click="goToGraph">去图谱探索 →</el-button>
          </el-empty>
        </div>

        <!-- 收藏卡片网格 -->
        <div v-else class="fav-grid">
          <div
            v-for="fav in filteredFavorites"
            :key="fav.id"
            class="fav-card"
            :class="{ 'fav-selected': selectedFavIds[fav.id] }"
            @click="navigateToFavorite(fav)"
          >
            <el-checkbox
              :model-value="!!selectedFavIds[fav.id]"
              class="fav-checkbox"
              @click.stop
              @change="toggleFavSelect(fav.id, $event)"
            />
            <div class="fav-card-header">
              <span class="fav-type-badge" :class="fav.type">
                {{ fav.type === 'chat' ? '💬 问答' : '🎯 节点' }}
              </span>
              <el-button
                text
                type="danger"
                size="small"
                class="fav-remove-btn"
                @click.stop="handleUnfavorite(fav)"
              >
                <el-icon><StarFilled /></el-icon>
              </el-button>
            </div>
            <h4 class="fav-title">{{ fav.title }}</h4>
            <p v-if="fav.description" class="fav-desc">{{ truncateText(fav.description, 60) }}</p>
            <div class="fav-meta">
              <span v-if="fav.type === 'chat'" class="fav-source">来源：问答对话</span>
              <span v-else class="fav-node-type" :style="{ color: getTypeColor(fav.nodeType || '') }">
                {{ fav.nodeType || '节点' }}
              </span>
              <span class="fav-time">{{ formatTime(fav.time) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ===== 病例视图 ===== -->
      <div v-if="activeTab === 'case'" class="content-panel">
        <div class="panel-toolbar">
          <el-input
            v-model="caseSearch"
            placeholder="搜索病例..."
            clearable
            :prefix-icon="Search"
            class="toolbar-search"
          />
          <el-select
            v-model="caseSyndromeFilter"
            placeholder="证候筛选"
            clearable
            style="width: 160px"
          >
            <el-option
              v-for="s in allSyndromes"
              :key="s"
              :label="s"
              :value="s"
            />
          </el-select>
          <div class="toolbar-batch">
            <el-button text size="small" @click="toggleSelectAllCases">
              {{ isAllCasesSelected ? '取消全选' : '全选' }}
            </el-button>
            <el-button
              type="danger"
              text
              size="small"
              :disabled="selectedCaseCount === 0"
              @click="batchDeleteCases"
            >
              批量删除 ({{ selectedCaseCount }})
            </el-button>
            <el-button text size="small" @click="exportCases">
              导出 CSV
            </el-button>
          </div>
        </div>

        <!-- 加载骨架 -->
        <div v-if="caseLoading" class="skeleton-list">
          <div v-for="i in 4" :key="i" class="skeleton-card">
            <div class="sk-line sk-title"></div>
            <div class="sk-line sk-text"></div>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-else-if="filteredCases.length === 0" class="empty-state">
          <el-empty description="暂无教学病例">
            <el-button type="primary" @click="goToCaseStudy">去录入 →</el-button>
          </el-empty>
        </div>

        <!-- 病例卡片网格 -->
        <div v-else class="case-grid">
          <div
            v-for="c in filteredCases"
            :key="c.id"
            class="case-card"
            :class="{ 'case-selected': selectedCaseIds[c.id] }"
            @click="openCase(c)"
          >
            <el-checkbox
              :model-value="!!selectedCaseIds[c.id]"
              class="case-checkbox"
              @click.stop
              @change="toggleCaseSelect(c.id, $event)"
            />
            <div class="case-card-header">
              <h4 class="case-name">{{ c.name || '未命名病例' }}</h4>
              <span class="case-gender">{{ c.gender || '' }}</span>
              <span v-if="c.age" class="case-age">{{ c.age }}岁</span>
            </div>
            <p class="case-complaint">{{ truncateText(c.chiefComplaint || c.symptoms, 60) }}</p>
            <div class="case-syndromes">
              <span
                v-for="s in (c.syndromes || [])"
                :key="s"
                class="case-syndrome-tag"
              >
                {{ s }}
              </span>
              <span v-if="!(c.syndromes || []).length" class="case-no-syndrome">待分析</span>
            </div>
            <div class="case-footer">
              <span class="case-time">{{ formatTime(c.createdAt || c.date) }}</span>
              <span class="case-detail-link">查看详情 →</span>
            </div>
            <el-button
              class="case-delete-btn"
              text
              type="danger"
              size="small"
              @click.stop="handleDeleteCase(c)"
            >
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </main>

    <!-- ==================== 删除确认弹窗（由 ElMessageBox 实现，无需 DOM） ==================== -->
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Delete, StarFilled } from '@element-plus/icons-vue'
import { chatApi, caseApi } from '@/api'

const router = useRouter()
const route = useRoute()

// ==================== Tab 状态 ====================
const activeTab = ref<'chat' | 'favorite' | 'case'>('chat')

// ==================== 问答历史 ====================
interface ChatHistoryItem {
  id: string
  title?: string
  question?: string
  answer?: string
  content?: string
  preview?: string
  timestamp?: string
  createdAt?: string
  messageCount?: number
  messages?: any[]
}

const chatHistories = ref<ChatHistoryItem[]>([])
const chatLoading = ref(false)
const chatSearch = ref('')
const chatSort = ref<'time' | 'hot'>('time')
const chatPage = ref(1)
const chatPageSize = ref(10)

// 时间分组
const chatGroups = computed(() => {
  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterdayStart = new Date(todayStart.getTime() - 86400000)

  const today: ChatHistoryItem[] = []
  const yesterday: ChatHistoryItem[] = []
  const earlier: ChatHistoryItem[] = []

  const sorted = [...chatHistories.value].sort((a, b) => {
    const ta = new Date(a.timestamp || a.createdAt || 0).getTime()
    const tb = new Date(b.timestamp || b.createdAt || 0).getTime()
    return tb - ta
  })

  sorted.forEach(item => {
    const t = new Date(item.timestamp || item.createdAt || 0).getTime()
    if (t >= todayStart.getTime()) {
      today.push(item)
    } else if (t >= yesterdayStart.getTime()) {
      yesterday.push(item)
    } else {
      earlier.push(item)
    }
  })

  const groups: { label: string; items: ChatHistoryItem[] }[] = []
  if (today.length) groups.push({ label: '今天', items: today })
  if (yesterday.length) groups.push({ label: '昨天', items: yesterday })
  if (earlier.length) groups.push({ label: '更早', items: earlier })
  return groups
})

const filteredChats = computed(() => {
  let list = [...chatHistories.value]
  if (chatSearch.value) {
    const kw = chatSearch.value.toLowerCase()
    list = list.filter(item =>
      (item.title || item.question || '').toLowerCase().includes(kw) ||
      (item.preview || item.answer || item.content || '').toLowerCase().includes(kw)
    )
  }
  if (chatSort.value === 'time') {
    list.sort((a, b) => new Date(b.timestamp || b.createdAt || 0).getTime() - new Date(a.timestamp || a.createdAt || 0).getTime())
  }
  // 热度排序：按消息数量降序
  if (chatSort.value === 'hot') {
    list.sort((a, b) => (b.messageCount || b.messages?.length || 1) - (a.messageCount || a.messages?.length || 1))
  }
  return list
})

const paginatedChats = computed(() => {
  const start = (chatPage.value - 1) * chatPageSize.value
  return filteredChats.value.slice(start, start + chatPageSize.value)
})

// ==================== 收藏 ====================
interface FavoriteItem {
  id: string
  type: 'chat' | 'graph'
  title: string
  description?: string
  nodeType?: string
  nodeId?: string
  chatId?: string
  time: string
}

const favorites = ref<FavoriteItem[]>([])
const favSearch = ref('')

const filteredFavorites = computed(() => {
  if (!favSearch.value) return favorites.value
  const kw = favSearch.value.toLowerCase()
  return favorites.value.filter(f =>
    f.title.toLowerCase().includes(kw) ||
    (f.description || '').toLowerCase().includes(kw)
  )
})

// ==================== 教学病例 ====================
interface CaseItem {
  id: string
  name?: string
  age?: number | null
  gender?: string
  chiefComplaint?: string
  symptoms?: string
  syndromes?: string[]
  formulas?: string[]
  createdAt?: string
  date?: string
}

const cases = ref<CaseItem[]>([])
const caseLoading = ref(false)
const caseSearch = ref('')
const caseSyndromeFilter = ref('')

const allSyndromes = computed(() => {
  const set = new Set<string>()
  cases.value.forEach(c => (c.syndromes || []).forEach(s => set.add(s)))
  return Array.from(set)
})

const filteredCases = computed(() => {
  let list = [...cases.value]
  if (caseSearch.value) {
    const kw = caseSearch.value.toLowerCase()
    list = list.filter(c =>
      (c.name || '').toLowerCase().includes(kw) ||
      (c.chiefComplaint || c.symptoms || '').toLowerCase().includes(kw)
    )
  }
  if (caseSyndromeFilter.value) {
    list = list.filter(c => (c.syndromes || []).includes(caseSyndromeFilter.value))
  }
  list.sort((a, b) => new Date(b.createdAt || b.date || 0).getTime() - new Date(a.createdAt || a.date || 0).getTime())
  return list
})

// ==================== 工具函数 ====================
const TYPE_COLORS: Record<string, string> = {
  '药材': '#10b981',
  '方剂': '#6366f1',
  '症状': '#f59e0b',
  '证候': '#b91c1c',
}

function getTypeColor(type: string): string {
  return TYPE_COLORS[type] || '#94a3b8'
}

function truncateText(text: string, maxLen: number): string {
  if (!text) return ''
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text
}

function formatTime(dateStr: string): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return dateStr.slice(0, 10)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 172800000) return '昨天'
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// ==================== 数据加载 ====================

async function loadChatHistories() {
  chatLoading.value = true
  try {
    const res: any = await chatApi.getHistory(1, 50)
    if (res?.data?.length > 0) {
      chatHistories.value = res.data
    } else if (Array.isArray(res)) {
      chatHistories.value = res
    } else if (res?.data?.items) {
      chatHistories.value = res.data.items
      // 支持分页
    } else {
      loadLocalChats()
    }
  } catch {
    loadLocalChats()
  } finally {
    chatLoading.value = false
  }
}

function loadLocalChats() {
  chatHistories.value = JSON.parse(localStorage.getItem('tcm_chat_histories') || '[]')
}

function loadFavorites() {
  const chatFavs: FavoriteItem[] = JSON.parse(localStorage.getItem('tcm_chat_favorites') || '[]')
  const graphFavIds: string[] = JSON.parse(localStorage.getItem('graph_favorites') || '[]')

  // 图谱收藏节点可能需要在 GraphBrowse 页面中查看，这里仅展示 ID
  const graphFavs: FavoriteItem[] = graphFavIds.map((id: string) => ({
    id: `graph-${id}`,
    type: 'graph' as const,
    title: `图谱节点 ${id}`,
    nodeId: id,
    nodeType: '',
    time: new Date().toISOString(),
  }))

  favorites.value = [...chatFavs, ...graphFavs].sort((a, b) =>
    new Date(b.time).getTime() - new Date(a.time).getTime()
  )
}

async function loadCases() {
  caseLoading.value = true
  try {
    const res: any = await caseApi.list({ page: 1, pageSize: 50 })
    if (res?.data?.length > 0) {
      cases.value = res.data
    } else if (Array.isArray(res)) {
      cases.value = res
    } else if (res?.data?.items) {
      cases.value = res.data.items
    } else {
      loadLocalCases()
    }
  } catch {
    loadLocalCases()
  } finally {
    caseLoading.value = false
  }
}

function loadLocalCases() {
  cases.value = JSON.parse(localStorage.getItem('tcm_cases') || '[]')
}

// ==================== Tab 切换 ====================

function switchTab(tab: 'chat' | 'favorite' | 'case') {
  activeTab.value = tab
  router.replace({ query: { tab } })
  chatPage.value = 1 // 重置分页
}

// ==================== 问答操作 ====================

function selectChatItem(item: ChatHistoryItem) {
  // 在右侧高亮显示对应条目
  const idx = filteredChats.value.findIndex(c => c.id === item.id)
  if (idx >= 0) {
    chatPage.value = Math.floor(idx / chatPageSize.value) + 1
  }
}

function continueChat(item: ChatHistoryItem) {
  router.push(`/chat?historyId=${item.id}`)
}

async function handleDeleteChat(item: ChatHistoryItem) {
  try {
    await ElMessageBox.confirm('确定删除这条对话记录吗？', '确认删除', {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  try {
    await chatApi.deleteHistory(item.id)
  } catch {
    // 静默处理 API 错误
  }

  chatHistories.value = chatHistories.value.filter(c => c.id !== item.id)
  saveLocalChats()
  ElMessage.success('对话记录已删除')
}

async function handleClearAllChats() {
  try {
    await ElMessageBox.confirm('确定清空所有对话记录吗？此操作不可恢复。', '确认清空', {
      confirmButtonText: '确定清空',
      cancelButtonText: '取消',
      type: 'error',
    })
  } catch {
    return
  }

  chatHistories.value = []
  saveLocalChats()
  ElMessage.success('所有对话记录已清空')
}

function saveLocalChats() {
  localStorage.setItem('tcm_chat_histories', JSON.stringify(chatHistories.value))
}

// ==================== 收藏操作 ====================

function handleUnfavorite(fav: FavoriteItem) {
  if (fav.type === 'chat') {
    const chatFavs: FavoriteItem[] = JSON.parse(localStorage.getItem('tcm_chat_favorites') || '[]')
    localStorage.setItem('tcm_chat_favorites', JSON.stringify(chatFavs.filter(f => f.id !== fav.id)))
  } else {
    const graphFavs: string[] = JSON.parse(localStorage.getItem('graph_favorites') || '[]')
    localStorage.setItem('graph_favorites', JSON.stringify(graphFavs.filter(id => `graph-${id}` !== fav.id)))
  }
  favorites.value = favorites.value.filter(f => f.id !== fav.id)
  ElMessage.success('已取消收藏')
}

function navigateToFavorite(fav: FavoriteItem) {
  if (fav.type === 'chat') {
    router.push(`/chat?historyId=${fav.chatId || fav.id}`)
  } else {
    router.push(`/graph?highlight=${fav.nodeId || fav.id.replace('graph-', '')}`)
  }
}

// ==================== 病例操作 ====================

function openCase(c: CaseItem) {
  router.push(`/case-study?caseId=${c.id}`)
}

async function handleDeleteCase(c: CaseItem) {
  try {
    await ElMessageBox.confirm(`确定删除病例"${c.name || '未命名'}"吗？`, '确认删除', {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  cases.value = cases.value.filter(cs => cs.id !== c.id)
  saveLocalCases()
  ElMessage.success('病例已删除')
}

function saveLocalCases() {
  localStorage.setItem('tcm_cases', JSON.stringify(cases.value))
}

// ==================== 批量选择 & 操作 ====================

const selectedFavIds = ref<Record<string, boolean>>({})
const selectedCaseIds = ref<Record<string, boolean>>({})

const selectedFavCount = computed(() => Object.keys(selectedFavIds.value).filter(k => selectedFavIds.value[k]).length)
const selectedCaseCount = computed(() => Object.keys(selectedCaseIds.value).filter(k => selectedCaseIds.value[k]).length)

const isAllFavsSelected = computed(() =>
  filteredFavorites.value.length > 0 && selectedFavCount.value === filteredFavorites.value.length
)
const isAllCasesSelected = computed(() =>
  filteredCases.value.length > 0 && selectedCaseCount.value === filteredCases.value.length
)

function toggleFavSelect(id: string, val: boolean) {
  selectedFavIds.value = { ...selectedFavIds.value, [id]: val }
}

function toggleCaseSelect(id: string, val: boolean) {
  selectedCaseIds.value = { ...selectedCaseIds.value, [id]: val }
}

function toggleSelectAllFavorites() {
  if (isAllFavsSelected.value) {
    selectedFavIds.value = {}
  } else {
    const all: Record<string, boolean> = {}
    filteredFavorites.value.forEach(f => { all[f.id] = true })
    selectedFavIds.value = all
  }
}

function toggleSelectAllCases() {
  if (isAllCasesSelected.value) {
    selectedCaseIds.value = {}
  } else {
    const all: Record<string, boolean> = {}
    filteredCases.value.forEach(c => { all[c.id] = true })
    selectedCaseIds.value = all
  }
}

async function batchUnfavorite() {
  if (selectedFavCount.value === 0) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedFavCount.value} 条收藏吗？`,
      '批量取消收藏',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }

  const ids = new Set(Object.keys(selectedFavIds.value).filter(k => selectedFavIds.value[k]))
  favorites.value = favorites.value.filter(f => !ids.has(f.id))

  // 同步更新 localStorage
  const chatFavs: FavoriteItem[] = JSON.parse(localStorage.getItem('tcm_chat_favorites') || '[]')
  localStorage.setItem('tcm_chat_favorites', JSON.stringify(chatFavs.filter(f => !ids.has(f.id))))
  const graphFavs: string[] = JSON.parse(localStorage.getItem('graph_favorites') || '[]')
  localStorage.setItem('graph_favorites', JSON.stringify(graphFavs.filter(gid => !ids.has(`graph-${gid}`))))

  selectedFavIds.value = {}
  ElMessage.success(`已删除 ${ids.size} 条收藏`)
}

async function batchDeleteCases() {
  if (selectedCaseCount.value === 0) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedCaseCount.value} 个病例吗？此操作不可恢复。`,
      '批量删除病例',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }

  const ids = new Set(Object.keys(selectedCaseIds.value).filter(k => selectedCaseIds.value[k]))
  cases.value = cases.value.filter(c => !ids.has(c.id))
  saveLocalCases()
  selectedCaseIds.value = {}
  ElMessage.success(`已删除 ${ids.size} 个病例`)
}

function exportFavorites() {
  const hasSelection = selectedFavCount.value > 0
  const data = (hasSelection
    ? favorites.value.filter(f => selectedFavIds.value[f.id])
    : favorites.value
  ).map(f => ({
    '类型': f.type === 'chat' ? '问答' : '图谱节点',
    '标题': f.title,
    '描述': f.description || '',
    '节点类型': f.nodeType || '',
    '时间': formatTime(f.time),
  }))
  if (data.length === 0) {
    ElMessage.warning('没有可导出的数据')
    return
  }
  exportCSV(data, ['类型', '标题', '描述', '节点类型', '时间'], '收藏列表')
}

function exportCases() {
  const hasSelection = selectedCaseCount.value > 0
  const data = (hasSelection
    ? cases.value.filter(c => selectedCaseIds.value[c.id])
    : cases.value
  ).map(c => ({
    '名称': c.name || '未命名',
    '年龄': c.age ?? '',
    '性别': c.gender || '',
    '主诉': c.chiefComplaint || c.symptoms || '',
    '证候': (c.syndromes || []).join('、'),
    '方剂': (c.formulas || []).join('、'),
    '时间': formatTime(c.createdAt || c.date || ''),
  }))
  if (data.length === 0) {
    ElMessage.warning('没有可导出的数据')
    return
  }
  exportCSV(data, ['名称', '年龄', '性别', '主诉', '证候', '方剂', '时间'], '病例列表')
}

function exportCSV(data: Record<string, any>[], headers: string[], filename: string) {
  const BOM = '﻿' // Excel 识别 UTF-8 中文
  const headerRow = headers.join(',')
  const rows = data.map(row =>
    headers.map(h => {
      const val = (row[h] ?? '').toString()
      return `"${val.replace(/"/g, '""')}"`
    }).join(',')
  )
  const csv = BOM + headerRow + '\n' + rows.join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `${filename}_${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  ElMessage.success(`已导出 ${data.length} 条记录`)
}

// ==================== 路由跳转 ====================

function goToChat() {
  router.push('/chat')
}

function goToGraph() {
  router.push('/graph')
}

function goToCaseStudy() {
  router.push('/case-study')
}

// ==================== 生命周期 ====================

onMounted(() => {
  // 读取 URL query 参数设置初始 tab
  const tabParam = route.query.tab as string
  if (tabParam === 'favorite' || tabParam === 'case' || tabParam === 'chat') {
    activeTab.value = tabParam
  }

  // 并行加载数据
  loadChatHistories()
  loadFavorites()
  loadCases()
})

// 监听 tab 变化，刷新对应数据
watch(activeTab, (tab) => {
  if (tab === 'chat') loadChatHistories()
  if (tab === 'favorite') loadFavorites()
  if (tab === 'case') loadCases()
})
</script>

<style scoped lang="scss">
// ==================== 变量 ====================
$bg-warm: #faf8f5;
$card-bg: #ffffff;
$card-radius: 12px;
$text-dark: #1e293b;
$text-body: #475569;
$text-muted: #94a3b8;
$indigo: #6366f1;
$indigo-light: #eef2ff;
$rose: #b91c1c;
$border-light: #e2e8f0;

// ==================== 主容器 ====================
.history-page {
  display: flex;
  gap: 20px;
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
  min-height: calc(100vh - 64px - 60px);
  background: $bg-warm;
  border-radius: 8px;
}

// ==================== 左侧栏 ====================
.left-sidebar {
  width: 30%;
  min-width: 270px;
  max-width: 350px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  flex-shrink: 0;
}

.sidebar-card {
  background: $card-bg;
  border-radius: $card-radius;
  padding: 16px;
  border: 2px solid transparent;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.04);

  &:hover {
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  }

  &.active {
    border-color: $indigo;
    box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.1);
  }

  .sc-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;

    .sc-icon {
      font-size: 18px;
    }
    .sc-title {
      font-size: 15px;
      font-weight: 600;
      color: $text-dark;
      flex: 1;
    }
    .sc-count {
      font-size: 12px;
      color: $text-muted;
      background: #f1f5f9;
      padding: 2px 10px;
      border-radius: 12px;
      font-weight: 500;
    }
  }

  .sc-preview {
    .sc-empty {
      color: $text-muted;
      font-size: 13px;
      padding: 8px 0;
      text-align: center;
    }

    .sc-group {
      margin-bottom: 8px;

      .sc-group-label {
        font-size: 11px;
        color: $text-muted;
        font-weight: 500;
        display: block;
        margin-bottom: 4px;
        padding-left: 2px;
      }
    }

    .sc-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 8px;
      border-radius: 6px;
      transition: background 0.2s;

      &:hover {
        background: #f8fafc;
      }

      .sci-title {
        flex: 1;
        font-size: 13px;
        color: $text-dark;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .sci-count {
        font-size: 11px;
        color: $text-muted;
        flex-shrink: 0;
      }

      .sci-time {
        font-size: 11px;
        color: #a1a1aa;
        flex-shrink: 0;
      }

      .sci-syndrome {
        font-size: 11px;
        color: $rose;
        font-weight: 500;
        flex-shrink: 0;
        max-width: 80px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .sci-type-tag {
        font-size: 13px;
        flex-shrink: 0;
      }
    }
  }

  .sc-footer {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid $border-light;
    text-align: center;
  }
}

// ==================== 右侧内容 ====================
.right-content {
  flex: 1;
  min-width: 0;
}

.content-panel {
  background: $card-bg;
  border-radius: $card-radius;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  min-height: 100%;
}

// 工具栏
.panel-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
  align-items: center;

  .toolbar-search {
    max-width: 320px;
  }

  .toolbar-batch {
    display: flex;
    gap: 6px;
    align-items: center;
    margin-left: auto;
  }
}

// ==================== 对话列表 ====================
.chat-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border: 1px solid $border-light;
  border-radius: 10px;
  margin-bottom: 10px;
  transition: all 0.25s;

  &:hover {
    border-color: $indigo;
    box-shadow: 0 2px 12px rgba(99, 102, 241, 0.08);
  }

  .chat-card-left {
    flex: 1;
    min-width: 0;

    .chat-title {
      margin: 0 0 6px 0;
      font-size: 15px;
      color: $text-dark;
      font-weight: 600;
    }

    .chat-preview {
      margin: 0;
      font-size: 13px;
      color: $text-muted;
      line-height: 1.5;
    }
  }

  .chat-card-right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 6px;
    flex-shrink: 0;
    margin-left: 16px;

    .chat-msg-count {
      font-size: 12px;
      color: $text-muted;
    }

    .chat-time {
      font-size: 11px;
      color: #a1a1aa;
    }

    .chat-actions {
      display: flex;
      gap: 6px;
    }
  }
}

.pagination-row {
  display: flex;
  justify-content: center;
  padding-top: 16px;
}

// ==================== 收藏网格 ====================
.fav-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.fav-card {
  background: #fafbfc;
  border: 1px solid $border-light;
  border-radius: 10px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.25s;
  position: relative;

  .fav-checkbox {
    position: absolute;
    top: 12px;
    left: 12px;
    z-index: 2;
  }

  &.fav-selected {
    border-color: $indigo;
    background: $indigo-light;
  }

  &:hover {
    border-color: $indigo;
    box-shadow: 0 4px 16px rgba(99, 102, 241, 0.1);
    transform: translateY(-2px);

    .fav-remove-btn {
      opacity: 1;
    }
  }

  .fav-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;

    .fav-type-badge {
      font-size: 11px;
      padding: 3px 10px;
      border-radius: 12px;
      background: #f1f5f9;
      color: $text-body;

      &.chat {
        background: #eef2ff;
        color: $indigo;
      }
      &.graph {
        background: #ecfdf5;
        color: #059669;
      }
    }

    .fav-remove-btn {
      opacity: 0;
      transition: opacity 0.2s;
    }
  }

  .fav-title {
    margin: 0 0 8px 0;
    font-size: 15px;
    color: $text-dark;
    font-weight: 600;
  }

  .fav-desc {
    margin: 0 0 10px 0;
    font-size: 13px;
    color: $text-muted;
    line-height: 1.5;
  }

  .fav-meta {
    display: flex;
    justify-content: space-between;
    font-size: 11px;

    .fav-source {
      color: $text-muted;
    }

    .fav-node-type {
      font-weight: 500;
    }

    .fav-time {
      color: #a1a1aa;
    }
  }
}

// ==================== 病例网格 ====================
.case-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.case-card {
  background: #fafbfc;
  border: 1px solid $border-light;
  border-radius: 10px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.25s;
  position: relative;

  .case-checkbox {
    position: absolute;
    top: 12px;
    left: 12px;
    z-index: 2;
  }

  &.case-selected {
    border-color: $rose;
    background: #fdf2f8;
  }

  &:hover {
    border-color: $indigo;
    box-shadow: 0 4px 16px rgba(99, 102, 241, 0.1);
    transform: translateY(-2px);

    .case-delete-btn {
      opacity: 1;
    }
  }

  .case-card-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;

    .case-name {
      margin: 0;
      font-size: 16px;
      color: $text-dark;
      font-weight: 600;
    }

    .case-gender,
    .case-age {
      font-size: 12px;
      color: $text-muted;
    }
  }

  .case-complaint {
    margin: 0 0 10px 0;
    font-size: 13px;
    color: $text-body;
    line-height: 1.5;
  }

  .case-syndromes {
    margin-bottom: 12px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;

    .case-syndrome-tag {
      padding: 3px 12px;
      background: #fdf2f8;
      color: $rose;
      border-radius: 14px;
      font-size: 12px;
      font-weight: 500;
    }

    .case-no-syndrome {
      font-size: 12px;
      color: $text-muted;
      font-style: italic;
    }
  }

  .case-footer {
    display: flex;
    justify-content: space-between;
    font-size: 11px;

    .case-time {
      color: #a1a1aa;
    }

    .case-detail-link {
      color: $indigo;
      font-weight: 500;
    }
  }

  .case-delete-btn {
    position: absolute;
    top: 10px;
    right: 10px;
    opacity: 0;
    transition: opacity 0.2s;
  }
}

// ==================== 骨架屏 ====================
.skeleton-list {
  .skeleton-card {
    padding: 16px;
    border: 1px solid $border-light;
    border-radius: 10px;
    margin-bottom: 10px;

    .sk-line {
      height: 14px;
      background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
      background-size: 200% 100%;
      animation: shimmer 1.5s ease-in-out infinite;
      border-radius: 4px;
      margin-bottom: 8px;

      &.sk-title {
        width: 60%;
        height: 18px;
      }
      &.sk-text {
        width: 90%;
      }
      &.short {
        width: 40%;
      }
    }
  }
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

// ==================== 空状态 ====================
.empty-state {
  padding: 60px 20px;
  text-align: center;
}

// ==================== 响应式 ====================
@media (max-width: 1024px) {
  .history-page {
    flex-direction: column;
  }

  .left-sidebar {
    width: 100%;
    max-width: 100%;
    min-width: 0;
    flex-direction: row;
    overflow-x: auto;

    .sidebar-card {
      min-width: 180px;
      flex-shrink: 0;

      .sc-preview {
        display: none;
      }
      .sc-footer {
        display: none;
      }
    }
  }

  .right-content {
    width: 100%;
  }
}

@media (max-width: 768px) {
  .history-page {
    padding: 10px;
  }

  .content-panel {
    padding: 16px;
  }

  .fav-grid,
  .case-grid {
    grid-template-columns: 1fr;
  }

  .chat-card {
    flex-direction: column;
    align-items: flex-start;

    .chat-card-right {
      flex-direction: row;
      align-items: center;
      margin-left: 0;
      margin-top: 10px;
      width: 100%;
    }
  }

  .panel-toolbar {
    flex-direction: column;
  }
}

.history-page {
  margin-top: -800px;
  
  @media (max-width: 1200px) {
    margin-top: -1020px;
  }
}
</style>