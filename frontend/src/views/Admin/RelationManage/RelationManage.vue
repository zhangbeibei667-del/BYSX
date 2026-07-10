<template>
  <div class="relation-manage">
    <!-- 顶部操作栏 -->
    <div class="page-header">
      <h2 class="page-title">图谱关系维护</h2>
      <div class="header-actions">
        <el-button type="primary" :icon="Plus" @click="handleAdd">新增关系</el-button>
        <el-button type="warning" :icon="WarningFilled" @click="handleCleanInvalid">
          清除无效关系
        </el-button>
      </div>
    </div>

    <!-- 搜索筛选栏 -->
    <div class="search-bar">
      <el-input
        v-model="searchParams.sourceName"
        placeholder="源实体名称..."
        clearable
        style="width: 220px"
        @keyup.enter="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-input
        v-model="searchParams.targetName"
        placeholder="目标实体名称..."
        clearable
        style="width: 220px"
        @keyup.enter="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-select
        v-model="searchParams.relation"
        placeholder="关系类型"
        clearable
        style="width: 180px"
      >
        <el-option
          v-for="rel in relationTypeOptions"
          :key="rel"
          :label="rel"
          :value="rel"
        />
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
      :row-key="getRowKey"
      style="width: 100%;"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="50" align="center" reserve-selection />
      <el-table-column type="index" label="序号" width="65" align="center" />
      <el-table-column label="源实体" width="200">
        <template #default="{ row }">
          <div class="entity-cell">
            <el-tag
              :type="getTypeTagColor(row.source_type)"
              size="small"
              effect="dark"
            >
              {{ row.source_type || '实体' }}
            </el-tag>
            <span class="entity-name">{{ row.source_name }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="关系" width="100" align="center">
        <template #default="{ row }">
          <el-tag
            :type="getRelationTagColor(row.relation)"
            size="small"
            effect="plain"
          >
            {{ row.relation }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="目标实体" width="200">
        <template #default="{ row }">
          <div class="entity-cell">
            <el-tag
              :type="getTypeTagColor(row.target_type)"
              size="small"
              effect="dark"
            >
              {{ row.target_type || '实体' }}
            </el-tag>
            <span class="entity-name">{{ row.target_name }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="依据/来源" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.evidence || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" align="center" fixed="right">
        <template #default="{ row }">
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

    <!-- 新增关系弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      title="新增关系"
      width="650px"
      :close-on-click-modal="false"
      @closed="resetForm"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="80px"
        label-position="right"
      >
        <el-form-item label="源实体" prop="source_id">
          <div class="entity-picker">
            <el-select
              v-model="formData.source_type_filter"
              placeholder="类型筛选"
              style="width: 110px"
              @change="handleSourceTypeChange"
            >
              <el-option label="全部" value="" />
              <el-option
                v-for="t in entityTypeOptions"
                :key="t"
                :label="t"
                :value="t"
              />
            </el-select>
            <el-select
              v-model="formData.source_id"
              filterable
              placeholder="搜索并选择源实体"
              style="flex: 1"
              :loading="entityLoading"
              @change="handleSourceSelect"
            >
              <el-option
                v-for="e in filteredSourceEntities"
                :key="e._key"
                :label="e.name"
                :value="e._key"
              >
                <div class="entity-option">
                  <span class="entity-name">{{ e.name }}</span>
                  <el-tag size="small" :type="getTypeTagColor(e.type)">{{ e.type }}</el-tag>
                </div>
              </el-option>
            </el-select>
          </div>
          <div v-if="formData.source_id" class="selected-entity-preview">
            <el-tag :type="getTypeTagColor(formData.source_type)" size="small" effect="dark">
              {{ formData.source_type }}
            </el-tag>
            <span>{{ formData.source_name }}</span>
          </div>
        </el-form-item>

        <el-form-item label="关系类型" prop="relation">
          <el-select v-model="formData.relation" placeholder="请选择关系类型" style="width: 100%">
            <el-option
              v-for="rel in relationTypeOptions"
              :key="rel"
              :label="rel"
              :value="rel"
            >
              <div class="relation-option">
                <span>{{ rel }}</span>
                <span class="relation-desc">{{ relationDescriptions[rel] }}</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item label="目标实体" prop="target_id">
          <div class="entity-picker">
            <el-select
              v-model="formData.target_type_filter"
              placeholder="类型筛选"
              style="width: 110px"
              @change="handleTargetTypeChange"
            >
              <el-option label="全部" value="" />
              <el-option
                v-for="t in entityTypeOptions"
                :key="t"
                :label="t"
                :value="t"
              />
            </el-select>
            <el-select
              v-model="formData.target_id"
              filterable
              placeholder="搜索并选择目标实体"
              style="flex: 1"
              :loading="entityLoading"
              @change="handleTargetSelect"
            >
              <el-option
                v-for="e in filteredTargetEntities"
                :key="e._key"
                :label="e.name"
                :value="e._key"
              >
                <div class="entity-option">
                  <span class="entity-name">{{ e.name }}</span>
                  <el-tag size="small" :type="getTypeTagColor(e.type)">{{ e.type }}</el-tag>
                </div>
              </el-option>
            </el-select>
          </div>
          <div v-if="formData.target_id" class="selected-entity-preview">
            <el-tag :type="getTypeTagColor(formData.target_type)" size="small" effect="dark">
              {{ formData.target_type }}
            </el-tag>
            <span>{{ formData.target_name }}</span>
          </div>
        </el-form-item>

        <el-form-item label="依据/证据" prop="evidence">
          <el-input
            v-model="formData.evidence"
            type="textarea"
            :rows="2"
            placeholder="请输入关系依据或文献来源（选填）"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">
          创建关系
        </el-button>
      </template>
    </el-dialog>

    <!-- 清除无效关系确认弹窗 -->
    <el-dialog
      v-model="cleanDialogVisible"
      title="清除无效关系"
      width="500px"
      :close-on-click-modal="false"
    >
      <div class="clean-content">
        <el-icon class="clean-icon" :size="48" color="#e6a23c">
          <WarningFilled />
        </el-icon>
        <p class="clean-description">
          系统将自动检测并删除所有指向已不存在实体的关系记录。
          此操作<strong>不可恢复</strong>，建议先导出备份。
        </p>
        <div v-if="invalidCount !== null" class="clean-result">
          <el-alert
            :title="invalidCount > 0 ? `检测到 ${invalidCount} 条无效关系` : '未检测到无效关系'"
            :type="invalidCount > 0 ? 'warning' : 'success'"
            :closable="false"
            show-icon
          />
        </div>
      </div>
      <template #footer>
        <el-button @click="cleanDialogVisible = false">取消</el-button>
        <el-button
          type="warning"
          :loading="cleanLoading"
          :disabled="invalidCount === 0"
          @click="confirmClean"
        >
          确认清除
        </el-button>
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
  Plus,
  Search,
  Refresh,
  Delete,
  WarningFilled
} from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { relationApi, entityApi } from '@/api'
import type { GraphRelation } from '@/types'

// ==================== 本地扩展类型 ====================
interface RelationRow extends GraphRelation {
  _id?: string
  source_type?: string
  target_type?: string
}

// ==================== 选项数据 ====================
const relationTypeOptions = ['包含', '主治', '提示', '对应', '具有', '禁忌', '来源于', '记载'] as const

const relationDescriptions: Record<string, string> = {
  '包含': '方剂→药材',
  '主治': '方剂/药材→症状',
  '提示': '症状→证候',
  '对应': '证候→方剂',
  '具有': '药材→功效',
  '禁忌': '药材/方剂→禁忌',
  '来源于': '方剂→文献',
  '记载': '文献→实体'
}

const entityTypeOptions = ['药材', '方剂', '症状', '证候']

// 类型标签颜色映射
const typeColorMap: Record<string, string> = {
  '药材': 'success',
  '方剂': 'primary',
  '症状': 'danger',
  '证候': 'warning',
  '功效': 'info',
  '禁忌': 'danger',
  '文献': ''
}

const getTypeTagColor = (type?: string): string => {
  return typeColorMap[type || ''] || 'info'
}

// 关系标签颜色映射
const relationColorMap: Record<string, string> = {
  '包含': 'primary',
  '主治': 'success',
  '提示': 'warning',
  '对应': 'info',
  '具有': 'success',
  '禁忌': 'danger',
  '来源于': '',
  '记载': 'info'
}

const getRelationTagColor = (r?: string): string => {
  return relationColorMap[r || ''] || ''
}

// ==================== 全部实体（供选择器使用） ====================
interface EntityOption {
  _key: string        // 组合键 "type:id"
  id: string
  name: string
  type: string
}

const allEntities = ref<EntityOption[]>([])
const entityLoading = ref(false)

const fetchAllEntities = async () => {
  entityLoading.value = true
  try {
    const fetchers: Array<Promise<{ type: string; data: any[] }>> = [
      entityApi.herbs.list({ pageSize: 9999 }).then((r: any) => ({
        type: '药材',
        data: resolveList(r)
      })),
      entityApi.prescriptions.list({ pageSize: 9999 }).then((r: any) => ({
        type: '方剂',
        data: resolveList(r)
      })),
      entityApi.symptoms.list({ pageSize: 9999 }).then((r: any) => ({
        type: '症状',
        data: resolveList(r)
      })),
      entityApi.syndromes.list({ pageSize: 9999 }).then((r: any) => ({
        type: '证候',
        data: resolveList(r)
      }))
    ]

    const results = await Promise.all(fetchers)
    const entities: EntityOption[] = []
    for (const { type, data } of results) {
      for (const item of data) {
        entities.push({
          _key: `${type}:${item.id}`,
          id: item.id,
          name: item.name,
          type
        })
      }
    }
    allEntities.value = entities
  } catch (error) {
    console.error('获取实体数据失败:', error)
  } finally {
    entityLoading.value = false
  }
}

const resolveList = (res: any): any[] => {
  if (res.code === 200) return res.data?.list ?? res.data?.records ?? []
  if (Array.isArray(res)) return res
  if (res.data && Array.isArray(res.data)) return res.data
  return []
}

// ==================== 表格数据 ====================
const tableRef = ref()
const loading = ref(false)
const tableData = ref<RelationRow[]>([])
const selectedRows = ref<RelationRow[]>([])

const searchParams = reactive({
  sourceName: '',
  targetName: '',
  relation: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const getRowKey = (row: RelationRow): string => {
  return row._id || `${row.source_id}_${row.relation}_${row.target_id}`
}

// 实体ID集合（用于检测无效关系）
const validEntityKeys = computed(() => new Set(allEntities.value.map((e) => `${e.type}:${e.id}`)))

// ==================== 数据获取 ====================
const fetchData = async () => {
  loading.value = true
  try {
    const res: any = await relationApi.list({
      page: pagination.page,
      pageSize: pagination.pageSize,
      sourceName: searchParams.sourceName || undefined,
      targetName: searchParams.targetName || undefined,
      relation: searchParams.relation || undefined
    })
    let list: RelationRow[] = []
    if (res.code === 200) {
      list = res.data?.list ?? res.data?.records ?? []
      pagination.total = res.data?.total ?? 0
    } else if (Array.isArray(res)) {
      list = res
      pagination.total = res.length
    } else if (res.data && Array.isArray(res.data)) {
      list = res.data
      pagination.total = res.total ?? res.data.length
    }
    // 推断实体类型并附加行列
    tableData.value = list.map((item: RelationRow) => ({
      ...item,
      _id: (item as any).id || `${item.source_id}_${item.relation}_${item.target_id}`,
      source_type: item.source_type || inferEntityType(item.source_id),
      target_type: item.target_type || inferEntityType(item.target_id)
    }))
  } catch (error) {
    console.error('获取关系列表失败:', error)
    ElMessage.error('获取关系列表失败')
  } finally {
    loading.value = false
  }
}

// 从ID前缀推断实体类型
const inferEntityType = (id: string): string => {
  if (!id) return ''
  const prefix = id.charAt(0).toUpperCase()
  const map: Record<string, string> = {
    'H': '药材',
    'F': '方剂',
    'S': '症状',
    'Z': '证候'
  }
  return map[prefix] || ''
}

// ==================== 搜索 ====================
const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchParams.sourceName = ''
  searchParams.targetName = ''
  searchParams.relation = ''
  handleSearch()
}

const handleSelectionChange = (rows: RelationRow[]) => {
  selectedRows.value = rows
}

// ==================== 新增关系弹窗 ====================
const dialogVisible = ref(false)
const submitLoading = ref(false)
const formRef = ref<FormInstance>()

const initFormData = () => ({
  source_type_filter: '',
  source_id: '',
  source_name: '',
  source_type: '',
  target_type_filter: '',
  target_id: '',
  target_name: '',
  target_type: '',
  relation: '' as string,
  evidence: ''
})

const formData = reactive(initFormData())

const formRules: FormRules = {
  source_id: [{ required: true, message: '请选择源实体', trigger: 'change' }],
  relation: [{ required: true, message: '请选择关系类型', trigger: 'change' }],
  target_id: [{ required: true, message: '请选择目标实体', trigger: 'change' }]
}

// 源实体过滤
const filteredSourceEntities = computed(() => {
  if (!formData.source_type_filter) return allEntities.value
  return allEntities.value.filter((e) => e.type === formData.source_type_filter)
})

// 目标实体过滤
const filteredTargetEntities = computed(() => {
  if (!formData.target_type_filter) return allEntities.value
  return allEntities.value.filter((e) => e.type === formData.target_type_filter)
})

const handleSourceTypeChange = () => {
  formData.source_id = ''
  formData.source_name = ''
  formData.source_type = ''
}

const handleTargetTypeChange = () => {
  formData.target_id = ''
  formData.target_name = ''
  formData.target_type = ''
}

const handleSourceSelect = (key: string) => {
  const entity = allEntities.value.find((e) => e._key === key)
  if (entity) {
    formData.source_name = entity.name
    formData.source_type = entity.type
  }
}

const handleTargetSelect = (key: string) => {
  const entity = allEntities.value.find((e) => e._key === key)
  if (entity) {
    formData.target_name = entity.name
    formData.target_type = entity.type
  }
}

const handleAdd = () => {
  dialogVisible.value = true
}

const resetForm = () => {
  Object.assign(formData, initFormData())
  formRef.value?.resetFields()
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return

    // 拆分 _key 获取 source_id
    const sourceId = formData.source_id.split(':').slice(1).join(':')
    const targetId = formData.target_id.split(':').slice(1).join(':')

    submitLoading.value = true
    try {
      const payload = {
        source_id: sourceId,
        source_name: formData.source_name,
        source_type: formData.source_type,
        relation: formData.relation,
        target_id: targetId,
        target_name: formData.target_name,
        target_type: formData.target_type,
        evidence: formData.evidence
      }

      await relationApi.create(payload as any)
      ElMessage.success('创建关系成功')
      dialogVisible.value = false
      fetchData()
    } catch (error) {
      console.error('创建关系失败:', error)
      ElMessage.error('创建关系失败，请重试')
    } finally {
      submitLoading.value = false
    }
  })
}

// ==================== 清除无效关系 ====================
const cleanDialogVisible = ref(false)
const cleanLoading = ref(false)
const invalidCount = ref<number | null>(null)

const handleCleanInvalid = async () => {
  invalidCount.value = null
  cleanDialogVisible.value = true

  // 确保实体数据已加载
  if (allEntities.value.length === 0) {
    await fetchAllEntities()
  }
  // 确保关系数据已加载
  if (tableData.value.length === 0) {
    await fetchData()
  }

  // 检测无效关系
  const keys = validEntityKeys.value
  const invalid = tableData.value.filter((row) => {
    const srcKey = `${row.source_type || inferEntityType(row.source_id)}:${row.source_id}`
    const tgtKey = `${row.target_type || inferEntityType(row.target_id)}:${row.target_id}`
    return !keys.has(srcKey) || !keys.has(tgtKey)
  })
  invalidCount.value = invalid.length
}

const confirmClean = async () => {
  if (invalidCount.value === 0) return

  cleanLoading.value = true
  try {
    const keys = validEntityKeys.value
    const invalidIds = tableData.value
      .filter((row) => {
        const srcKey = `${row.source_type || inferEntityType(row.source_id)}:${row.source_id}`
        const tgtKey = `${row.target_type || inferEntityType(row.target_id)}:${row.target_id}`
        return !keys.has(srcKey) || !keys.has(tgtKey)
      })
      .map((row) => row._id!)
      .filter(Boolean)

    if (invalidIds.length > 0) {
      await relationApi.batchDelete(invalidIds)
      ElMessage.success(`成功清除 ${invalidIds.length} 条无效关系`)
    } else {
      ElMessage.info('没有需要清除的无效关系')
    }

    cleanDialogVisible.value = false
    invalidCount.value = null
    fetchData()
  } catch (error) {
    console.error('清除无效关系失败:', error)
    ElMessage.error('清除失败，请重试')
  } finally {
    cleanLoading.value = false
  }
}

// ==================== 删除 ====================
const deleteDialogVisible = ref(false)
const deleteLoading = ref(false)
const isBatchDelete = ref(false)
const deleteTarget = ref<RelationRow | null>(null)

const deleteMessage = computed(() => {
  if (isBatchDelete.value) {
    return `确认删除选中的 ${selectedRows.value.length} 条关系记录？此操作不可恢复。`
  }
  if (deleteTarget.value) {
    return `确认删除关系「${deleteTarget.value.source_name} → ${deleteTarget.value.relation} → ${deleteTarget.value.target_name}」？此操作不可恢复。`
  }
  return '确认删除该关系？此操作不可恢复。'
})

const handleDelete = (row: RelationRow) => {
  isBatchDelete.value = false
  deleteTarget.value = row
  deleteDialogVisible.value = true
}

const handleBatchDelete = () => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要删除的关系')
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
      const ids = selectedRows.value.map((row) => row._id!).filter(Boolean)
      if (ids.length > 0) {
        await relationApi.batchDelete(ids)
      }
      ElMessage.success(`成功删除 ${ids.length} 条记录`)
    } else if (deleteTarget.value) {
      await relationApi.delete(deleteTarget.value._id!)
      ElMessage.success('删除成功')
    }
    deleteDialogVisible.value = false
    tableRef.value?.clearSelection()
    fetchData()
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
  fetchAllEntities()
})
</script>

