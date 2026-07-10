<template>
  <div class="chat-input">
    <div class="input-container">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="3"
        :maxlength="1000"
        placeholder="请输入症状、药材、方剂相关问题..."
        resize="none"
        @keydown.enter.exact.prevent="handleSend"
        @keydown.enter.ctrl="handleCtrlEnter"
      />
      
      <div class="input-actions">
        <div class="action-left">
          <el-button type="info" link size="small" @click="handleClear">
            <el-icon><Delete /></el-icon>
            清空
          </el-button>
          
          <el-button type="info" link size="small" @click="handleExample">
            <el-icon><MagicStick /></el-icon>
            示例
          </el-button>
          
          <el-button type="info" link size="small" @click="toggleAttachment">
            <el-icon>
              <Paperclip v-if="!showAttachment" />
              <Close v-else />
            </el-icon>
            {{ showAttachment ? '取消附件' : '附件' }}
          </el-button>
        </div>
        
        <div class="action-right">
          <el-button
            type="primary"
            :loading="isSending"
            :disabled="!canSend"
            @click="handleSend"
          >
            <el-icon><Promotion /></el-icon>
            发送
          </el-button>
        </div>
      </div>
      
      <!-- 附件区域 -->
      <div v-if="showAttachment" class="attachment-area">
        <el-divider />
        
        <div class="attachment-options">
          <el-upload
            class="upload-area"
            :multiple="true"
            :show-file-list="false"
            :before-upload="handleBeforeUpload"
          >
            <el-button type="primary" link>
              <el-icon><UploadFilled /></el-icon>
              上传文件
            </el-button>
            <template #tip>
              <div class="upload-tip">支持图片、PDF、Word文档格式</div>
            </template>
          </el-upload>
          
          <div class="quick-options">
            <el-button type="info" link size="small" @click="insertTemplate('症状模板')">
              <el-icon><Edit /></el-icon>
              症状模板
            </el-button>
            
            <el-button type="info" link size="small" @click="insertTemplate('病例模板')">
              <el-icon><Notebook /></el-icon>
              病例模板
            </el-button>
          </div>
        </div>
        
        <!-- 已选文件列表 -->
        <div v-if="attachedFiles.length" class="file-list">
          <div v-for="file in attachedFiles" :key="file.name" class="file-item">
            <el-icon><Document /></el-icon>
            <span class="file-name">{{ file.name }}</span>
            <span class="file-size">{{ formatFileSize(file.size) }}</span>
            <el-button type="danger" link size="small" @click="removeFile(file)">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Delete,
  MagicStick,
  Paperclip,
  Close,
  Promotion,
  UploadFilled,
  Edit,
  Notebook,
  Document
} from '@element-plus/icons-vue'

interface Props {
  isSending?: boolean
}

interface Emits {
  (e: 'send', message: string, files?: File[]): void
  (e: 'clear'): void
}

const props = withDefaults(defineProps<Props>(), {
  isSending: false
})

const emit = defineEmits<Emits>()

const inputText = ref('')
const showAttachment = ref(false)
const attachedFiles = ref<File[]>([])

const canSend = computed(() => {
  return inputText.value.trim().length > 0 && !props.isSending
})

const handleSend = () => {
  if (!canSend.value) return
  
  const message = inputText.value.trim()
  emit('send', message, attachedFiles.value)
  inputText.value = ''
  attachedFiles.value = []
  showAttachment.value = false
}

const handleCtrlEnter = () => {
  inputText.value += '\n'
}

const handleClear = () => {
  inputText.value = ''
  attachedFiles.value = []
  showAttachment.value = false
  emit('clear')
}

const handleExample = () => {
  inputText.value = '风寒感冒有哪些症状？应该用什么方剂治疗？'
}

const toggleAttachment = () => {
  showAttachment.value = !showAttachment.value
}

const handleBeforeUpload = (file: File) => {
  const allowedTypes = [
    'image/jpeg',
    'image/png',
    'image/gif',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ]
  
  const maxSize = 10 * 1024 * 1024 // 10MB
  
  if (!allowedTypes.includes(file.type)) {
    ElMessage.error('不支持的文件格式，请上传图片、PDF或Word文档')
    return false
  }
  
  if (file.size > maxSize) {
    ElMessage.error('文件大小不能超过10MB')
    return false
  }
  
  attachedFiles.value.push(file)
  ElMessage.success(`已添加文件: ${file.name}`)
  return false // 阻止自动上传，我们会在发送时一起处理
}

const removeFile = (fileToRemove: File) => {
  attachedFiles.value = attachedFiles.value.filter(file => file !== fileToRemove)
}

const insertTemplate = (type: string) => {
  let template = ''
  
  switch (type) {
    case '症状模板':
      template = `症状描述：
• 主要症状：
• 伴随症状：
• 持续时间：
• 加重缓解因素：`
      break
      
    case '病例模板':
      template = `患者信息：
• 性别：
• 年龄：
• 主诉：
• 舌象：
• 脉象：
• 既往史：
• 辅助检查：`
      break
  }
  
  inputText.value = template
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}
</script>

<style scoped lang="scss">
.chat-input {
  margin-top: 20px;
  
  .input-container {
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    overflow: hidden;
    background: white;
    
    :deep(.el-textarea__inner) {
      border: none;
      border-radius: 0;
      font-size: 14px;
      line-height: 1.5;
      padding: 12px 16px;
      
      &:focus {
        box-shadow: none;
      }
    }
  }
  
  .input-actions {
    padding: 8px 16px;
    border-top: 1px solid #e4e7ed;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #fafafa;
    
    .action-left {
      display: flex;
      gap: 12px;
      
      .el-button {
        color: #666;
        
        &:hover {
          color: #409eff;
        }
      }
    }
    
    .action-right {
      .el-button {
        min-width: 80px;
      }
    }
  }
  
  .attachment-area {
    .attachment-options {
      padding: 12px 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      
      .upload-area {
        display: flex;
        align-items: center;
        gap: 8px;
        
        .upload-tip {
          font-size: 12px;
          color: #666;
        }
      }
      
      .quick-options {
        display: flex;
        gap: 12px;
      }
    }
    
    .file-list {
      padding: 0 16px 12px 16px;
      
      .file-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px;
        background: #f5f7fa;
        border-radius: 4px;
        margin-bottom: 8px;
        
        &:last-child {
          margin-bottom: 0;
        }
        
        .file-name {
          flex: 1;
          font-size: 13px;
          color: #333;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        
        .file-size {
          font-size: 12px;
          color: #666;
        }
      }
    }
  }
}
</style>