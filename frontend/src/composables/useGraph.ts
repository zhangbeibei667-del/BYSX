import { ref } from 'vue'
import { graphApi } from '@/api'
import type { GraphNode, GraphResponse } from '@/types'

export function useGraph() {
  const graphData = ref<GraphResponse>({ nodes: [], edges: [] })
  const selectedNode = ref<GraphNode | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const loadGraphData = async () => {
    loading.value = true
    error.value = null
    try {
      graphData.value = await graphApi.getFullGraph() as unknown as GraphResponse
      return graphData.value
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '图谱加载失败'
      throw cause
    } finally {
      loading.value = false
    }
  }

  const searchNode = async (query: string) => {
    loading.value = true
    error.value = null
    try {
      graphData.value = await graphApi.searchEntities(query.trim()) as unknown as GraphResponse
      return graphData.value
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '实体搜索失败'
      throw cause
    } finally {
      loading.value = false
    }
  }

  const getNodeRelations = async (nodeId: string) => {
    loading.value = true
    error.value = null
    try {
      graphData.value = await graphApi.getRelatedEntities(nodeId, 2) as unknown as GraphResponse
      return graphData.value
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '关联关系加载失败'
      throw cause
    } finally {
      loading.value = false
    }
  }

  return {
    graphData,
    selectedNode,
    loading,
    error,
    loadGraphData,
    searchNode,
    getNodeRelations
  }
}