<style scoped lang="scss">
.relation-manage {
  padding: 20px;
  max-width: 100%;
  overflow: hidden;

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

  .entity-cell {
    display: flex;
    align-items: center;
    gap: 8px;

    .entity-name {
      color: #303133;
      font-weight: 500;
    }
  }

  .pagination-wrapper {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }

  // 表格滚动容器
  .table-wrapper {
    width: 100%;
    max-width: 100%;
    overflow-x: auto;
    overflow-y: visible;

    // 让表格有最小宽度，触发横向滚动
    :deep(.el-table) {
      min-width: 1200px;
      width: 100%;

      .el-table__body-wrapper {
        overflow-x: auto;
      }
    }
  }

  // 实体选择器
  .entity-picker {
    display: flex;
    gap: 8px;
    width: 100%;
  }

  .selected-entity-preview {
    margin-top: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background-color: #f5f7fa;
    border-radius: 4px;
    font-size: 14px;
    color: #303133;
  }

  .entity-option {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
    padding-right: 4px;

    .entity-name {
      color: #303133;
      font-weight: 500;
    }
  }

  .relation-option {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;

    .relation-desc {
      font-size: 12px;
      color: #909399;
    }
  }

  // 清除无效关系
  .clean-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 16px 0;

    .clean-icon {
      margin-bottom: 16px;
    }

    .clean-description {
      font-size: 15px;
      color: #303133;
      text-align: center;
      line-height: 1.8;
      margin-bottom: 16px;
    }

    .clean-result {
      width: 100%;
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
