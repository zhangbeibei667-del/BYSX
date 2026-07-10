<template>
  <el-dialog
    v-model="visible"
    :title="title"
    width="600px"
    :close-on-click-modal="false"
  >
    <div class="import-dialog">
      <!-- 模板下载 -->
      <div class="template-section">
        <h4>导入模板下载</h4>
        <p class="template-description">
          请先下载模板文件，按照模板格式填写数据后再上传。
        </p>
        <div class="template-buttons">
          <el-button
            type="primary"
            :icon="Download"
            @click="downloadTemplate"
          >
            下载Excel模板
          </el-button>
          <el-button
            type="info"
            :icon="Document"
            @click="viewTemplateFormat"
          >
            查看格式说明
          </el-button>
        </div>
      </div>
      
      <!-- 文件上传 -->
      <div class="upload-section">
        <h4>上传文件</h4>
        <el-upload
          ref="uploadRef"
          class="upload-area"
          drag
          :action="uploadUrl"
          :headers="uploadHeaders"
          :data="uploadData"
          :before-upload="beforeUpload"
          :on-success="handleSuccess"
          :on-error="handleError"
          :on-progress="handleProgress"
          :accept="accept"
          :show-file-list="false"
        >
          <div class="upload-content">
            <el-icon class="upload-icon" :size="48">
              <UploadFilled v-if="!uploading" />
              <Loading v-else />
            </el-icon>
            <p class="upload-text">
              {{ uploading ? '正在上传...' : '点击或拖拽文件到此区域' }}
            </p>
            <p class="upload-hint">
              支持 {{ accept }} 格式，文件大小不超过 10MB
            </p>
          </div>
        </el-upload>
        
        <!-- 上传结果 -->
        <div v-if="uploadResult" class="upload-result">
          <div v-if="uploadResult.success" class="result-success">
            <el-icon color="#67c23a"><CircleCheckFilled /></el-icon>
            <span>导入成功！共处理 {{ uploadResult.total }} 条数据</span>
          </div>
          <div v-else class="result-error">
            <el-icon color="#f56c6c"><CircleCloseFilled /></el-icon>
            <span>导入失败：{{ uploadResult.message }}</span>
          </div>
          
          <!-- 失败详情 -->
          <div v-if="uploadResult.errors?.length" class="error-details">
            <h5>失败记录详情：</h5>
            <el-table
              :data="uploadResult.errors"
              size="small"
              max-height="200"
            >
              <el-table-column prop="row" label="行号" width="80" />
              <el-table-column prop="field" label="字段" width="120" />
              <el-table-column prop="message" label="错误信息" />
            </el-table>
          </div>
        </div>
      </div>
      
      <!-- 导入选项 -->
      <div v-if="showOptions" class="options-section">
        <h4>导入选项</h4>
        <div class="option-items">
          <el-checkbox v-model="options.skipHeader" label="跳过表头行" />
          <el-checkbox v-model="options.ignoreEmptyRows" label="忽略空行" />
          <el-checkbox v-model="options.updateExisting" label="更新已存在的数据" />
        </div>
      </div>
    </div>
    
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="handleCancel">取消</el-button>
        <el-button
          v-if="showConfirm"
          type="primary"
          :loading="uploading"
          @click="handleConfirm"
        >
          确认导入
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Download,
  Document,
  UploadFilled,
  Loading,
  CircleCheckFilled,
  CircleCloseFilled
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

interface Props {
  modelValue: boolean
  title?: string
  uploadUrl?: string
  accept?: string
  showOptions?: boolean
  templateUrl?: string
  entityType?: string
}

interface UploadResult {
  success: boolean
  message: string
  total?: number
  successCount?: number
  errorCount?: number
  errors?: Array<{
    row: number
    field: string
    message: string
  }>
}

