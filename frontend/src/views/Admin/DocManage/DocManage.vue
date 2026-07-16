<template>
  <div class="doc-manage">
    <!-- 顶部操作栏 -->
    <div class="page-header">
      <h2 class="page-title">
        <el-icon class="title-icon"><Files /></el-icon>
        文献资料管理
      </h2>
      <div class="header-actions">
        <el-button v-permission="['admin']" class="btn-primary" :icon="Plus" @click="handleAdd">上传文献</el-button>
        <el-button v-permission="['admin', 'user']" class="btn-outline" :icon="Download" @click="handleExport">导出数据</el-button>
      </div>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <el-input
        v-model="searchParams.keyword"
        placeholder="搜索标题/内容关键词..."
        clearable
        style="width: 260px"
        @keyup.enter="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-select
        v-model="searchParams.type"
        placeholder="文献类型"
        clearable
        style="width: 130px"
      >
        <el-option v-for="t in docTypeOptions" :key="t" :label="t" :value="t" />
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
        <el-table-column label="文献标题" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <el-button class="btn-edit" link @click="handleView(row)">
              {{ row.name }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="来源类型" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="getDocTypeColor(row.type)" size="small">{{ getDocTypeLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="原文片段" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tooltip
              v-if="row.original_text"
              :content="row.original_text"
              placement="top"
              :show-after="300"
              effect="light"
              popper-class="doc-text-tooltip"
            >
              <span class="text-preview">{{ truncateText(row.original_text, 30) }}</span>
            </el-tooltip>
            <span v-else class="text-placeholder">-</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getDocTypeColor(row.type)" size="small">{{ row.type || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="160" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.source || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="170" align="center">
          <template #default="{ row }">
            {{ formatDate(row.createdAt) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-button class="btn-edit" link size="small" @click="handleView(row)">
              <el-icon><View /></el-icon>
              查看
            </el-button>
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

    <!-- 上传/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑文献' : '上传文献'"
      width="800px"
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
          <el-col :span="14">
            <el-form-item label="文献标题" prop="name">
              <el-input v-model="formData.name" placeholder="请输入文献标题" />
            </el-form-item>
          </el-col>
          <el-col :span="10">
            <el-form-item label="文献类型" prop="type">
              <el-select v-model="formData.type" placeholder="请选择类型" style="width: 100%">
                <el-option v-for="t in docTypeOptions" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="14">
            <el-form-item label="来源详情">
              <el-input v-model="formData.source_detail" placeholder="如：《中国药典》2020版 第一卷" />
            </el-form-item>
          </el-col>
          <el-col :span="10">
            <el-form-item label="页码/章节">
              <el-input v-model="formData.chapter" placeholder="如：P123 或 第五章" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="原文片段">
          <el-input
            v-model="formData.original_text"
            type="textarea"
            :rows="4"
            placeholder="请直接引用原文内容，用于RAG回答中展示依据"
          />
        </el-form-item>

        <el-form-item label="文献内容" prop="content">
          <div class="editor-wrapper">
            <div class="editor-toolbar">
              <span class="toolbar-hint">支持 Markdown 格式</span>
              <el-button-group size="small">
                <el-button class="btn-outline" @click="insertMarkdown('**', '**')" title="加粗">B</el-button>
                <el-button class="btn-outline" @click="insertMarkdown('*', '*')" title="斜体"><em>I</em></el-button>
                <el-button class="btn-outline" @click="insertMarkdown('### ', '')" title="标题">H</el-button>
                <el-button class="btn-outline" @click="insertMarkdown('- ', '')" title="列表">•</el-button>
                <el-button class="btn-outline" @click="insertMarkdown('> ', '')" title="引用">❝</el-button>
              </el-button-group>
            </div>
            <el-input
              v-model="formData.content"
              type="textarea"
              :rows="12"
              placeholder="请输入文献内容，支持 Markdown 格式"
            />
          </div>
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="来源出处">
              <el-input v-model="formData.source" placeholder="如：《伤寒论》（选填）" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="上传附件">
              <el-upload
                ref="uploadRef"
                :auto-upload="false"
                :limit="1"
                :on-change="handleFileChange"
                :on-remove="handleFileRemove"
                accept=".pdf,.txt,.doc,.docx"
              >
                <el-button class="btn-outline" size="small" :icon="Upload">选择文件</el-button>
                <template #tip>
                  <span class="upload-tip">支持 PDF/TXT/DOC，大小不超过 20MB</span>
                </template>
              </el-upload>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button class="btn-cancel" @click="dialogVisible = false">取消</el-button>
        <el-button class="btn-primary" :loading="submitLoading" @click="handleSubmit">
          {{ isEdit ? '保存修改' : '上传文献' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 查看文献弹窗 -->
    <el-dialog
      v-model="viewDialogVisible"
      :title="viewDoc?.name"
      width="800px"
      :close-on-click-modal="false"
      class="tcm-dialog"
    >
      <div v-if="viewDoc" class="view-doc-content">
        <div class="doc-meta">
          <el-tag :type="getDocTypeColor(viewDoc.type)" size="small">{{ viewDoc.type }}</el-tag>
          <span class="meta-source" v-if="viewDoc.source">来源：{{ viewDoc.source }}</span>
          <span class="meta-time">上传时间：{{ formatDate(viewDoc.createdAt) }}</span>
        </div>

        <!-- 溯源信息 -->
        <div class="doc-provenance" v-if="viewDoc.source_detail || viewDoc.chapter || viewDoc.original_text">
          <div class="section-label">📖 溯源信息</div>
          <div class="provenance-grid">
            <div class="provenance-item" v-if="viewDoc.source_detail">
              <span class="provenance-label">来源详情：</span>
              <span class="provenance-value">{{ viewDoc.source_detail }}</span>
            </div>
            <div class="provenance-item" v-if="viewDoc.chapter">
              <span class="provenance-label">页码/章节：</span>
              <span class="provenance-value">{{ viewDoc.chapter }}</span>
            </div>
          </div>
          <div class="provenance-quote" v-if="viewDoc.original_text">
            <div class="provenance-label">原文片段：</div>
            <blockquote class="original-text-block">{{ viewDoc.original_text }}</blockquote>
          </div>
        </div>

        <div class="doc-body">
          <div class="section-label">文献内容：</div>
          <div class="markdown-body" v-html="renderMarkdown(viewDoc.content || '')"></div>
        </div>

        <div class="doc-attachment" v-if="viewDoc.fileUrl || viewDoc.fileName">
          <span class="section-label">附件：</span>
          <el-button class="btn-edit" link :icon="Download" @click="downloadFile(viewDoc)">
            {{ viewDoc.fileName || '下载附件' }}
          </el-button>
        </div>
      </div>
      <template #footer>
        <el-button class="btn-cancel" @click="viewDialogVisible = false">关闭</el-button>
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
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus, Upload, Download, Search, Refresh, Delete, Edit, View, WarningFilled, Files } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import MarkdownIt from 'markdown-it'
import { documentApi } from '@/api'
import type { DocumentEntity } from '@/types'

const docTypeOptions = ['药典', '教材', '古籍', '科普', '期刊']

const docTypeColorMap: Record<string, string> = { '药典': 'danger', '教材': 'primary', '古籍': 'warning', '科普': 'info', '期刊': 'success' }
const getDocTypeColor = (t?: string): string => docTypeColorMap[t || ''] || 'info'
const getDocTypeLabel = (t?: string): string => {
  const map: Record<string, string> = { '药典': '药典', '教材': '教材', '古籍': '古籍', '科普': '科普', '期刊': '期刊' }
  return map[t || ''] || t || '-'
}

// ==================== Markdown 工具 ====================
const md = new MarkdownIt({ html: false, linkify: true, breaks: true, typographer: true })
const renderMarkdown = (text: string): string => { if (!text) return ''; return md.render(text) }

const insertMarkdown = (before: string, after: string) => {
  const textarea = document.querySelector('.editor-wrapper textarea') as HTMLTextAreaElement | null
  if (!textarea) return
  const start = textarea.selectionStart; const end = textarea.selectionEnd
  const selected = formData.content.substring(start, end)
  formData.content = formData.content.substring(0, start) + before + selected + after + formData.content.substring(end)
}

const truncateText = (text: string, maxLen: number): string => {
  if (!text) return ''
  return text.length > maxLen ? text.substring(0, maxLen) + '…' : text
}

const formatDate = (dateStr?: string): string => {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

// ==================== 表格数据 ====================
const tableRef = ref()
const loading = ref(false)
const tableData = ref<DocumentEntity[]>([])
const selectedRows = ref<DocumentEntity[]>([])

const searchParams = reactive({ keyword: '', type: '' })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

const fetchData = async () => {
  loading.value = true
  try {
    const res: any = await documentApi.list({
      page: pagination.page, pageSize: pagination.pageSize,
      keyword: searchParams.keyword || undefined,
      type: searchParams.type || undefined
    })
    if (res.code === 200) { tableData.value = res.data?.list ?? res.data?.records ?? []; pagination.total = res.data?.total ?? 0 }
    else if (Array.isArray(res)) { tableData.value = res; pagination.total = res.length }
    else if (res.data && Array.isArray(res.data)) { tableData.value = res.data; pagination.total = res.total ?? res.data.length }
    else { tableData.value = []; pagination.total = 0 }
  } catch (error) { console.error('获取文献列表失败:', error); ElMessage.error('获取文献列表失败') }
  finally { loading.value = false }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchParams.keyword = ''; searchParams.type = ''; handleSearch() }
const handleSelectionChange = (rows: DocumentEntity[]) => { selectedRows.value = rows }

// ==================== 导出 ====================
const handleExport = async () => {
  try {
    const res: any = await documentApi.export()
    const blob = res instanceof Blob ? res : new Blob([res], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url; link.download = '文献数据导出.xlsx'
    document.body.appendChild(link); link.click(); document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { const link = document.createElement('a'); link.href = '/api/admin/documents/export'; link.download = '文献数据导出.xlsx'; document.body.appendChild(link); link.click(); document.body.removeChild(link) }
}

// ==================== 上传/编辑弹窗 ====================
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref('')
const submitLoading = ref(false)
const formRef = ref<FormInstance>()
const uploadRef = ref()
const uploadFile = ref<File | null>(null)

const initFormData = () => ({ name: '', type: '', source_detail: '', original_text: '', chapter: '', content: '', source: '' })
const formData = reactive(initFormData())

const formRules: FormRules = {
  name: [{ required: true, message: '请输入文献标题', trigger: 'blur' }],
  type: [{ required: true, message: '请选择文献类型', trigger: 'change' }],
  content: [{ required: true, message: '请输入文献内容', trigger: 'blur' }]
}

const handleAdd = () => { isEdit.value = false; editId.value = ''; uploadFile.value = null; dialogVisible.value = true }

const handleEdit = (row: DocumentEntity) => {
  isEdit.value = true; editId.value = row.id; uploadFile.value = null
  formData.name = row.name; formData.type = row.type || ''; formData.content = row.content || ''
  formData.source_detail = (row as any).source_detail || row.source_detail || ''
  formData.original_text = (row as any).original_text || row.original_text || ''
  formData.chapter = (row as any).chapter || row.chapter || ''
  formData.source = row.source || ''
  dialogVisible.value = true
}

const resetForm = () => { Object.assign(formData, initFormData()); formRef.value?.resetFields(); uploadFile.value = null; uploadRef.value?.clearFiles() }

const handleFileChange = (file: any) => { uploadFile.value = file.raw || file }
const handleFileRemove = () => { uploadFile.value = null }

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    submitLoading.value = true
    try {
      const payload: any = {
        name: formData.name, type: formData.type, content: formData.content,
        source: formData.source, source_detail: formData.source_detail,
        original_text: formData.original_text, chapter: formData.chapter
      }
      if (uploadFile.value) {
        try {
          const uploadRes: any = await documentApi.upload(uploadFile.value)
          if (uploadRes.code === 200) { payload.fileName = uploadRes.data?.fileName || uploadFile.value.name; payload.fileUrl = uploadRes.data?.url || '' }
        } catch (err) { console.error('附件上传失败:', err) }
      }
      if (isEdit.value) { await documentApi.update(editId.value, payload); ElMessage.success('文献更新成功') }
      else { await documentApi.create(payload); ElMessage.success('文献上传成功') }
      dialogVisible.value = false; fetchData()
    } catch (error) { console.error('提交失败:', error); ElMessage.error('操作失败，请重试') }
    finally { submitLoading.value = false }
  })
}

// ==================== 查看弹窗 ====================
const viewDialogVisible = ref(false)
const viewDoc = ref<DocumentEntity | null>(null)
const handleView = (row: DocumentEntity) => { viewDoc.value = row; viewDialogVisible.value = true }

const downloadFile = (doc: DocumentEntity) => {
  if (doc.fileUrl) window.open(doc.fileUrl, '_blank')
  else ElMessage.warning('该文献暂无附件')
}

// ==================== 删除 ====================
const deleteDialogVisible = ref(false)
const deleteLoading = ref(false)
const isBatchDelete = ref(false)
const deleteTarget = ref<DocumentEntity | null>(null)

const deleteMessage = computed(() => {
  if (isBatchDelete.value) return `确认删除选中的 ${selectedRows.value.length} 条文献？此操作不可恢复。`
  return `确认删除文献「${deleteTarget.value?.name}」？此操作不可恢复。`
})

const handleDelete = (row: DocumentEntity) => { isBatchDelete.value = false; deleteTarget.value = row; deleteDialogVisible.value = true }
const handleBatchDelete = () => {
  if (selectedRows.value.length === 0) { ElMessage.warning('请先选择要删除的文献'); return }
  isBatchDelete.value = true; deleteTarget.value = null; deleteDialogVisible.value = true
}

const confirmDelete = async () => {
  deleteLoading.value = true
  try {
    if (isBatchDelete.value) { const ids = selectedRows.value.map((row) => row.id); await documentApi.batchDelete(ids); ElMessage.success(`成功删除 ${ids.length} 条文献`) }
    else if (deleteTarget.value) { await documentApi.delete(deleteTarget.value.id); ElMessage.success('删除成功') }
    deleteDialogVisible.value = false; tableRef.value?.clearSelection(); fetchData()
  } catch (error) { console.error('删除失败:', error); ElMessage.error('删除失败，请重试') }
  finally { deleteLoading.value = false }
}

// ==================== 初始化 ====================
onMounted(fetchData)
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

.doc-manage {
  padding: 0;
  max-width: 100%;
  overflow: hidden;

  .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;
    .page-title { margin: 0; font-size: 22px; font-weight: 500; color: $text-dark; letter-spacing: 1px; display: flex; align-items: center; gap: 8px;
      .title-icon { color: $soft-gold; font-size: 22px; }
    }
    .header-actions { display: flex; gap: 10px; }
  }

  .search-bar { display: flex; gap: 12px; align-items: center; margin-bottom: 18px; padding: 16px 20px; background: $cream-white; border-radius: 12px; border: 1px solid $border-light; flex-wrap: wrap; }

  .tag-list { display: flex; flex-wrap: wrap; gap: 4px; padding: 2px 0; }
  .text-placeholder { color: #c0c4cc; font-size: 13px; }

  .pagination-wrapper { margin-top: 18px; display: flex; justify-content: flex-end;
    :deep(.el-pagination) { .el-pagination__total { color: $text-light; } .el-pager li { border-radius: 4px; &:hover { color: $mid-green; } &.is-active { background: $gold-light; color: $mid-green; font-weight: 500; } } button:hover { color: $mid-green; } }
  }

  .table-wrapper { width: 100%; overflow-x: auto; border-radius: 12px; border: 1px solid $border-light; background: $cream-white; }

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

  // ===== 编辑器 =====
  .editor-wrapper {
    width: 100%;
    .editor-toolbar { display: flex; justify-content: space-between; align-items: center; padding: 6px 8px; margin-bottom: 4px; background: $cream-bg; border-radius: 4px 4px 0 0; border: 1px solid $border-light; border-bottom: none;
      .toolbar-hint { font-size: 12px; color: $text-light; }
    }
    :deep(.el-textarea__inner) { border-radius: 0 0 4px 4px; font-family: 'Courier New', monospace; font-size: 14px; line-height: 1.8; }
  }

  .upload-tip { font-size: 12px; color: $text-light; margin-left: 8px; }

  // ===== 查看弹窗 =====
  .view-doc-content {
    .doc-meta { display: flex; align-items: center; gap: 16px; padding-bottom: 12px; border-bottom: 1px solid $border-light; margin-bottom: 16px;
      .meta-source, .meta-time { font-size: 13px; color: $text-light; }
    }
    .doc-provenance { margin-bottom: 16px; padding: 14px 16px; background: $cream-bg; border-radius: 10px; border: 1px solid $border-light;
      .section-label { font-size: 14px; font-weight: 500; color: $text-dark; margin-bottom: 10px; }
      .provenance-grid { display: flex; flex-wrap: wrap; gap: 12px 24px; margin-bottom: 8px; }
      .provenance-item { font-size: 13px;
        .provenance-label { color: $text-light; }
        .provenance-value { color: $text-dark; font-weight: 500; }
      }
      .provenance-quote { margin-top: 8px;
        .provenance-label { font-size: 13px; color: $text-light; margin-bottom: 6px; display: block; }
        .original-text-block { margin: 6px 0 0 0; padding: 10px 14px; background: rgba(70, 99, 80, 0.05); border-left: 3px solid $mid-green; border-radius: 4px; font-size: 14px; line-height: 1.8; color: $text-dark; font-style: italic; }
      }
    }
    .doc-body { margin-bottom: 16px;
      .markdown-body { padding: 16px; background: $cream-bg; border-radius: 8px; line-height: 1.8; color: $text-dark; font-size: 14px; max-height: 400px; overflow-y: auto; }
    }
    .doc-attachment { display: flex; align-items: center; gap: 8px; padding-top: 12px; border-top: 1px solid $border-light; }
    .section-label { font-size: 14px; font-weight: 500; color: $text-dark; margin-right: 8px; }
  }

  // 表格内原文片段截断
  .text-preview { cursor: default; color: $text-light; font-size: 13px; }

  .delete-confirm-content { display: flex; flex-direction: column; align-items: center; padding: 16px 0;
    .delete-icon { margin-bottom: 16px; }
    .delete-message { font-size: 15px; color: $text-dark; text-align: center; line-height: 1.6; }
  }
}
</style>

<style lang="scss">
// 原文片段 tooltip（渲染在 body 层，需非 scoped 样式）
.doc-text-tooltip {
  max-width: 420px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.8;
  color: #2c3630;
  background: #faf6ef;
  border: 1px solid rgba(110, 135, 120, 0.18);
  box-shadow: 0 6px 24px rgba(42, 64, 48, 0.1);
}
</style>
