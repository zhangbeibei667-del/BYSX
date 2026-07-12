<template>
  <div class="base-table">
    <!-- 搜索栏 -->
    <div class="table-header" v-if="showSearch">
      <div class="search-bar">
        <el-input
          v-model="searchQuery"
          :placeholder="searchPlaceholder"
          clearable
          @input="handleSearch"
          @clear="handleSearchClear"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        
        <div class="header-actions">
          <slot name="header-actions" />
          
          <el-button
            v-if="showAdd"
            type="primary"
            @click="handleAdd"
            :icon="Plus"
          >
            {{ addButtonText }}
          </el-button>
          
          <el-button
            v-if="showExport && selection.length > 0"
            :icon="Download"
            @click="handleExport"
          >
            导出选中
          </el-button>
          
          <el-button
            v-if="showDelete && selection.length > 0"
            type="danger"
            :icon="Delete"
            @click="handleDeleteSelected"
          >
            删除选中
          </el-button>
        </div>
      </div>
    </div>
    
    <!-- 表格 -->
    <el-table
      ref="tableRef"
      v-loading="loading"
      :data="tableData"
      :border="border"
      :stripe="stripe"
      :row-key="rowKey"
      @selection-change="handleSelectionChange"
    >
      <!-- 选择列 -->
      <el-table-column
        v-if="showSelection"
        type="selection"
        width="55"
        align="center"
      />
      
      <!-- 序号列 -->
      <el-table-column
        v-if="showIndex"
        type="index"
        label="序号"
        width="80"
        align="center"
      />
      
      <!-- 内容列 -->
      <slot />
      
      <!-- 操作列 -->
      <el-table-column
        v-if="showActions"
        label="操作"
        width="180"
        align="center"
        fixed="right"
      >
        <template #default="{ row }">
          <div class="action-buttons">
            <el-button
              v-if="showEdit"
              type="primary"
              link
              size="small"
              @click="handleEdit(row)"
            >
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            
            <el-button
              v-if="showDetail"
              type="info"
              link
              size="small"
              @click="handleDetail(row)"
            >
              <el-icon><View /></el-icon>
              详情
            </el-button>
            
            <el-button
              v-if="showDelete"
              type="danger"
              link
              size="small"
              @click="handleDelete(row)"
            >
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
            
            <slot name="custom-actions" :row="row" />
          </div>
        </template>
      </el-table-column>
    </el-table>
    
    <!-- 分页 -->
    <div class="table-footer" v-if="showPagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
      />
    </div>
    
    <!-- 表单弹窗 -->
    <slot name="form-dialog" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted } from 'vue'
import {
  Search,
  Plus,
  Download,
  Delete,
  Edit,
  View
} from '@element-plus/icons-vue'

interface Props {
  // 数据相关
  tableData?: any[]
  total?: number
  loading?: boolean
  
  // 功能开关
  showSearch?: boolean
  showAdd?: boolean
  showEdit?: boolean
  showDetail?: boolean
  showDelete?: boolean
  showExport?: boolean
  showSelection?: boolean
  showIndex?: boolean
  showActions?: boolean
  showPagination?: boolean
  
  // 样式
  border?: boolean
  stripe?: boolean
  
  // 文本
  searchPlaceholder?: string
  addButtonText?: string
  
  // 其他
  rowKey?: string
}

const props = withDefaults(defineProps<Props>(), {
  tableData: () => [],
  total: 0,
  loading: false,
  showSearch: true,
  showAdd: true,
  showEdit: true,
  showDetail: false,
  showDelete: true,
  showExport: true,
  showSelection: true,
  showIndex: true,
  showActions: true,
  showPagination: true,
  border: true,
  stripe: true,
  searchPlaceholder: '请输入关键词搜索...',
  addButtonText: '新增',
  rowKey: 'id'
})

const emit = defineEmits<{
  search: [query: string]
  'update:page': [page: number]
  'update:size': [size: number]
  add: []
  edit: [row: any]
  detail: [row: any]
  delete: [row: any]
  'delete-selected': [rows: any[]]
  export: []
  'selection-change': [rows: any[]]
}>()

const tableRef = ref()
const searchQuery = ref('')
const selection = ref<any[]>([])
const currentPage = ref(1)
const pageSize = ref(20)

const computedTableData = computed(() => props.tableData)

const handleSearch = () => {
  emit('search', searchQuery.value)
}

const handleSearchClear = () => {
  searchQuery.value = ''
  emit('search', '')
}

const handleSelectionChange = (val: any[]) => {
  selection.value = val
  emit('selection-change', val)
}

const handleAdd = () => {
  emit('add')
}

const handleEdit = (row: any) => {
  emit('edit', row)
}

const handleDetail = (row: any) => {
  emit('detail', row)
}

const handleDelete = (row: any) => {
  emit('delete', row)
}

const handleDeleteSelected = () => {
  if (selection.value.length > 0) {
    emit('delete-selected', selection.value)
  }
}

const handleExport = () => {
  emit('export')
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  emit('update:size', size)
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  emit('update:page', page)
}

const clearSelection = () => {
  if (tableRef.value) {
    tableRef.value.clearSelection()
  }
}

defineExpose({
  clearSelection
})
</script>

<style scoped lang="scss">
.base-table {
  .table-header {
    margin-bottom: 16px;
    
    .search-bar {
      display: flex;
      gap: 16px;
      align-items: center;
      
      .el-input {
        flex: 1;
        max-width: 400px;
      }
      
      .header-actions {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }
    }
  }
  
  .action-buttons {
    display: flex;
    gap: 8px;
    justify-content: center;
  }
  
  .table-footer {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>