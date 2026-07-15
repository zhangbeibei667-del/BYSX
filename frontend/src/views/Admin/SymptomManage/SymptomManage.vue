<template>
  <div class="symptom-manage">
    <!-- 顶部操作栏 -->
    <div class="page-header">
      <h2 class="page-title">
        <el-icon class="title-icon"><Warning /></el-icon>
        症状管理
      </h2>
      <div class="header-actions">
        <el-button v-permission="['admin']" class="btn-primary" :icon="Plus" @click="handleAdd">新建</el-button>
        <el-button v-permission="['admin']" class="btn-outline" :icon="Upload" @click="showImportDialog = true">批量导入</el-button>
        <el-button v-permission="['admin', 'user']" class="btn-outline" :icon="Download" @click="handleExport">导出数据</el-button>
      </div>
    </div>

    <!-- 搜索筛选栏 -->
    <div class="search-bar">
      <el-input
        v-model="searchParams.name"
        placeholder="请输入症状名称搜索..."
        clearable
        style="width: 240px"
        @keyup.enter="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-select
        v-model="searchParams.category"
        placeholder="请选择分类"
        clearable
        style="width: 160px"
      >
        <el-option
          v-for="cat in categoryOptions"
          :key="cat"
          :label="cat"
          :value="cat"
        />
      </el-select>
      <el-button class="btn-primary" :icon="Search" @click="handleSearch">搜索</el-button>
      <el-button class="btn-outline" :icon="Refresh" @click="handleReset">重置</el-button>

      <el-button
        v-if="selectedRows.length > 0"
        v-permission="['admin']"
        class="btn-danger"
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
        class="tcm-table"
      >
        <el-table-column type="selection" width="50" align="center" />
        <el-table-column type="index" label="序号" width="65" align="center" />
        <el-table-column prop="id" label="编号" width="100" align="center" />
        <el-table-column prop="name" label="症状名" width="130" align="center" />
        <el-table-column prop="category" label="分类" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="danger">{{ row.category }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="描述" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.description || row.properties?.nature || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="部位" width="100" align="center">
          <template #default="{ row }">
            {{ row.properties?.body_part || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="辨证要点" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.properties?.differentiation || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="关联证候" width="120" align="center">
          <template #default="{ row }">
            <el-badge
              :value="getSyndromeCount(row.id)"
              class="syndrome-badge"
              :hidden="!getSyndromeCount(row.id)"
            >
              <el-button
                class="btn-edit"
                link
                size="small"
                @click="showRelatedSyndromes(row)"
              >
                <el-icon><Connection /></el-icon>
                {{ getSyndromeCount(row.id) ? '查看' : '无' }}
              </el-button>
            </el-badge>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" align="center" fixed="right">
          <template #default="{ row }">
            <el-button v-permission="['admin']" class="btn-edit" link size="small" @click="handleEdit(row)">
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-button v-permission="['admin']" class="btn-delete" link size="small" @click="handleDelete(row)">
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

    <!-- 新建/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑症状' : '新建症状'"
      width="700px"
      :close-on-click-modal="false"
      @closed="resetForm"
      class="tcm-dialog"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="80px"
        label-position="right"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="名称" prop="name">
              <el-input v-model="formData.name" placeholder="请输入症状名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="分类" prop="category">
              <el-select v-model="formData.category" placeholder="请选择分类" style="width: 100%">
                <el-option
                  v-for="cat in categoryOptions"
                  :key="cat"
                  :label="cat"
                  :value="cat"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="部位" prop="body_part">
              <el-input v-model="formData.body_part" placeholder="如：头部、腹部（选填）" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="性质" prop="nature">
              <el-select
                v-model="formData.nature"
                filterable
                allow-create
                placeholder="请选择或输入症状性质"
                style="width: 100%"
              >
                <el-option
                  v-for="n in natureOptions"
                  :key="n"
                  :label="n"
                  :value="n"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="描述" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="2"
            placeholder="请输入症状描述"
          />
        </el-form-item>

        <el-form-item label="辨证要点" prop="differentiation">
          <el-input
            v-model="formData.differentiation"
            type="textarea"
            :rows="2"
            placeholder="请输入辨证要点（选填）"
          />
        </el-form-item>

        <el-form-item label="常见伴随症状" prop="associated_symptoms">
          <div class="associated-selector">
            <el-select
              v-model="formData.associated_symptoms"
              multiple
              filterable
              placeholder="请选择常见伴随症状（可搜索）"
              style="width: 100%"
            >
              <el-option
                v-for="sym in allSymptoms"
                :key="sym.id"
                :label="sym.name"
                :value="sym.name"
              >
                <div class="symptom-option">
                  <span class="sym-name">{{ sym.name }}</span>
                  <span class="sym-category">{{ sym.category }}</span>
                </div>
              </el-option>
            </el-select>
            <div v-if="formData.associated_symptoms.length > 0" class="selected-tags">
              <span class="tag-label">已选：</span>
              <el-tag
                v-for="(sym, index) in formData.associated_symptoms"
                :key="index"
                closable
                size="small"
                @close="removeSymptom(index)"
              >
                {{ sym }}
              </el-tag>
            </div>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button class="btn-cancel" @click="dialogVisible = false">取消</el-button>
        <el-button class="btn-primary" :loading="submitLoading" @click="handleSubmit">
          {{ isEdit ? '更新' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 关联证候弹窗 -->
    <el-dialog
      v-model="syndromeDialogVisible"
      :title="`「${currentSymptom?.name}」关联的证候`"
      width="600px"
      :close-on-click-modal="false"
      class="tcm-dialog"
    >
      <div v-if="syndromeLoading" class="loading-content">
        <el-icon class="loading-icon" :size="32"><Loading /></el-icon>
        <p>正在加载关联证候...</p>
      </div>
      <div v-else-if="relatedSyndromes.length === 0" class="empty-content">
        <el-empty description="暂无关联证候数据" />
      </div>
      <div v-else class="syndrome-list">
        <el-table :data="relatedSyndromes" border stripe size="small" class="tcm-table">
          <el-table-column prop="id" label="编号" width="90" align="center" />
          <el-table-column prop="name" label="证候名称" width="140" align="center" />
          <el-table-column prop="category" label="分类" width="100" align="center" />
          <el-table-column label="病机" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.properties?.pathogenesis || '-' }}
            </template>
          </el-table-column>
        </el-table>
      </div>
      <template #footer>
        <el-button class="btn-cancel" @click="syndromeDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 删除确认弹窗 -->
    <el-dialog
      v-model="deleteDialogVisible"
      title="确认删除"
      width="420px"
      :close-on-click-modal="false"
      class="tcm-dialog"
    >
      <div class="delete-confirm-content">
        <el-icon class="delete-icon" :size="48" color="#b35c5c">
          <WarningFilled />
        </el-icon>
        <p class="delete-message">{{ deleteMessage }}</p>
      </div>
      <template #footer>
        <el-button class="btn-cancel" @click="deleteDialogVisible = false">取消</el-button>
        <el-button class="btn-danger" :loading="deleteLoading" @click="confirmDelete">
          确认删除
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量导入弹窗 -->
    <ImportDialog
      v-model="showImportDialog"
      title="批量导入症状"
      entity-type="symptom"
      template-url="/api/admin/symptoms/template"
      upload-url="/api/admin/symptoms/import"
      @success="handleImportSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Plus,
  Upload,
  Download,
  Search,
  Refresh,
  Delete,
  Edit,
  WarningFilled,
  Warning,
  Connection,
  Loading
} from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { entityApi, graphApi } from '@/api'
import type { SymptomEntity, SyndromeEntity } from '@/types'
import ImportDialog from '@/components/Common/ImportDialog.vue'

// ==================== 选项数据 ====================
const categoryOptions = [
  '寒热', '疼痛', '心神', '头面', '五官',
  '胸腹', '腰背', '四肢', '二便', '饮食',
  '睡眠', '汗出', '妇人', '小儿', '舌脉',
  '气血', '痰饮', '外感', '内伤'
]

const natureOptions = [
  '胀痛', '刺痛', '隐痛', '灼痛', '冷痛',
  '绞痛', '重痛', '窜痛', '掣痛', '酸痛',
  '热', '寒', '虚', '实', '浮', '沉',
  '迟', '数', '滑', '涩', '弦', '细',
  '红', '淡', '紫', '暗'
]

// ==================== 全部症状 ====================
const allSymptoms = ref<SymptomEntity[]>([])

const fetchAllSymptoms = async () => {
  try {
    const res: any = await entityApi.symptoms.list({ pageSize: 9999 })
    if (res.code === 200) {
      allSymptoms.value = res.data?.list ?? res.data?.records ?? []
    } else if (Array.isArray(res)) {
      allSymptoms.value = res
    } else if (res.data && Array.isArray(res.data)) {
      allSymptoms.value = res.data
    }
  } catch (error) {
    console.error('获取症状列表失败:', error)
  }
}

const removeSymptom = (index: number) => {
  formData.associated_symptoms.splice(index, 1)
}

// ==================== 表格数据 ====================
const tableRef = ref()
const loading = ref(false)
const tableData = ref<SymptomEntity[]>([])
const selectedRows = ref<SymptomEntity[]>([])

const route = useRoute()
const router = useRouter()

const searchParams = reactive({
  name: '',
  category: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const syndromeCountMap = ref<Record<string, number>>({})

const getSyndromeCount = (id: string): number => {
  return syndromeCountMap.value[id] ?? 0
}

// ==================== 数据获取 ====================
const fetchData = async () => {
  loading.value = true
  try {
    const res: any = await entityApi.symptoms.list({
      page: pagination.page,
      pageSize: pagination.pageSize,
      name: searchParams.name || undefined,
      category: searchParams.category || undefined
    })
    let list: SymptomEntity[] = []
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
    tableData.value = list
    fetchSyndromeCounts(list)
  } catch (error) {
    console.error('获取症状列表失败:', error)
    ElMessage.error('获取症状列表失败')
  } finally {
    loading.value = false
  }
}

const fetchSyndromeCounts = async (list: SymptomEntity[]) => {
  for (const item of list) {
    try {
      const res: any = await graphApi.getRelatedEntities(item.id, 1)
      const nodes = res?.nodes ?? res?.data?.nodes ?? []
      const count = nodes.filter((n: any) => n.type === '证候').length
      syndromeCountMap.value[item.id] = count
    } catch {
      syndromeCountMap.value[item.id] = 0
    }
  }
}

// ==================== 搜索 ====================
const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchParams.name = ''
  searchParams.category = ''
  handleSearch()
}

const handleSelectionChange = (rows: SymptomEntity[]) => {
  selectedRows.value = rows
}

// ==================== 导出 ====================
const handleExport = async () => {
  try {
    const res: any = await entityApi.symptoms.export()
    const blob = res instanceof Blob ? res : new Blob([res], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '症状数据导出.xlsx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch {
    const link = document.createElement('a')
    link.href = '/api/admin/symptoms/export'
    link.download = '症状数据导出.xlsx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }
}

// ==================== 导入 ====================
const showImportDialog = ref(false)

const handleImportSuccess = () => {
  showImportDialog.value = false
  ElMessage.success('导入成功')
  fetchData()
  fetchAllSymptoms()
}

// ==================== 新建/编辑弹窗 ====================
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref('')
const submitLoading = ref(false)
const formRef = ref<FormInstance>()

const initFormData = () => ({
  name: '',
  category: '',
  body_part: '',
  nature: '',
  description: '',
  differentiation: '',
  associated_symptoms: [] as string[]
})

const formData = reactive(initFormData())

const formRules: FormRules = {
  name: [{ required: true, message: '请输入症状名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'change' }]
}

const handleAdd = () => {
  isEdit.value = false
  editId.value = ''
  dialogVisible.value = true
}

const handleEdit = (row: SymptomEntity) => {
  isEdit.value = true
  editId.value = row.id
  formData.name = row.name
  formData.category = row.category
  formData.body_part = row.properties?.body_part || ''
  formData.nature = row.properties?.nature || ''
  formData.description = row.description || ''
  formData.differentiation = row.properties?.differentiation || ''
  const assoc = row.properties?.associated_symptoms || ''
  formData.associated_symptoms = assoc ? assoc.split(/[,，]/).map((s: string) => s.trim()).filter(Boolean) : []
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

    submitLoading.value = true
    try {
      const payload = {
        name: formData.name,
        category: formData.category,
        description: formData.description,
        properties: {
          body_part: formData.body_part,
          nature: formData.nature,
          differentiation: formData.differentiation,
          associated_symptoms: formData.associated_symptoms.join('，')
        }
      }

      if (isEdit.value) {
        await entityApi.symptoms.update(editId.value, payload as any)
        ElMessage.success('编辑成功')
      } else {
        await entityApi.symptoms.create(payload as any)
        ElMessage.success('创建成功')
      }

      dialogVisible.value = false
      fetchData()
    } catch (error) {
      console.error('提交失败:', error)
      ElMessage.error('操作失败，请重试')
    } finally {
      submitLoading.value = false
    }
  })
}

// ==================== 关联证候弹窗 ====================
const syndromeDialogVisible = ref(false)
const syndromeLoading = ref(false)
const currentSymptom = ref<SymptomEntity | null>(null)
const relatedSyndromes = ref<SyndromeEntity[]>([])

const showRelatedSyndromes = async (row: SymptomEntity) => {
  currentSymptom.value = row
  syndromeDialogVisible.value = true
  syndromeLoading.value = true
  relatedSyndromes.value = []

  try {
    const res: any = await graphApi.getRelatedEntities(row.id, 1)
    const nodes: any[] = res?.nodes ?? res?.data?.nodes ?? []
    relatedSyndromes.value = nodes.filter((n: any) => n.type === '证候')
  } catch (error) {
    console.error('获取关联证候失败:', error)
    ElMessage.error('获取关联证候失败')
  } finally {
    syndromeLoading.value = false
  }
}

// ==================== 删除 ====================
const deleteDialogVisible = ref(false)
const deleteLoading = ref(false)
const isBatchDelete = ref(false)
const deleteTarget = ref<SymptomEntity | null>(null)

const deleteMessage = computed(() => {
  if (isBatchDelete.value) {
    return `确认删除选中的 ${selectedRows.value.length} 条症状记录？此操作不可恢复。`
  }
  return `确认删除症状「${deleteTarget.value?.name}」？此操作不可恢复。`
})

const handleDelete = (row: SymptomEntity) => {
  isBatchDelete.value = false
  deleteTarget.value = row
  deleteDialogVisible.value = true
}

const handleBatchDelete = () => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要删除的症状')
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
      await entityApi.symptoms.batchDelete(ids)
      ElMessage.success(`成功删除 ${ids.length} 条记录`)
    } else if (deleteTarget.value) {
      await entityApi.symptoms.delete(deleteTarget.value.id)
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
onMounted(async () => {
  await fetchData()
  fetchAllSymptoms()

  const editId = route.query.editId as string
  if (editId) {
    await nextTick()
    const entity = tableData.value.find((item: any) => item.id === editId)
    if (entity) {
      handleEdit(entity)
      router.replace({ query: {} })
    }
  }
})
</script>

<style scoped lang="scss">
$dark-green: #2a4030;
$mid-green: #466350;
$soft-gold: #c8a86e;
$gold-light: rgba(200, 168, 110, 0.15);
$cream-bg: #f7f3eb;
$cream-white: #faf6ef;
$text-dark: #2c3630;
$text-light: #6b7a72;
$border-light: rgba(110, 135, 120, 0.12);
$danger-red: #b35c5c;

.symptom-manage {
  padding: 0;
  max-width: 100%;
  overflow: hidden;

  .page-header {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;
    .page-title { margin: 0; font-size: 22px; font-weight: 500; color: $text-dark; letter-spacing: 1px; display: flex; align-items: center; gap: 8px;
      .title-icon { color: $soft-gold; font-size: 22px; }
    }
    .header-actions { display: flex; gap: 10px; }
  }

  .search-bar {
    display: flex; gap: 12px; align-items: center; margin-bottom: 18px;
    padding: 16px 20px; background: $cream-white; border-radius: 12px; border: 1px solid $border-light; flex-wrap: wrap;
  }

  .syndrome-badge :deep(.el-badge__content) { margin-top: -2px; }

  .pagination-wrapper {
    margin-top: 18px; display: flex; justify-content: flex-end;
    :deep(.el-pagination) {
      .el-pagination__total { color: $text-light; }
      .el-pager li { border-radius: 4px; &:hover { color: $mid-green; } &.is-active { background: $gold-light; color: $mid-green; font-weight: 500; } }
      button:hover { color: $mid-green; }
    }
  }

  .table-wrapper {
    width: 100%; overflow-x: auto; border-radius: 12px; border: 1px solid $border-light; background: $cream-white;
  }

  :deep(.tcm-table) {
    --el-table-border-color: $border-light;
    --el-table-header-bg-color: $cream-bg;
    --el-table-row-hover-bg-color: rgba(200, 168, 110, 0.06);
    .el-table__header-wrapper th { background-color: $cream-bg !important; color: $text-dark; font-weight: 500; font-size: 13px; letter-spacing: 0.5px; }
    .el-table__body-wrapper td { color: $text-light; font-size: 13px; }
    .el-table__row--striped { background-color: rgba(247, 243, 235, 0.3); }
  }

  .btn-primary { background: $mid-green; border-color: $mid-green; color: #fff; &:hover { background: lighten($mid-green, 8%); border-color: lighten($mid-green, 8%); color: #fff; } }
  .btn-outline { background: transparent; border-color: $border-light; color: $text-light; &:hover { border-color: $mid-green; color: $mid-green; background: rgba(70, 99, 80, 0.05); } }
  .btn-danger { background: $danger-red; border-color: $danger-red; color: #fff; &:hover { background: darken($danger-red, 8%); border-color: darken($danger-red, 8%); color: #fff; } }
  .btn-edit { color: $mid-green; &:hover { color: lighten($mid-green, 15%); } }
  .btn-delete { color: $danger-red; &:hover { color: darken($danger-red, 10%); } }
  .btn-cancel { color: $text-light; &:hover { color: $text-dark; } }

  :deep(.tcm-dialog) {
    .el-dialog { border-radius: 16px; box-shadow: 0 8px 40px rgba(42, 64, 48, 0.12); }
    .el-dialog__header { border-bottom: 1px solid $border-light; padding: 20px 24px 16px; .el-dialog__title { color: $text-dark; font-weight: 500; font-size: 18px; } }
    .el-dialog__body { padding: 24px; }
    .el-dialog__footer { border-top: 1px solid $border-light; padding: 16px 24px 20px; }
  }

  .associated-selector .selected-tags {
    margin-top: 8px; display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
    .tag-label { font-size: 13px; color: $text-light; margin-right: 4px; }
  }

  .symptom-option {
    display: flex; justify-content: space-between; align-items: center; width: 100%;
    .sym-name { color: $text-dark; font-weight: 500; }
    .sym-category { font-size: 12px; color: $text-light; }
  }

  .loading-content { display: flex; flex-direction: column; align-items: center; padding: 32px 0;
    .loading-icon { color: $mid-green; animation: spin 2s linear infinite; margin-bottom: 12px; }
    p { color: $text-light; }
  }
  @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
  .empty-content { padding: 20px 0; }

  .delete-confirm-content {
    display: flex; flex-direction: column; align-items: center; padding: 16px 0;
    .delete-icon { margin-bottom: 16px; }
    .delete-message { font-size: 15px; color: $text-dark; text-align: center; line-height: 1.6; }
  }
}
</style>