const props = withDefaults(defineProps<Props>(), {
  title: '批量导入',
  accept: '.xlsx,.xls',
  showOptions: true,
  templateUrl: '/api/template/download',
  entityType: ''
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  success: [result: any]
  error: [error: any]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const uploadRef = ref()
const uploading = ref(false)
const uploadResult = ref<UploadResult | null>(null)

const options = ref({
  skipHeader: true,
  ignoreEmptyRows: true,
  updateExisting: false
})

const showConfirm = computed(() => !props.uploadUrl)

const uploadHeaders = computed(() => {
  const token = localStorage.getItem('admin_token')
  return {
    Authorization: token ? `Bearer ${token}` : ''
  }
})

const uploadData = computed(() => ({
  entityType: props.entityType,
  ...options.value
}))

const downloadTemplate = () => {
  const link = document.createElement('a')
  link.href = `${props.templateUrl}?type=${props.entityType}`
  link.download = `${props.entityType}_template.xlsx`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

const viewTemplateFormat = () => {
  ElMessage.info({
    message: '模板格式说明：第一行为表头，包含字段名称，后续行按表头格式填写数据',
    duration: 5000
  })
}

const beforeUpload = (file: File) => {
  const isExcel = file.type.includes('excel') || file.type.includes('spreadsheet')
  const isSizeValid = file.size / 1024 / 1024 <= 10
  
  if (!isExcel) {
    ElMessage.error('请上传 Excel 文件')
    return false
  }
  
  if (!isSizeValid) {
    ElMessage.error('文件大小不能超过 10MB')
    return false
  }
  
  uploading.value = true
  uploadResult.value = null
  return true
}

const handleSuccess = (response: any) => {
  uploading.value = false
  
  if (response.code === 200) {
    uploadResult.value = {
      success: true,
      message: '导入成功',
      total: response.data.total,
      successCount: response.data.successCount,
      errorCount: response.data.errorCount,
      errors: response.data.errors
    }
    
    ElMessage.success('导入成功')
    emit('success', response.data)
  } else {
    uploadResult.value = {
      success: false,
      message: response.message || '导入失败'
    }
    ElMessage.error(response.message || '导入失败')
    emit('error', response)
  }
}

const handleError = (error: any) => {
  uploading.value = false
  uploadResult.value = {
    success: false,
    message: '上传过程中发生错误'
  }
  ElMessage.error('上传失败')
  console.error('Upload error:', error)
  emit('error', error)
}

const handleProgress = () => {
  // 上传进度处理
}

const handleConfirm = () => {
  if (uploadRef.value) {
    const fileList = uploadRef.value.uploadFiles
    if (fileList.length === 0) {
      ElMessage.warning('请选择要上传的文件')
      return
    }
    
    // 触发上传
    uploadRef.value.submit()
  }
}

const handleCancel = () => {
  visible.value = false
  resetState()
}

const resetState = () => {
  uploading.value = false
  uploadResult.value = null
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
}

defineExpose({
  resetState
})
</script>

<style scoped lang="scss">
.import-dialog {
  .template-section,
  .upload-section,
  .options-section {
    margin-bottom: 24px;
    
    h4 {
      margin: 0 0 12px 0;
      color: #303133;
      font-size: 16px;
    }
  }
  
  .template-description {
    color: #606266;
    font-size: 14px;
    margin-bottom: 12px;
  }
  
  .template-buttons {
    display: flex;
    gap: 12px;
  }
  
  .upload-area {
    width: 100%;
    
    :deep(.el-upload-dragger) {
      width: 100%;
      height: 180px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
    }
    
    .upload-content {
      text-align: center;
      
      .upload-icon {
        color: #409eff;
        margin-bottom: 12px;
      }
      
      .upload-text {
        color: #606266;
        margin-bottom: 8px;
      }
      
      .upload-hint {
        color: #909399;
        font-size: 12px;
      }
    }
  }
  
  .upload-result {
    margin-top: 16px;
    padding: 12px;
    background-color: #f5f7fa;
    border-radius: 4px;
    
    .result-success,
    .result-error {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 500;
    }
    
    .result-success {
      color: #67c23a;
    }
    
    .result-error {
      color: #f56c6c;
    }
    
    .error-details {
      margin-top: 12px;
      
      h5 {
        margin: 0 0 8px 0;
        color: #303133;
        font-size: 14px;
      }
    }
  }
  
  .option-items {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>