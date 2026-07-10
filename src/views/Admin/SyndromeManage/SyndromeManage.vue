<template>
  <div class="syndrome-manage">
    <!-- 顶部操作栏 -->
    <div class="page-header">
      <h2 class="page-title">证候管理</h2>
      <div class="header-actions">
        <el-button type="primary" :icon="Plus" @click="handleAdd">新建</el-button>
        <el-button :icon="Upload" @click="showImportDialog = true">批量导入</el-button>
        <el-button :icon="Download" @click="handleExport">导出数据</el-button>
      </div>
    </div>

    <!-- 搜索筛选栏 -->
    <div class="search-bar">
      <el-input
        v-model="searchParams.name"
        placeholder="请输入证候名称搜索..."
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
        style="width: 200px"
      >
        <el-option
          v-for="cat in categoryOptions"
          :key="cat"
          :label="cat"
          :value="cat"
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
      row-key="id"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="50" align="center" />
      <el-table-column type="index" label="序号" width="65" align="center" />
      <el-table-column prop="id" label="编号" width="100" align="center" />
      <el-table-column prop="name" label="证候名" width="140" align="center" />
      <el-table-column prop="category" label="分类" width="130" align="center">
        <template #default="{ row }">
          <el-tag size="small" type="warning">{{ row.category }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="核心症状" min-width="220">
        <template #default="{ row }">
          <div class="tag-list" v-if="getTagList(row.properties?.clinical_manifestations).length">
            <el-tag
              v-for="(tag, i) in getTagList(row.properties?.clinical_manifestations)"
              :key="i"
              size="small"
              type="danger"
              effect="light"
            >
              {{ tag }}
            </el-tag>
          </div>
          <span v-else class="text-placeholder">-</span>
        </template>
      </el-table-column>
      <el-table-column label="对应方剂" min-width="200">
        <template #default="{ row }">
          <div class="tag-list" v-if="getTagList(row.properties?.commonly_used_formulas).length">
            <el-tag
              v-for="(tag, i) in getTagList(row.properties?.commonly_used_formulas)"
              :key="i"
              size="small"
              type="success"
              effect="light"
            >
              {{ tag }}
            </el-tag>
          </div>
          <span v-else class="text-placeholder">-</span>
        </template>
      </el-table-column>
      <el-table-column label="病机" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.properties?.pathogenesis || '-' }}
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
      :title="isEdit ? '编辑证候' : '新建证候'"
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
            <el-form-item label="名称" prop="name">
              <el-input v-model="formData.name" placeholder="请输入证候名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="分类" prop="category">
              <el-select v-model="formData.category" placeholder="请选择证候分类" style="width: 100%">
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

        <el-form-item label="核心症状" prop="clinical_manifestations">
          <div class="relation-selector">
            <el-select
              v-model="formData.clinical_manifestations"
              multiple
              filterable
              placeholder="请选择核心症状（可搜索已有症状）"
              style="width: 100%"
            >
              <el-option
                v-for="sym in symptomOptions"
                :key="sym.id"
                :label="sym.name"
                :value="sym.name"
              >
                <div class="entity-option">
                  <span class="entity-name">{{ sym.name }}</span>
                  <span class="entity-category">{{ sym.category }}</span>
                </div>
              </el-option>
            </el-select>
            <div v-if="formData.clinical_manifestations.length > 0" class="selected-tags">
              <span class="tag-label">已选核心症状：</span>
              <el-tag
                v-for="(item, index) in formData.clinical_manifestations"
                :key="index"
                closable
                size="small"
                type="danger"
                effect="light"
                @close="removeTag(formData.clinical_manifestations, index)"
              >
                {{ item }}
              </el-tag>
            </div>
          </div>
        </el-form-item>

        <el-form-item label="对应方剂" prop="commonly_used_formulas">
          <div class="relation-selector">
            <el-select
              v-model="formData.commonly_used_formulas"
              multiple
              filterable
              placeholder="请选择对应方剂（可搜索已有方剂）"
              style="width: 100%"
            >
              <el-option
                v-for="pres in prescriptionOptions"
                :key="pres.id"
                :label="pres.name"
                :value="pres.name"
              >
                <div class="entity-option">
                  <span class="entity-name">{{ pres.name }}</span>
                  <span class="entity-category">{{ pres.category }}</span>
                </div>
              </el-option>
            </el-select>
            <div v-if="formData.commonly_used_formulas.length > 0" class="selected-tags">
              <span class="tag-label">已选对应方剂：</span>
              <el-tag
                v-for="(item, index) in formData.commonly_used_formulas"
                :key="index"
                closable
                size="small"
                type="success"
                effect="light"
                @close="removeTag(formData.commonly_used_formulas, index)"
              >
                {{ item }}
              </el-tag>
            </div>
          </div>
        </el-form-item>

        <el-form-item label="病机" prop="pathogenesis">
          <el-input
            v-model="formData.pathogenesis"
            type="textarea"
            :rows="2"
            placeholder="请输入病机分析（选填）"
          />
        </el-form-item>

        <el-form-item label="治则" prop="treatment_principle">
          <el-input
            v-model="formData.treatment_principle"
            type="textarea"
            :rows="2"
            placeholder="请输入治则治法（选填）"
          />
        </el-form-item>

        <el-form-item label="证候解析" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入证候解析说明（选填）"
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

    <!-- 批量导入弹窗 -->
    <ImportDialog
      v-model="showImportDialog"
      title="批量导入证候"
      entity-type="syndrome"
      template-url="/api/admin/syndromes/template"
      upload-url="/api/admin/syndromes/import"
      @success="handleImportSuccess"
    />
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
import type { SyndromeEntity, SymptomEntity, PrescriptionEntity } from '@/types'
import ImportDialog from '@/components/Common/ImportDialog.vue'

