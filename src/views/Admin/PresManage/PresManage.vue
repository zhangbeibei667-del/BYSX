<template>
  <div class="pres-manage">
    <!-- 顶部操作栏 -->
    <div class="page-header">
      <h2 class="page-title">方剂管理</h2>
      <div class="header-actions">
        <el-button type="primary" :icon="Plus" @click="handleAdd">新建</el-button>
        <el-button :icon="Upload" @click="showImportDialog = true">批量导入</el-button>
        <el-button :icon="Download" @click="handleExportTemplate">导出模板</el-button>
      </div>
    </div>

    <!-- 搜索筛选栏 -->
    <div class="search-bar">
      <el-input
        v-model="searchParams.name"
        placeholder="请输入方剂名称搜索..."
        clearable
        style="width: 220px"
        @keyup.enter="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-select
        v-model="searchParams.category"
        placeholder="功效分类"
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
      <el-select
        v-model="searchParams.source"
        placeholder="来源医籍"
        clearable
        style="width: 200px"
      >
        <el-option
          v-for="src in sourceOptions"
          :key="src"
          :label="src"
          :value="src"
        />
      </el-select>
      <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
      <el-button :icon="Refresh" @click="handleReset">重置</el-button>

      <!-- 批量删除按钮 -->
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
      <el-table-column prop="name" label="方剂名" width="140" align="center" />
      <el-table-column label="组成" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="composition-text">
            {{ row.properties?.composition || '-' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="功效" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.properties?.functions || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="主治" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.properties?.indications || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="禁忌" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.properties?.contraindications || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="category" label="分类" width="110" align="center" />
      <el-table-column label="来源" width="180" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.description || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" align="center" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="handleEdit(row)">
            <el-icon><Edit /></el-icon>
            编辑
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

    <!-- 新建/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑方剂' : '新建方剂'"
      width="750px"
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
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="方剂名" prop="name">
              <el-input v-model="formData.name" placeholder="请输入方剂名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="功效分类" prop="category">
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

        <el-form-item label="组成" prop="composition">
          <div class="composition-selector">
            <el-select
              v-model="formData.composition"
              multiple
              filterable
              placeholder="请选择组成药材（可搜索）"
              style="width: 100%"
              :loading="herbLoading"
              popper-class="composition-popper"
            >
              <el-option
                v-for="herb in herbOptions"
                :key="herb.id"
                :label="herb.name"
                :value="herb.name"
              >
                <div class="herb-option">
                  <span class="herb-name">{{ herb.name }}</span>
                  <span class="herb-category">{{ herb.category }}</span>
                </div>
              </el-option>
            </el-select>
            <div v-if="formData.composition.length > 0" class="selected-tags">
              <span class="tag-label">已选药材：</span>
              <el-tag
                v-for="(herb, index) in formData.composition"
                :key="index"
                closable
                size="small"
                @close="removeHerb(index)"
              >
                {{ herb }}
              </el-tag>
            </div>
          </div>
        </el-form-item>

        <el-form-item label="功效" prop="functions">
          <el-input
            v-model="formData.functions"
            type="textarea"
            :rows="2"
            placeholder="请输入方剂功效"
          />
        </el-form-item>

        <el-form-item label="主治" prop="indications">
          <el-input
            v-model="formData.indications"
            type="textarea"
            :rows="2"
            placeholder="请输入主治病症"
          />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="用法用量" prop="usage_dosage">
              <el-input v-model="formData.usage_dosage" placeholder="如：水煎服，每日一剂" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="来源" prop="source">
              <el-select
                v-model="formData.source"
                filterable
                allow-create
                placeholder="请选择或输入古籍来源"
                style="width: 100%"
              >
                <el-option
                  v-for="src in sourceOptions"
                  :key="src"
                  :label="src"
                  :value="src"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="禁忌" prop="contraindications">
          <el-input
            v-model="formData.contraindications"
            type="textarea"
            :rows="2"
            placeholder="请输入禁忌及注意事项"
          />
        </el-form-item>

        <el-form-item label="方解说明" prop="explanation">
          <el-input
            v-model="formData.explanation"
            type="textarea"
            :rows="3"
            placeholder="请输入方解说明，如配伍原理、加减变化等（选填）"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">
          {{ isEdit ? '更新' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量导入弹窗 -->
    <ImportDialog
      v-model="showImportDialog"
      title="批量导入方剂"
      entity-type="prescription"
      :template-url="templateUrl"
      upload-url="/api/admin/prescriptions/import"
      @success="handleImportSuccess"
    />

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
  Upload,
  Download,
  Search,
  Refresh,
  Delete,
  Edit,
  WarningFilled
} from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { entityApi } from '@/api'
import type { HerbEntity, PrescriptionEntity } from '@/types'
import ImportDialog from '@/components/Common/ImportDialog.vue'

// ==================== 选项数据 ====================
const categoryOptions = [
  '解表剂', '泻下剂', '和解剂', '清热剂', '祛暑剂',
  '温里剂', '补益剂', '固涩剂', '安神剂', '开窍剂',
  '理气剂', '理血剂', '治风剂', '治燥剂', '祛湿剂',
  '祛痰剂', '消食剂', '驱虫剂', '涌吐剂'
]

const sourceOptions = [
  '《伤寒论》', '《金匮要略》', '《温病条辨》', '《太平惠民和剂局方》',
  '《伤寒杂病论》', '《千金要方》', '《外台秘要》', '《景岳全书》',
  '《医林改错》', '《脾胃论》', '《丹溪心法》', '《医学衷中参西录》',
  '《温病条辨》', '《医宗金鉴》', '《肘后备急方》'
]

// ==================== 药材列表（供组成选择） ====================
const herbOptions = ref<HerbEntity[]>([])
const herbLoading = ref(false)

const fetchHerbs = async () => {
  herbLoading.value = true
  try {
    const res: any = await entityApi.herbs.list({ pageSize: 9999 })
    if (res.code === 200) {
      herbOptions.value = res.data?.list ?? res.data?.records ?? []
    } else if (Array.isArray(res)) {
      herbOptions.value = res
    } else if (res.data && Array.isArray(res.data)) {
      herbOptions.value = res.data
    }
  } catch (error) {
    console.error('获取药材列表失败:', error)
  } finally {
    herbLoading.value = false
  }
}

const removeHerb = (index: number) => {
  formData.composition.splice(index, 1)
}

// ==================== 表格数据 ====================
const tableRef = ref()
const loading = ref(false)
const tableData = ref<PrescriptionEntity[]>([])
const selectedRows = ref<PrescriptionEntity[]>([])

const searchParams = reactive({
  name: '',
  category: '',
  source: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// ==================== 数据获取 ====================
const fetchData = async () => {
  loading.value = true
  try {
    const res: any = await entityApi.prescriptions.list({
      page: pagination.page,
      pageSize: pagination.pageSize,
      name: searchParams.name || undefined,
      category: searchParams.category || undefined,
      source: searchParams.source || undefined
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
    console.error('获取方剂列表失败:', error)
    ElMessage.error('获取方剂列表失败')
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
  searchParams.name = ''
  searchParams.category = ''
  searchParams.source = ''
  handleSearch()
}

const handleSelectionChange = (rows: PrescriptionEntity[]) => {
  selectedRows.value = rows
}

// ==================== 导出模板 ====================
const templateUrl = '/api/admin/prescriptions/template'

const handleExportTemplate = async () => {
  try {
    const res: any = await entityApi.prescriptions.export()
    const blob = res instanceof Blob ? res : new Blob([res], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '方剂导入模板.xlsx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('模板下载成功')
  } catch (error) {
    const link = document.createElement('a')
    link.href = '/api/admin/prescriptions/export'
    link.download = '方剂导入模板.xlsx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }
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
  composition: [] as string[],
  functions: '',
  indications: '',
  usage_dosage: '',
  contraindications: '',
  source: '',
  explanation: ''
})

const formData = reactive(initFormData())

const formRules: FormRules = {
  name: [{ required: true, message: '请输入方剂名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择功效分类', trigger: 'change' }],
  composition: [{ required: true, message: '请选择组成药材', trigger: 'change' }],
  functions: [{ required: true, message: '请输入方剂功效', trigger: 'blur' }],
  indications: [{ required: true, message: '请输入主治病症', trigger: 'blur' }],
  usage_dosage: [{ required: true, message: '请输入用法用量', trigger: 'blur' }],
  contraindications: [{ required: true, message: '请输入禁忌及注意事项', trigger: 'blur' }],
  source: [{ required: true, message: '请选择或输入来源', trigger: 'blur' }]
}

const handleAdd = () => {
  isEdit.value = false
  editId.value = ''
  dialogVisible.value = true
}

const handleEdit = (row: PrescriptionEntity) => {
  isEdit.value = true
  editId.value = row.id
  formData.name = row.name
  formData.category = row.category
  // 将逗号分隔的组成字符串拆分为数组
  const comp = row.properties?.composition || ''
  formData.composition = comp ? comp.split(/[,，]/).map((s: string) => s.trim()).filter(Boolean) : []
  formData.functions = row.properties?.functions || ''
  formData.indications = row.properties?.indications || ''
  formData.usage_dosage = row.properties?.usage_dosage || ''
  formData.contraindications = row.properties?.contraindications || ''
  formData.source = row.description || ''
  formData.explanation = row.properties?.modern_application || ''
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
        properties: {
          composition: formData.composition.join('，'),
          preparation: '',
          functions: formData.functions,
          indications: formData.indications,
          usage_dosage: formData.usage_dosage,
          contraindications: formData.contraindications,
          modern_application: formData.explanation
        },
        description: formData.source
      }

      if (isEdit.value) {
        await entityApi.prescriptions.update(editId.value, payload as any)
        ElMessage.success('编辑成功')
      } else {
        await entityApi.prescriptions.create(payload as any)
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

// ==================== 删除 ====================
const deleteDialogVisible = ref(false)
const deleteLoading = ref(false)
const isBatchDelete = ref(false)
const deleteTarget = ref<PrescriptionEntity | null>(null)

const deleteMessage = computed(() => {
  if (isBatchDelete.value) {
    return `确认删除选中的 ${selectedRows.value.length} 条方剂记录？此操作不可恢复。`
  }
  return `确认删除方剂「${deleteTarget.value?.name}」？此操作不可恢复。`
})

const handleDelete = (row: PrescriptionEntity) => {
  isBatchDelete.value = false
  deleteTarget.value = row
  deleteDialogVisible.value = true
}

const handleBatchDelete = () => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要删除的方剂')
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
      await entityApi.prescriptions.batchDelete(ids)
      ElMessage.success(`成功删除 ${ids.length} 条记录`)
    } else if (deleteTarget.value) {
      await entityApi.prescriptions.delete(deleteTarget.value.id)
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

// ==================== 导入 ====================
const showImportDialog = ref(false)

const handleImportSuccess = () => {
  showImportDialog.value = false
  ElMessage.success('导入成功')
  fetchData()
}

// ==================== 初始化 ====================
onMounted(() => {
  fetchData()
  fetchHerbs()
})
</script>

<style scoped lang="scss">
.pres-manage {
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

  .composition-text {
    color: #303133;
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

  // 组成选择器
  .composition-selector {
    .selected-tags {
      margin-top: 8px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px;

      .tag-label {
        font-size: 13px;
        color: #909399;
        margin-right: 4px;
      }
    }
  }

  // 药材下拉选项
  .herb-option {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;

    .herb-name {
      color: #303133;
      font-weight: 500;
    }

    .herb-category {
      font-size: 12px;
      color: #909399;
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
