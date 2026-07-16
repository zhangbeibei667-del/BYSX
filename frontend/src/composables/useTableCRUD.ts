import { ref, type Ref } from 'vue'

export interface TablePage<T> {
  list: T[]
  total: number
}

export interface TableCRUDOptions<T extends Record<string, any>, CreateData = Partial<T>, UpdateData = Partial<T>> {
  fetch: (params: { page: number; pageSize: number; keyword: string }) => Promise<TablePage<T>>
  create?: (data: CreateData) => Promise<unknown>
  update?: (id: string, data: UpdateData) => Promise<unknown>
  remove?: (id: string) => Promise<unknown>
  batchRemove?: (ids: string[]) => Promise<unknown>
  importFile?: (file: File) => Promise<unknown>
  exportFile?: () => Promise<Blob>
  getId?: (row: T) => string
}

// 统一处理分页、CRUD、批量删除和导入导出；具体接口由页面注入。
export function useTableCRUD<T extends Record<string, any>, CreateData = Partial<T>, UpdateData = Partial<T>>(
  options: TableCRUDOptions<T, CreateData, UpdateData>
) {
  const dataList = ref<T[]>([])
  const loading = ref(false)
  const total = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(10)
  const searchQuery = ref('')
  const selectedRows = ref<T[]>([])

  const fetchData = async () => {
    loading.value = true
    try {
      const page = await options.fetch({
        page: currentPage.value,
        pageSize: pageSize.value,
        keyword: searchQuery.value.trim()
      })
      dataList.value = page.list
      total.value = page.total
    } finally {
      loading.value = false
    }
  }

  const handleSearch = () => {
    currentPage.value = 1
    fetchData()
  }

  const handleAdd = async (data: CreateData) => {
    if (!options.create) throw new Error('未配置新增接口')
    await options.create(data)
    await fetchData()
  }

  const getRowId = (row: T) => options.getId?.(row) ?? String(row.id)

  const handleEdit = async (row: T, data: UpdateData) => {
    if (!options.update) throw new Error('未配置更新接口')
    await options.update(getRowId(row), data)
    await fetchData()
  }

  const handleDelete = async (id: string) => {
    if (!options.remove) throw new Error('未配置删除接口')
    await options.remove(id)
    await fetchData()
  }

  const handleBatchDelete = async () => {
    if (!options.batchRemove) throw new Error('未配置批量删除接口')
    const ids = selectedRows.value.map(row => getRowId(row as T))
    if (ids.length === 0) return
    await options.batchRemove(ids)
    selectedRows.value = []
    await fetchData()
  }

  const handleImport = async (file: File) => {
    if (!options.importFile) throw new Error('未配置导入接口')
    await options.importFile(file)
    await fetchData()
  }

  const handleExport = async () => {
    if (!options.exportFile) throw new Error('未配置导出接口')
    return options.exportFile()
  }

  return {
    dataList,
    loading,
    total,
    currentPage,
    pageSize,
    searchQuery,
    selectedRows: selectedRows as Ref<T[]>,
    fetchData,
    handleSearch,
    handleAdd,
    handleEdit,
    handleDelete,
    handleBatchDelete,
    handleImport,
    handleExport
  }
}