// ==================== 选项数据 ====================
const categoryOptions = [
  '脏腑辨证', '气血津液辨证', '八纲辨证', '六经辨证',
  '卫气营血辨证', '三焦辨证', '经络辨证', '病因辨证'
]

// ==================== 已有实体数据（供多选） ====================
const symptomOptions = ref<SymptomEntity[]>([])
const prescriptionOptions = ref<PrescriptionEntity[]>([])

const fetchReferenceData = async () => {
  try {
    const [symRes, presRes]: any[] = await Promise.all([
      entityApi.symptoms.list({ pageSize: 9999 }),
      entityApi.prescriptions.list({ pageSize: 9999 })
    ])

    if (symRes.code === 200) {
      symptomOptions.value = symRes.data?.list ?? symRes.data?.records ?? []
    } else if (Array.isArray(symRes)) {
      symptomOptions.value = symRes
    } else if (symRes.data && Array.isArray(symRes.data)) {
      symptomOptions.value = symRes.data
    }

    if (presRes.code === 200) {
      prescriptionOptions.value = presRes.data?.list ?? presRes.data?.records ?? []
    } else if (Array.isArray(presRes)) {
      prescriptionOptions.value = presRes
    } else if (presRes.data && Array.isArray(presRes.data)) {
      prescriptionOptions.value = presRes.data
    }
  } catch (error) {
    console.error('获取参考数据失败:', error)
  }
}

const removeTag = (arr: string[], index: number) => {
  arr.splice(index, 1)
}

// ==================== 标签解析工具 ====================
const getTagList = (str?: string): string[] => {
  if (!str) return []
  return str.split(/[,，]/).map((s: string) => s.trim()).filter(Boolean)
}

