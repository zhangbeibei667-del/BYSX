<template>
  <div class="herb-manage">
    <!-- 顶部操作栏 -->
    <div class="page-header">
      <h2 class="page-title">
        <el-icon class="title-icon"><Orange /></el-icon>
        药材管理
      </h2>
      <div class="header-actions">
        <el-button v-permission="['admin']" class="btn-primary" :icon="Plus" @click="handleAdd">新建</el-button>
        <el-button v-permission="['admin']" class="btn-outline" :icon="Upload" @click="showImportDialog = true">批量导入</el-button>
        <el-button v-permission="['admin', 'user']" class="btn-outline" :icon="Download" @click="handleExportTemplate">导出模板</el-button>
      </div>
    </div>

    <!-- 搜索筛选栏 -->
    <div class="search-bar">
      <el-input
        v-model="searchParams.name"
        placeholder="请输入药材名称搜索..."
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
        style="width: 180px"
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

      <!-- 批量删除按钮 -->
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
        style="width: 100%;"
        @selection-change="handleSelectionChange"
        class="tcm-table"
      >
        <el-table-column type="selection" width="50" align="center" fixed="left" />
        <el-table-column type="index" label="序号" width="70" align="center" fixed="left" />
        <el-table-column prop="id" label="编号" width="100" align="center" />
        <el-table-column prop="name" label="名称" width="120" align="center" />
        <el-table-column label="性味" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.properties?.nature_and_flavor || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="归经" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.properties?.channel_tropism || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="功效" width="150" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.properties?.efficacy || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="主治" width="180" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.properties?.indications || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="用量" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.properties?.usage_dosage || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="禁忌" width="150" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.properties?.contraindications || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="120" align="center" />
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
      :title="isEdit ? '编辑药材' : '新建药材'"
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
              <el-input v-model="formData.name" placeholder="请输入药材名称" />
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

        <el-form-item label="性味" prop="nature_and_flavor">
          <el-input v-model="formData.nature_and_flavor" placeholder="如：甘，平" />
        </el-form-item>

        <el-form-item label="归经" prop="channel_tropism">
          <el-input v-model="formData.channel_tropism" placeholder="如：归心、肝经" />
        </el-form-item>

        <el-form-item label="功效" prop="efficacy">
          <el-input
            v-model="formData.efficacy"
            type="textarea"
            :rows="2"
            placeholder="请输入功效"
          />
        </el-form-item>

        <el-form-item label="主治" prop="indications">
          <el-input
            v-model="formData.indications"
            type="textarea"
            :rows="2"
            placeholder="请输入主治"
          />
        </el-form-item>

        <el-form-item label="用量" prop="usage_dosage">
          <el-input v-model="formData.usage_dosage" placeholder="如：煎服，3-10g" />
        </el-form-item>

        <el-form-item label="禁忌" prop="contraindications">
          <el-input
            v-model="formData.contraindications"
            type="textarea"
            :rows="2"
            placeholder="请输入禁忌"
          />
        </el-form-item>

        <el-form-item label="炮制方法" prop="processing_method">
          <el-input v-model="formData.processing_method" placeholder="请输入炮制方法（选填）" />
        </el-form-item>

        <el-form-item label="来源" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="2"
            placeholder="请输入药材来源描述（选填）"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button class="btn-cancel" @click="dialogVisible = false">取消</el-button>
        <el-button class="btn-primary" :loading="submitLoading" @click="handleSubmit">
          {{ isEdit ? '更新' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量导入弹窗 -->
    <ImportDialog
      v-model="showImportDialog"
      title="批量导入药材"
      entity-type="herb"
      :template-url="templateUrl"
      upload-url="/api/admin/herbs/import"
      @success="handleImportSuccess"
    />

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
  Orange
} from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { entityApi } from '@/api'
import type { HerbEntity } from '@/types'
import ImportDialog from '@/components/Common/ImportDialog.vue'

// ==================== 分类选项 ====================
const categoryOptions = [
  '补气药', '补血药', '补阴药', '补阳药',
  '清热药', '泻下药', '祛风湿药', '化湿药',
  '利水渗湿药', '温里药', '理气药', '消食药',
  '止血药', '活血化瘀药', '化痰止咳平喘药',
  '安神药', '平肝息风药', '开窍药', '收涩药',
  '涌吐药', '攻毒杀虫止痒药', '拔毒化腐生肌药'
]

// ==================== 表格数据 ====================
const tableRef = ref()
const loading = ref(false)
const tableData = ref<HerbEntity[]>([])
const selectedRows = ref<HerbEntity[]>([])

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

// ==================== 数据获取 ====================
const fetchData = async () => {
  loading.value = true
  try {
    const res: any = await entityApi.herbs.list({
      page: pagination.page,
      pageSize: pagination.pageSize,
      name: searchParams.name || undefined,
      category: searchParams.category || undefined
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
    console.error('获取药材列表失败:', error)
    ElMessage.error('获取药材列表失败')
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
  handleSearch()
}

const handleSelectionChange = (rows: HerbEntity[]) => {
  selectedRows.value = rows
}

// ==================== 导出模板 ====================
const templateUrl = '/api/admin/herbs/template'

const handleExportTemplate = async () => {
  try {
    const res: any = await entityApi.herbs.export()
    const blob = res instanceof Blob ? res : new Blob([res], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '药材导入模板.xlsx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('模板下载成功')
  } catch (error) {
    const link = document.createElement('a')
    link.href = '/api/admin/herbs/export'
    link.download = '药材导入模板.xlsx'
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
  nature_and_flavor: '',
  channel_tropism: '',
  efficacy: '',
  indications: '',
  usage_dosage: '',
  contraindications: '',
  processing_method: '',
  description: ''
})

const formData = reactive(initFormData())

const formRules: FormRules = {
  name: [{ required: true, message: '请输入药材名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
  nature_and_flavor: [{ required: true, message: '请输入性味', trigger: 'blur' }],
  channel_tropism: [{ required: true, message: '请输入归经', trigger: 'blur' }],
  efficacy: [{ required: true, message: '请输入功效', trigger: 'blur' }],
  indications: [{ required: true, message: '请输入主治', trigger: 'blur' }],
  usage_dosage: [{ required: true, message: '请输入用量', trigger: 'blur' }],
  contraindications: [{ required: true, message: '请输入禁忌', trigger: 'blur' }]
}

const handleAdd = () => {
  isEdit.value = false
  editId.value = ''
  dialogVisible.value = true
}

const handleEdit = (row: HerbEntity) => {
  isEdit.value = true
  editId.value = row.id
  formData.name = row.name
  formData.category = row.category
  formData.nature_and_flavor = row.properties?.nature_and_flavor || ''
  formData.channel_tropism = row.properties?.channel_tropism || ''
  formData.efficacy = row.properties?.efficacy || ''
  formData.indications = row.properties?.indications || ''
  formData.usage_dosage = row.properties?.usage_dosage || ''
  formData.contraindications = row.properties?.contraindications || ''
  formData.processing_method = row.properties?.processing_method || ''
  formData.description = row.description || ''
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
          nature_and_flavor: formData.nature_and_flavor,
          channel_tropism: formData.channel_tropism,
          efficacy: formData.efficacy,
          indications: formData.indications,
          usage_dosage: formData.usage_dosage,
          contraindications: formData.contraindications,
          processing_method: formData.processing_method
        },
        description: formData.description
      }

      if (isEdit.value) {
        await entityApi.herbs.update(editId.value, payload as any)
        ElMessage.success('编辑成功')
      } else {
        await entityApi.herbs.create(payload as any)
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
const deleteTarget = ref<HerbEntity | null>(null)

const deleteMessage = computed(() => {
  if (isBatchDelete.value) {
    return `确认删除选中的 ${selectedRows.value.length} 条药材记录？此操作不可恢复。`
  }
  return `确认删除药材「${deleteTarget.value?.name}」？此操作不可恢复。`
})

const handleDelete = (row: HerbEntity) => {
  isBatchDelete.value = false
  deleteTarget.value = row
  deleteDialogVisible.value = true
}

const handleBatchDelete = () => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要删除的药材')
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
      await entityApi.herbs.batchDelete(ids)
      ElMessage.success(`成功删除 ${ids.length} 条记录`)
    } else if (deleteTarget.value) {
      await entityApi.herbs.delete(deleteTarget.value.id)
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
onMounted(async () => {
  await fetchData()

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
// ==================== 国风色彩变量 ====================
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

.herb-manage {
  padding: 0;
  max-width: 100%;
  overflow: hidden;

  // ===== 页面标题栏 =====
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    .page-title {
      margin: 0;
      font-size: 22px;
      font-weight: 500;
      color: $text-dark;
      letter-spacing: 1px;
      display: flex;
      align-items: center;
      gap: 8px;

      .title-icon {
        color: $soft-gold;
        font-size: 22px;
      }
    }

    .header-actions {
      display: flex;
      gap: 10px;
    }
  }

  // ===== 搜索栏 =====
  .search-bar {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 18px;
    padding: 14px 20px;
    background: $cream-white;
    border-radius: 12px;
    border: 1px solid rgba(110, 135, 120, 0.2);
    flex-wrap: wrap;

    :deep(.el-input__wrapper) {
      border-radius: 8px;
      box-shadow: none !important;
      border: 1px solid rgba(110, 135, 120, 0.25);
      background: #fff;
      transition: border-color 0.2s;

      &:hover, &:focus-within {
        border-color: $mid-green;
      }
    }

    :deep(.el-input__prefix-inner .el-icon) {
      color: $mid-green;
    }

    :deep(.el-select .el-input__wrapper) {
      border: 1px solid rgba(110, 135, 120, 0.25);

      &:hover, &.is-focus {
        border-color: $mid-green;
      }
    }

    :deep(.el-select .el-input__prefix .el-icon) {
      color: $mid-green;
    }
  }

  // ===== 表格容器 =====
  .table-wrapper {
    width: 100%;
    overflow-x: auto;
    border-radius: 12px;
    border: 1px solid $border-light;
    background: $cream-white;
  }

  // ===== 国风表格样式 =====
  :deep(.tcm-table) {
    --el-table-border-color: $border-light;
    --el-table-header-bg-color: $cream-bg;
    --el-table-row-hover-bg-color: rgba(200, 168, 110, 0.06);
    
    .el-table__header-wrapper th {
      background-color: $cream-bg !important;
      color: $text-dark;
      font-weight: 500;
      font-size: 13px;
      letter-spacing: 0.5px;
    }
    
    .el-table__body-wrapper td {
      color: $text-light;
      font-size: 13px;
    }
    
    .el-table__row--striped {
      background-color: rgba(247, 243, 235, 0.3);
    }
  }

  // ===== 分页 =====
  .pagination-wrapper {
    margin-top: 18px;
    display: flex;
    justify-content: flex-end;
    
    :deep(.el-pagination) {
      .el-pagination__total {
        color: $text-light;
      }
      
      .el-pager li {
        border-radius: 4px;
        &:hover {
          color: $mid-green;
        }
        &.is-active {
          background: $gold-light;
          color: $mid-green;
          font-weight: 500;
        }
      }
      
      button:hover {
        color: $mid-green;
      }
    }
  }

  // ===== 国风按钮 =====
  .btn-primary {
    background: $mid-green;
    border-color: $mid-green;
    color: #fff;
    
    &:hover {
      background: lighten($mid-green, 8%);
      border-color: lighten($mid-green, 8%);
      color: #fff;
    }
  }
  
  .btn-outline {
    background: transparent;
    border-color: $border-light;
    color: $text-light;
    
    &:hover {
      border-color: $mid-green;
      color: $mid-green;
      background: rgba(70, 99, 80, 0.05);
    }
  }
  
  .btn-danger {
    background: $danger-red;
    border-color: $danger-red;
    color: #fff;
    
    &:hover {
      background: darken($danger-red, 8%);
      border-color: darken($danger-red, 8%);
      color: #fff;
    }
  }
  
  .btn-edit {
    color: $mid-green;
    
    &:hover {
      color: lighten($mid-green, 15%);
    }
  }
  
  .btn-delete {
    color: $danger-red;
    
    &:hover {
      color: darken($danger-red, 10%);
    }
  }
  
  .btn-cancel {
    color: $text-light;
    
    &:hover {
      color: $text-dark;
    }
  }

  // ===== 弹窗 =====
  :deep(.tcm-dialog) {
    .el-dialog {
      border-radius: 16px;
      box-shadow: 0 8px 40px rgba(42, 64, 48, 0.12);
    }
    
    .el-dialog__header {
      border-bottom: 1px solid $border-light;
      padding: 20px 24px 16px;
      
      .el-dialog__title {
        color: $text-dark;
        font-weight: 500;
        font-size: 18px;
      }
    }
    
    .el-dialog__body {
      padding: 24px;
    }
    
    .el-dialog__footer {
      border-top: 1px solid $border-light;
      padding: 16px 24px 20px;
    }
  }

  // ===== 删除确认弹窗 =====
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
      color: $text-dark;
      text-align: center;
      line-height: 1.6;
    }
  }
}
</style>
