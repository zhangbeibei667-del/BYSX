<template>
  <div class="record-manage">
    <!-- 顶部操作栏 -->
    <div class="page-header">
      <h2 class="page-title">问答记录管理</h2>
      <div class="header-actions">
        <el-button :icon="Download" @click="handleExportAll">导出全部记录</el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-cards">
      <div class="stat-card">
        <div class="stat-value">{{ stats.today }}</div>
        <div class="stat-label">今日问答</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.thisWeek }}</div>
        <div class="stat-label">本周问答</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">累计问答</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.favorites }}</div>
        <div class="stat-label">收藏数量</div>
      </div>
    </div>

    <!-- 搜索筛选栏 -->
    <div class="search-bar">
      <el-input
        v-model="searchParams.keyword"
        placeholder="搜索问题/回答关键词..."
        clearable
        style="width: 260px"
        @keyup.enter="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-date-picker
        v-model="searchParams.dateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        format="YYYY-MM-DD"
        value-format="YYYY-MM-DD"
        style="width: 260px"
      />
      <el-select
        v-model="searchParams.isFavorite"
        placeholder="收藏状态"
        clearable
        style="width: 130px"
      >
        <el-option label="已收藏" :value="true" />
        <el-option label="未收藏" :value="false" />
      </el-select>
      <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
      <el-button :icon="Refresh" @click="handleReset">重置</el-button>

      <el-button
        v-if="selectedRows.length > 0"
        type="danger"
        :icon="Delete"
        @click="handleBatchDelete"
      >
        批量删除 ({{ selectedRows.length }})
      </el-button>
    </div>

    <!-- 数据表格 -->
    <div class="table-wrapper">
    <el-table
      ref="tableRef"
      v-loading="loading"
      :data="tableData"
      border
      stripe
      row-key="id"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="50" align="center" />
      <el-table-column type="index" label="序号" width="65" align="center" />
      <el-table-column prop="id" label="编号" width="100" align="center" />
      <el-table-column label="用户问题" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="question-text">{{ truncate(row.question, 50) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="回答摘要" min-width="240" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="answer-text">{{ truncate(row.answer, 60) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="关联实体" min-width="200">
        <template #default="{ row }">
          <div class="tag-list" v-if="getAllRelatedEntities(row).length">
            <el-tag
              v-for="(entity, i) in getAllRelatedEntities(row).slice(0, 4)"
              :key="i"
              :type="getEntityTypeColor(entity.type)"
              size="small"
              effect="light"
            >
              {{ entity.name }}
            </el-tag>
            <el-tag v-if="getAllRelatedEntities(row).length > 4" size="small" type="info">
              +{{ getAllRelatedEntities(row).length - 4 }}
            </el-tag>
          </div>
          <span v-else class="text-placeholder">-</span>
        </template>
      </el-table-column>
      <el-table-column label="收藏" width="80" align="center">
        <template #default="{ row }">
          <el-icon v-if="row.isFavorite" color="#f59e0b" :size="18">
            <StarFilled />
          </el-icon>
          <el-icon v-else color="#c0c4cc" :size="18">
            <Star />
          </el-icon>
        </template>
      </el-table-column>
      <el-table-column label="提问时间" width="170" align="center">
        <template #default="{ row }">
          {{ formatDate(row.createdAt) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" align="center" fixed="right">
        <template #default="{ row }">
          <el-button type="info" link size="small" @click="handleView(row)">
            <el-icon><View /></el-icon>
            详情
          </el-button>
          <el-button
            type="warning"
            link
            size="small"
            @click="handleToggleFavorite(row)"
          >
            <el-icon><StarFilled v-if="row.isFavorite" /><Star v-else /></el-icon>
            {{ row.isFavorite ? '取消' : '收藏' }}
          </el-button>
          <el-button type="danger" link size="small" @click="handleDelete(row)">
            <el-icon><Delete /></el-icon>
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    </div>

    <!-- 分页 -->
    <div class="pagination-wrapper">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </div>

    <!-- 查看详情弹窗 -->
    <el-dialog
      v-model="viewDialogVisible"
      :title="`问答详情`"
      width="850px"
      :close-on-click-modal="false"
    >
      <div v-if="viewRecord" class="view-record-content">
        <!-- 用户问题 -->
        <div class="qa-section">
          <div class="section-header question-header">
            <el-icon :size="16"><UserFilled /></el-icon>
            <span>用户提问</span>
            <span class="section-time">{{ formatDate(viewRecord.createdAt) }}</span>
          </div>
          <div class="question-body">{{ viewRecord.question }}</div>
        </div>

        <!-- Agent回答 -->
        <div class="qa-section">
          <div class="section-header answer-header">
            <el-icon :size="16"><ChatDotRound /></el-icon>
            <span>Agent 回答</span>
            <el-tag
              v-if="viewRecord.isFavorite"
              size="small"
              type="warning"
              effect="plain"
            >
              已收藏
            </el-tag>
          </div>
          <div class="answer-body markdown-body" v-html="renderMarkdown(viewRecord.answer || '')"></div>
        </div>

        <!-- 关联图谱实体 -->
        <div class="related-section" v-if="getAllRelatedEntities(viewRecord).length">
          <h4 class="section-title">关联图谱实体</h4>
          <div class="entity-group" v-if="viewRecord.herbs?.length">
            <span class="entity-type-label">药材：</span>
            <el-tag
              v-for="(h, i) in viewRecord.herbs"
              :key="'h' + i"
              size="small"
              type="success"
              effect="light"
            >{{ h }}</el-tag>
          </div>
          <div class="entity-group" v-if="viewRecord.formulas?.length">
            <span class="entity-type-label">方剂：</span>
            <el-tag
              v-for="(f, i) in viewRecord.formulas"
              :key="'f' + i"
              size="small"
              type="primary"
              effect="light"
            >{{ f }}</el-tag>
          </div>
          <div class="entity-group" v-if="viewRecord.symptoms?.length">
            <span class="entity-type-label">症状：</span>
            <el-tag
              v-for="(s, i) in viewRecord.symptoms"
              :key="'s' + i"
              size="small"
              type="danger"
              effect="light"
            >{{ s }}</el-tag>
          </div>
          <div class="entity-group" v-if="viewRecord.syndromes?.length">
            <span class="entity-type-label">证候：</span>
            <el-tag
              v-for="(sy, i) in viewRecord.syndromes"
              :key="'sy' + i"
              size="small"
              type="warning"
              effect="light"
            >{{ sy }}</el-tag>
          </div>
        </div>

        <!-- 引用文献片段 -->
        <div class="evidence-section" v-if="viewRecord.evidence?.length">
          <h4 class="section-title">引用文献片段</h4>
          <div
            v-for="(ev, i) in viewRecord.evidence"
            :key="'ev' + i"
            class="evidence-item"
          >
            <div class="evidence-title">
              <el-icon :size="14"><Document /></el-icon>
              {{ ev.title }}
            </div>
            <div class="evidence-content">{{ ev.content }}</div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 删除确认弹窗 -->
    <el-dialog
      v-model="deleteDialogVisible"
      title="确认删除"
      width="420px"
      :close-on-click-modal="false"
    >
      <div class="delete-confirm-content">
        <el-icon class="delete-icon" :size="48" color="#f56c6c">
          <WarningFilled />
        </el-icon>
        <p class="delete-message">{{ deleteMessage }}</p>
      </div>
      <template #footer>
        <el-button @click="deleteDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="deleteLoading" @click="confirmDelete">
          确认删除
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import {
  Download,
  Search,
  Refresh,
  Delete,
  View,
  Star,
  StarFilled,
  WarningFilled,
  UserFilled,
  ChatDotRound,
  Document
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { recordApi } from '@/api'
import type { RecordEntity } from '@/types'

// ==================== 统计卡片 ====================
const stats = reactive({
  today: 0,
  thisWeek: 0,
  total: 0,
  favorites: 0
})

const fetchStats = async () => {
  try {
    const res: any = await recordApi.getStats()
    if (res.code === 200 && res.data) {
      stats.today = res.data.today ?? 0
      stats.thisWeek = res.data.thisWeek ?? 0
      stats.total = res.data.total ?? 0
      stats.favorites = res.data.favorites ?? 0
    }
  } catch (error) {
    console.error('获取统计数据失败:', error)
  }
}

// ==================== 工具函数 ====================
const truncate = (text?: string, maxLen = 50): string => {
  if (!text) return '-'
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text
}

const entityTypeColorMap: Record<string, string> = {
  '药材': 'success',
  '方剂': 'primary',
  '症状': 'danger',
  '证候': 'warning'
}

const getEntityTypeColor = (type: string): string => {
  return entityTypeColorMap[type] || 'info'
}

interface RelatedEntity {
  name: string
  type: string
}

const getAllRelatedEntities = (record: RecordEntity | null): RelatedEntity[] => {
  if (!record) return []
  const list: RelatedEntity[] = []
  if (record.herbs) record.herbs.forEach((h) => list.push({ name: h, type: '药材' }))
  if (record.formulas) record.formulas.forEach((f) => list.push({ name: f, type: '方剂' }))
  if (record.symptoms) record.symptoms.forEach((s) => list.push({ name: s, type: '症状' }))
  if (record.syndromes) record.syndromes.forEach((sy) => list.push({ name: sy, type: '证候' }))
  return list
}

const formatDate = (dateStr?: string): string => {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${min}`
}

// ==================== Markdown 渲染 ====================
const renderMarkdown = (text: string): string => {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h4 style="margin:16px 0 8px;color:#303133">$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 style="margin:20px 0 10px;color:#303133">$1</h3>')
    .replace(/^# (.+)$/gm, '<h2 style="margin:24px 0 12px;color:#303133">$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^- (.+)$/gm, '<li style="margin-left:20px">$1</li>')
    .replace(/^> (.+)$/gm, '<blockquote style="border-left:3px solid #dcdfe6;padding:4px 12px;color:#909399;margin:8px 0">$1</blockquote>')
    .replace(/\n/g, '<br/>')
}

// ==================== 表格数据 ====================
const tableRef = ref()
const loading = ref(false)
const tableData = ref<RecordEntity[]>([])
const selectedRows = ref<RecordEntity[]>([])

const searchParams = reactive({
  keyword: '',
  dateRange: [] as string[],
  isFavorite: undefined as boolean | undefined
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const fetchData = async () => {
  loading.value = true
  try {
    const [startDate, endDate] = searchParams.dateRange || []
    const res: any = await recordApi.list({
      page: pagination.page,
      pageSize: pagination.pageSize,
      keyword: searchParams.keyword || undefined,
      startDate: startDate || undefined,
      endDate: endDate || undefined,
      isFavorite: searchParams.isFavorite
    })
    if (res.code === 200) {
      tableData.value = res.data?.list ?? res.data?.records ?? []
      pagination.total = res.data?.total ?? 0
    } else if (Array.isArray(res)) {
      tableData.value = res
      pagination.total = res.length
    } else if (res.data && Array.isArray(res.data)) {
      tableData.value = res.data
      pagination.total = res.total ?? res.data.length
    } else {
      tableData.value = []
      pagination.total = 0
    }
  } catch (error) {
    console.error('获取问答记录失败:', error)
    ElMessage.error('获取问答记录失败')
  } finally {
    loading.value = false
  }
}

// ==================== 搜索 ====================
const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchParams.keyword = ''
  searchParams.dateRange = []
  searchParams.isFavorite = undefined
  handleSearch()
}

const handleSelectionChange = (rows: RecordEntity[]) => {
  selectedRows.value = rows
}

// ==================== 导出 ====================
const handleExportAll = async () => {
  try {
    const [startDate, endDate] = searchParams.dateRange || []
    const res: any = await recordApi.export({
      keyword: searchParams.keyword || undefined,
      startDate: startDate || undefined,
      endDate: endDate || undefined,
      isFavorite: searchParams.isFavorite
    })
    const blob = res instanceof Blob ? res : new Blob([res], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `问答记录_${new Date().toISOString().slice(0, 10)}.xlsx`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
    console.error('导出失败:', error)
  }
}

// ==================== 查看详情 ====================
const viewDialogVisible = ref(false)
const viewRecord = ref<RecordEntity | null>(null)

const handleView = (row: RecordEntity) => {
  viewRecord.value = row
  viewDialogVisible.value = true
}

// ==================== 收藏切换 ====================
const handleToggleFavorite = async (row: RecordEntity) => {
  try {
    await recordApi.toggleFavorite(row.id)
    row.isFavorite = !row.isFavorite
    ElMessage.success(row.isFavorite ? '已收藏' : '已取消收藏')
  } catch (error) {
    console.error('操作失败:', error)
    ElMessage.error('操作失败')
  }
}

// ==================== 删除 ====================
const deleteDialogVisible = ref(false)
const deleteLoading = ref(false)
const isBatchDelete = ref(false)
const deleteTarget = ref<RecordEntity | null>(null)

const deleteMessage = computed(() => {
  if (isBatchDelete.value) {
    return `确认删除选中的 ${selectedRows.value.length} 条问答记录？此操作不可恢复。`
  }
  return `确认删除该问答记录？此操作不可恢复。`
})

const handleDelete = (row: RecordEntity) => {
  isBatchDelete.value = false
  deleteTarget.value = row
  deleteDialogVisible.value = true
}

const handleBatchDelete = () => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要删除的记录')
    return
  }
  isBatchDelete.value = true
  deleteTarget.value = null
  deleteDialogVisible.value = true
}

const confirmDelete = async () => {
  deleteLoading.value = true
  try {
    if (isBatchDelete.value) {
      const ids = selectedRows.value.map((row) => row.id)
      await recordApi.batchDelete(ids)
      ElMessage.success(`成功删除 ${ids.length} 条记录`)
    } else if (deleteTarget.value) {
      await recordApi.delete(deleteTarget.value.id)
      ElMessage.success('删除成功')
    }
    deleteDialogVisible.value = false
    tableRef.value?.clearSelection()
    fetchData()
    fetchStats()
  } catch (error) {
    console.error('删除失败:', error)
    ElMessage.error('删除失败，请重试')
  } finally {
    deleteLoading.value = false
  }
}

// ==================== 初始化 ====================
onMounted(() => {
  fetchData()
  fetchStats()
})
</script>

<style scoped lang="scss">
.record-manage {
  padding: 20px;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    .page-title {
      margin: 0;
      font-size: 22px;
      font-weight: 600;
      color: #303133;
    }

    .header-actions {
      display: flex;
      gap: 10px;
    }
  }

  // 统计卡片
  .stats-cards {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 20px;

    .stat-card {
      text-align: center;
      padding: 20px 16px;
      background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
      border-radius: 8px;
      border: 1px solid #ebeef5;
      transition: box-shadow 0.3s;

      &:hover {
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
      }

      .stat-value {
        font-size: 32px;
        font-weight: 700;
        color: #409eff;
        margin-bottom: 6px;
        line-height: 1.2;
      }

      .stat-label {
        font-size: 14px;
        color: #909399;
      }
    }
  }

  .search-bar {
    display: flex;
    gap: 12px;
    align-items: center;
    margin-bottom: 16px;
    padding: 16px;
    background-color: #f5f7fa;
    border-radius: 6px;
    flex-wrap: wrap;
  }

  .question-text {
    color: #303133;
  }

  .answer-text {
    color: #606266;
  }

  .tag-list {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    padding: 2px 0;
  }

  .text-placeholder {
    color: #c0c4cc;
    font-size: 13px;
  }

  .pagination-wrapper {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }

  .table-wrapper {
    width: 100%;
    overflow-x: auto;
  }

  // 查看详情弹窗
  .view-record-content {
    .qa-section {
      margin-bottom: 20px;

      .section-header {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 14px;
        border-radius: 6px 6px 0 0;
        font-size: 14px;
        font-weight: 600;

        .section-time {
          margin-left: auto;
          font-size: 12px;
          font-weight: 400;
          color: #909399;
        }
      }

      .question-header {
        background-color: #ecf5ff;
        color: #409eff;
      }

      .answer-header {
        background-color: #f0f9eb;
        color: #67c23a;
      }

      .question-body {
        padding: 14px;
        background: #fafafa;
        border: 1px solid #ebeef5;
        border-top: none;
        border-radius: 0 0 6px 6px;
        font-size: 15px;
        color: #303133;
        line-height: 1.8;
        white-space: pre-wrap;
      }

      .answer-body {
        padding: 14px;
        background: #fafafa;
        border: 1px solid #ebeef5;
        border-top: none;
        border-radius: 0 0 6px 6px;
        line-height: 1.8;
        color: #303133;
        font-size: 14px;
        max-height: 350px;
        overflow-y: auto;
      }
    }

    .related-section,
    .evidence-section {
      margin-bottom: 16px;

      .section-title {
        margin: 0 0 10px 0;
        font-size: 15px;
        color: #303133;
        padding-bottom: 8px;
        border-bottom: 1px solid #ebeef5;
      }

      .entity-group {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
        margin-bottom: 8px;

        .entity-type-label {
          font-size: 13px;
          color: #909399;
          min-width: 48px;
        }
      }
    }

    .evidence-item {
      padding: 12px;
      margin-bottom: 10px;
      background: #f5f7fa;
      border-radius: 6px;
      border-left: 3px solid #409eff;

      .evidence-title {
        font-size: 14px;
        font-weight: 600;
        color: #303133;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 6px;
      }

      .evidence-content {
        font-size: 13px;
        color: #606266;
        line-height: 1.7;
      }
    }
  }

  // 删除确认弹窗
  .delete-confirm-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 16px 0;

    .delete-icon {
      margin-bottom: 16px;
    }

    .delete-message {
      font-size: 15px;
      color: #303133;
      text-align: center;
      line-height: 1.6;
    }
  }
}
</style>