// ==================== 表格数据 ====================
const tableRef = ref()
const loading = ref(false)
const tableData = ref<SyndromeEntity[]>([])
const selectedRows = ref<SyndromeEntity[]>([])

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
    const res: any = await entityApi.syndromes.list({
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
    console.error('获取证候列表失败:', error)
    ElMessage.error('获取证候列表失败')
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

const handleSelectionChange = (rows: SyndromeEntity[]) => {
  selectedRows.value = rows
}

// ==================== 导出 ====================
const handleExport = async () => {
  try {
    const res: any = await entityApi.syndromes.export()
    const blob = res instanceof Blob ? res : new Blob([res], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '证候数据导出.xlsx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch {
    const link = document.createElement('a')
    link.href = '/api/admin/syndromes/export'
    link.download = '证候数据导出.xlsx'
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
  fetchReferenceData()
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
  clinical_manifestations: [] as string[],
  commonly_used_formulas: [] as string[],
  pathogenesis: '',
  treatment_principle: '',
  description: ''
})

const formData = reactive(initFormData())

const formRules: FormRules = {
  name: [{ required: true, message: '请输入证候名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择证候分类', trigger: 'change' }],
  clinical_manifestations: [{ required: true, message: '请选择核心症状', trigger: 'change' }]
}

const handleAdd = () => {
  isEdit.value = false
  editId.value = ''
  dialogVisible.value = true
}

const handleEdit = (row: SyndromeEntity) => {
  isEdit.value = true
  editId.value = row.id
  formData.name = row.name
  formData.category = row.category
  formData.clinical_manifestations = getTagList(row.properties?.clinical_manifestations)
  formData.commonly_used_formulas = getTagList(row.properties?.commonly_used_formulas)
  formData.pathogenesis = row.properties?.pathogenesis || ''
  formData.treatment_principle = row.properties?.treatment_principle || ''
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
        description: formData.description,
        properties: {
          clinical_manifestations: formData.clinical_manifestations.join('，'),
          commonly_used_formulas: formData.commonly_used_formulas.join('，'),
          pathogenesis: formData.pathogenesis,
          treatment_principle: formData.treatment_principle
        }
      }

      if (isEdit.value) {
        await entityApi.syndromes.update(editId.value, payload as any)
        ElMessage.success('编辑成功')
      } else {
        await entityApi.syndromes.create(payload as any)
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
const deleteTarget = ref<SyndromeEntity | null>(null)

const deleteMessage = computed(() => {
  if (isBatchDelete.value) {
    return `确认删除选中的 ${selectedRows.value.length} 条证候记录？此操作不可恢复。`
  }
  return `确认删除证候「${deleteTarget.value?.name}」？此操作不可恢复。`
})

const handleDelete = (row: SyndromeEntity) => {
  isBatchDelete.value = false
  deleteTarget.value = row
  deleteDialogVisible.value = true
}

const handleBatchDelete = () => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要删除的证候')
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
      await entityApi.syndromes.batchDelete(ids)
      ElMessage.success(`成功删除 ${ids.length} 条记录`)
    } else if (deleteTarget.value) {
      await entityApi.syndromes.delete(deleteTarget.value.id)
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
  fetchReferenceData()
})
</script>

<style scoped lang="scss">
.syndrome-manage {
  // ===== 这行控制页面整体的上下左右边距 =====
  padding: 20px;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    // ===== 顶部标题栏与下方搜索栏的间距（下边距）=====
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
    // ===== 搜索栏与下方表格的间距（下边距）=====
    margin-bottom: 16px;
    // ===== 搜索栏内部内边距（上下左右）=====
    padding: 16px;
    background-color: #f5f7fa;
    border-radius: 6px;
    flex-wrap: wrap;
  }

  .tag-list {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    padding: 2px 0;
  }

  .text-placeholder {
    color: #c0c4cc;
  }

  .pagination-wrapper {
    // ===== 表格与分页组件的间距（上边距）=====
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }

  .table-wrapper {
    width: 100%;
    overflow-x: auto;
  }

  .relation-selector {
    .selected-tags {
      // ===== 选择器与下方标签列表的间距（上边距）=====
      margin-top: 8px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px;

      .tag-label {
        font-size: 13px;
        color: #909399;
        // ===== 标签文字右侧间距 =====
        margin-right: 4px;
      }
    }
  }

  .entity-option {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;

    .entity-name {
      color: #303133;
      font-weight: 500;
    }

    .entity-category {
      font-size: 12px;
      color: #909399;
    }
  }

  .delete-confirm-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    // ===== 删除确认弹窗内容的内边距（上下）=====
    padding: 16px 0;

    .delete-icon {
      // ===== 警告图标与下方文字间距（下边距）=====
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
