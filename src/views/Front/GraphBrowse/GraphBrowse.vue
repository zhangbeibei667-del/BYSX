<template>
  <div class="graph-browse">
    <!-- ==================== 左侧控制面板（20%） ==================== -->
    <aside class="left-panel">
      <div class="panel-scroll">
        <!-- 1. 搜索区域 -->
        <div class="panel-card">
          <div class="card-header">
            <el-icon><Search /></el-icon>
            <span>实体搜索</span>
          </div>
          <div class="search-box">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索药材、方剂、症状..."
              clearable
              @keyup.enter="handleSearch"
              @clear="clearSearch"
            >
              <template #suffix>
                <el-icon class="search-icon" @click="handleSearch"><Search /></el-icon>
              </template>
            </el-input>
            <el-button
              type="primary"
              class="search-btn"
              @click="handleSearch"
              :loading="searchLoading"
            >
              搜索
            </el-button>
          </div>
        </div>

        <!-- 2. 实体筛选 -->
        <div class="panel-card">
          <div class="card-header">
            <span>🎯 实体筛选</span>
          </div>
          <div class="filter-list">
            <label
              v-for="ft in filterTypes"
              :key="ft.type"
              class="filter-item"
              :class="{ unchecked: !ft.checked }"
            >
              <el-checkbox v-model="ft.checked" @change="handleFilterChange" />
              <span class="filter-dot" :style="{ background: ft.color }"></span>
              <span class="filter-label">{{ ft.label }}</span>
            </label>
          </div>
        </div>

        <!-- 3. 图谱概览 -->
        <div class="panel-card">
          <div class="card-header">
            <span>📊 图谱概览</span>
          </div>
          <div class="stats-overview">
            <div class="stats-count">
              <span class="count-num">{{ filteredNodeCount }}</span>
              <span class="count-unit">个节点</span>
              <span class="count-divider">·</span>
              <span class="count-num">{{ filteredEdgeCount }}</span>
              <span class="count-unit">条关系</span>
            </div>
            <div class="legend-grid">
              <div
                v-for="lg in legendItems"
                :key="lg.type"
                class="legend-item"
              >
                <span class="legend-dot" :style="{ background: lg.color }"></span>
                <span>{{ lg.label }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 4. 路径查询 -->
        <div class="panel-card">
          <div class="card-header">
            <span>🔗 关系路径</span>
          </div>
          <div class="path-query">
            <el-select
              v-model="pathSource"
              placeholder="起点实体"
              filterable
              clearable
              :disabled="allEntityOptions.length === 0"
            >
              <el-option
                v-for="opt in allEntityOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              >
                <span class="entity-option">
                  <span class="option-dot" :style="{ background: opt.color }"></span>
                  <span>{{ opt.label }}</span>
                  <span class="option-type">{{ opt.type }}</span>
                </span>
              </el-option>
            </el-select>
            <span class="path-arrow">→</span>
            <el-select
              v-model="pathTarget"
              placeholder="终点实体"
              filterable
              clearable
              :disabled="allEntityOptions.length === 0"
            >
              <el-option
                v-for="opt in allEntityOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              >
                <span class="entity-option">
                  <span class="option-dot" :style="{ background: opt.color }"></span>
                  <span>{{ opt.label }}</span>
                  <span class="option-type">{{ opt.type }}</span>
                </span>
              </el-option>
            </el-select>
            <el-button
              type="success"
              class="path-btn"
              @click="handlePathQuery"
              :loading="pathLoading"
              :disabled="!pathSource || !pathTarget"
            >
              查询路径
            </el-button>
            <el-button
              v-if="activePath.length > 0"
              text
              size="small"
              type="warning"
              @click="clearPath"
            >
              清除路径
            </el-button>
          </div>
        </div>

        <!-- 5. 快速跳转 - 热门实体 -->
        <div class="panel-card">
          <div class="card-header">
            <span>🔥 热门实体</span>
          </div>
          <div class="hot-entities">
            <span
              v-for="hot in hotEntities"
              :key="hot.id"
              class="hot-tag"
              :style="{ borderColor: hot.color, color: hot.color }"
              @click="jumpToEntity(hot.id)"
            >
              {{ hot.label }}
            </span>
            <span v-if="hotEntities.length === 0" class="no-data">暂无热门实体</span>
          </div>
        </div>
      </div>
    </aside>

    <!-- ==================== 中央图谱画布（60%） ==================== -->
    <section class="center-canvas" ref="canvasContainer">
      <!-- 星空背景 -->
      <div class="starfield-bg"></div>

      <!-- ECharts 挂载容器 -->
      <div ref="chartRef" class="chart-container"></div>

      <!-- 空状态 -->
      <div v-if="!loading && allNodes.length === 0" class="empty-state">
        <el-empty description="暂无图谱数据">
          <el-button type="primary" @click="loadGraphData">重新加载</el-button>
        </el-empty>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="loading-state">
        <el-icon class="loading-icon"><Loading /></el-icon>
        <p>正在加载知识图谱...</p>
      </div>

      <!-- 左上角：当前定位实体 -->
      <div v-if="selectedNode" class="location-tag">
        <el-icon><Position /></el-icon>
        <span>{{ selectedNode.label }}</span>
      </div>

      <!-- 右上角：浮动工具栏 -->
      <div class="canvas-toolbar">
        <el-tooltip content="放大" placement="left">
          <button class="tool-btn" @click="zoomIn" :disabled="zoomLevel >= 5">
            <el-icon><ZoomIn /></el-icon>
          </button>
        </el-tooltip>
        <el-tooltip content="缩小" placement="left">
          <button class="tool-btn" @click="zoomOut" :disabled="zoomLevel <= 0.2">
            <el-icon><ZoomOut /></el-icon>
          </button>
        </el-tooltip>
        <el-tooltip content="重置视图" placement="left">
          <button class="tool-btn" @click="resetView">
            <el-icon><RefreshRight /></el-icon>
          </button>
        </el-tooltip>
        <el-tooltip content="导出截图" placement="left">
          <button class="tool-btn" @click="exportImage">
            <el-icon><Download /></el-icon>
          </button>
        </el-tooltip>
      </div>
    </section>

    <!-- ==================== 右侧详情面板（20%） ==================== -->
    <transition name="slide-right">
      <aside v-if="selectedNode" class="right-panel">
        <div class="detail-scroll">
          <!-- 关闭按钮 -->
          <button class="close-btn" @click="clearSelection">
            <el-icon><Close /></el-icon>
          </button>

          <!-- 实体头部 -->
          <div class="detail-header">
            <h2 class="detail-name">{{ selectedNode.label }}</h2>
            <span
              class="detail-type-tag"
              :style="{
                background: getTypeColor(selectedNode.type),
                color: '#fff'
              }"
            >
              {{ selectedNode.type }}
            </span>
          </div>

          <!-- 加载详情 -->
          <div v-if="detailLoading" class="detail-loading">
            <el-icon class="loading-icon"><Loading /></el-icon>
            <p>加载详情中...</p>
          </div>

          <!-- 属性列表 -->
          <div v-else-if="entityDetail" class="detail-section">
            <h3 class="section-label">📋 属性信息</h3>
            <div class="property-list">
              <div
                v-for="(value, key) in displayProperties"
                :key="key"
                class="property-row"
              >
                <span class="prop-label">{{ key }}</span>
                <span class="prop-value">{{ value }}</span>
              </div>
            </div>
            <div v-if="Object.keys(displayProperties).length === 0" class="no-data">
              暂无属性信息
            </div>
          </div>

          <!-- 关联关系 -->
          <div class="detail-section">
            <h3 class="section-label">🔗 关联关系</h3>
            <div v-if="relatedEdges.length > 0" class="relation-list">
              <div
                v-for="(rel, idx) in relatedEdges"
                :key="idx"
                class="relation-item"
                @click="jumpToRelatedEntity(rel)"
              >
                <span class="rel-source">
                  {{ rel.sourceLabel }}
                  <span
                    class="rel-type-dot"
                    :style="{ background: getTypeColor(rel.sourceType) }"
                  ></span>
                </span>
                <span class="rel-arrow">→</span>
                <span class="rel-label-tag">{{ rel.label }}</span>
                <span class="rel-arrow">→</span>
                <span class="rel-target">
                  <span
                    class="rel-type-dot"
                    :style="{ background: getTypeColor(rel.targetType) }"
                  ></span>
                  {{ rel.targetLabel }}
                </span>
              </div>
            </div>
            <div v-else class="no-data">暂无关联关系</div>
          </div>

          <!-- 底部操作按钮 -->
          <div class="detail-actions">
            <el-button
              type="primary"
              @click="goToAdminDetail"
              :disabled="!isAdmin"
            >
              <el-icon><Edit /></el-icon>
              查看详情（后台）
            </el-button>
            <el-button
              :type="isFavorited ? 'warning' : 'default'"
              @click="toggleFavorite"
            >
              <el-icon><StarFilled v-if="isFavorited" /><Star v-else /></el-icon>
              {{ isFavorited ? '已收藏' : '收藏节点' }}
            </el-button>
          </div>
        </div>
      </aside>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Search, ZoomIn, ZoomOut, RefreshRight, Download,
  Position, Close, Edit, Star, StarFilled, Loading
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { graphApi, statsApi, entityApi } from '@/api'
import { useGraphStore } from '@/store'
import type { GraphNode, GraphEdge } from '@/types'

const router = useRouter()
const graphStore = useGraphStore()

// ==================== 常量定义 ====================
const TYPE_COLORS: Record<string, string> = {
  '药材': '#10b981',
  '方剂': '#6366f1',
  '症状': '#f59e0b',
  '证候': '#b91c1c',
  '功效': '#06b6d4',
  '禁忌': '#ef4444',
  '文献': '#8b5cf6',
}

const TYPE_LABELS: Record<string, string> = {
  '药材': '药材',
  '方剂': '方剂',
  '症状': '症状',
  '证候': '证候',
}

const FILTER_TYPE_MAP: Record<string, string> = {
  '药材': '药材',
  '方剂': '方剂',
  '症状': '症状',
  '证候': '证候',
}

const PROPERTY_LABEL_MAP: Record<string, string> = {
  nature_and_flavor: '性味',
  channel_tropism: '归经',
  efficacy: '功效',
  indications: '主治',
  usage_dosage: '用法用量',
  contraindications: '禁忌',
  processing_method: '炮制方法',
  composition: '组成',
  preparation: '制法',
  functions: '功用',
  modern_application: '现代应用',
  body_part: '部位',
  nature: '性质',
  associated_symptoms: '伴随症状',
  differentiation: '辨证要点',
  pathogenesis: '病机',
  clinical_manifestations: '临床表现',
  treatment_principle: '治则',
  commonly_used_formulas: '常用方剂',
  description: '描述',
  category: '分类',
  source: '来源',
}

// ==================== 响应式状态 ====================

// 数据
const allNodes = ref<GraphNode[]>([])
const allEdges = ref<GraphEdge[]>([])
const loading = ref(false)

// 搜索
const searchKeyword = ref('')
const searchLoading = ref(false)

// 筛选
const filterTypes = reactive([
  { type: '药材', label: '药材', color: TYPE_COLORS['药材'], checked: true },
  { type: '方剂', label: '方剂', color: TYPE_COLORS['方剂'], checked: true },
  { type: '症状', label: '症状', color: TYPE_COLORS['症状'], checked: true },
  { type: '证候', label: '证候', color: TYPE_COLORS['证候'], checked: true },
])

// 路径查询
const pathSource = ref('')
const pathTarget = ref('')
const pathLoading = ref(false)
const activePath = ref<{ nodes: string[]; edges: [string, string][] }>({ nodes: [], edges: [] })

// 热门实体
const hotEntities = ref<Array<{ id: string; label: string; type: string; color: string }>>([])

// 选中节点
const selectedNode = ref<GraphNode | null>(null)
const entityDetail = ref<Record<string, any> | null>(null)
const detailLoading = ref(false)

// 收藏
const favorites = ref<Set<string>>(new Set(JSON.parse(localStorage.getItem('graph_favorites') || '[]')))

// 图谱实例
const chartRef = ref<HTMLDivElement>()
const canvasContainer = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null
const zoomLevel = ref(1)

// 权限
const isAdmin = computed(() => !!localStorage.getItem('admin_token'))
const isFavorited = computed(() => selectedNode.value ? favorites.value.has(selectedNode.value.id) : false)

// ==================== 计算属性 ====================

// 筛选后的节点
const filteredNodes = computed(() => {
  const checkedTypes = filterTypes.filter(f => f.checked).map(f => f.type)
  return allNodes.value.filter(n => checkedTypes.includes(n.type))
})

// 筛选后的边（两端节点都在筛选结果中）
const filteredEdges = computed(() => {
  const filteredNodeIds = new Set(filteredNodes.value.map(n => n.id))
  return allEdges.value.filter(
    e => filteredNodeIds.has(e.source) && filteredNodeIds.has(e.target)
  )
})

const filteredNodeCount = computed(() => filteredNodes.value.length)
const filteredEdgeCount = computed(() => filteredEdges.value.length)

// 图谱概览图例
const legendItems = computed(() =>
  filterTypes.map(f => ({ type: f.type, label: f.label, color: f.color }))
)

// 所有实体选项（用于路径查询下拉框）
const allEntityOptions = computed(() =>
  allNodes.value.map(n => ({
    value: n.id,
    label: n.label,
    type: n.type,
    color: getTypeColor(n.type),
  }))
)

// 当前选中节点的关联边
const relatedEdges = computed(() => {
  if (!selectedNode.value) return []
  const nodeId = selectedNode.value.id
  return allEdges.value
    .filter(e => e.source === nodeId || e.target === nodeId)
    .map(e => {
      const isSource = e.source === nodeId
      const otherId = isSource ? e.target : e.source
      const otherNode = allNodes.value.find(n => n.id === otherId)
      return {
        sourceLabel: isSource ? selectedNode.value!.label : (otherNode?.label || otherId),
        targetLabel: isSource ? (otherNode?.label || otherId) : selectedNode.value!.label,
        sourceType: isSource ? selectedNode.value!.type : (otherNode?.type || ''),
        targetType: isSource ? (otherNode?.type || '') : selectedNode.value!.type,
        label: e.label,
        otherId,
        otherType: otherNode?.type || '',
      }
    })
})

// 展示的属性（映射中文名）
const displayProperties = computed(() => {
  if (!entityDetail.value) return {}
  const props = entityDetail.value.properties || entityDetail.value
  const mapped: Record<string, string> = {}
  for (const [key, value] of Object.entries(props)) {
    if (key === 'id' || key === 'name' || key === 'createdAt' || key === 'updatedAt') continue
    const label = PROPERTY_LABEL_MAP[key] || key
    mapped[label] = String(value)
  }
  // 也处理顶层字段
  if (entityDetail.value.category && !mapped['分类']) {
    mapped['分类'] = entityDetail.value.category
  }
  if (entityDetail.value.description && !mapped['描述']) {
    mapped['描述'] = entityDetail.value.description
  }
  return mapped
})

// ==================== 工具函数 ====================

function getTypeColor(type: string): string {
  return TYPE_COLORS[type] || '#94a3b8'
}

function calculateDegree(nodes: GraphNode[], edges: GraphEdge[]): Record<string, number> {
  const degree: Record<string, number> = {}
  nodes.forEach(n => { degree[n.id] = 0 })
  edges.forEach(e => {
    degree[e.source] = (degree[e.source] || 0) + 1
    degree[e.target] = (degree[e.target] || 0) + 1
  })
  return degree
}

// ==================== 图谱渲染 ====================

function buildChartOption(
  nodes: GraphNode[],
  edges: GraphEdge[],
  highlightPath?: { nodes: string[]; edges: [string, string][] }
) {
  const degreeMap = calculateDegree(allNodes.value, allEdges.value)
  const pathNodeSet = new Set(highlightPath?.nodes || [])
  const pathEdgeSet = new Set(
    (highlightPath?.edges || []).map(([s, t]) => `${s}->${t}`)
  )

  const isPathActive = highlightPath && highlightPath.nodes.length > 0

  const chartNodes = nodes.map(n => {
    const degree = degreeMap[n.id] || 0
    const size = Math.min(25 + degree * 4, 60)
    const color = getTypeColor(n.type)
    const inPath = pathNodeSet.has(n.id)
    const dimmed = isPathActive && !inPath

    return {
      id: n.id,
      name: n.label,
      symbol: n.type === '方剂' ? 'diamond' as const : 'circle' as const,
      symbolSize: size,
      category: n.type,
      // 存储原始数据
      _rawType: n.type,
      _rawId: n.id,
      itemStyle: {
        color: inPath ? '#fbbf24' : color,
        borderColor: inPath ? '#f59e0b' : 'rgba(255,255,255,0.3)',
        borderWidth: inPath ? 2 : 0.5,
        shadowColor: inPath ? '#fbbf24' : color,
        shadowBlur: inPath ? 25 : 12,
        opacity: dimmed ? 0.25 : 1,
      },
      label: {
        show: !dimmed || inPath,
        color: dimmed ? 'rgba(148,163,184,0.3)' : '#e2e8f0',
        fontSize: 11,
        position: 'bottom' as const,
        distance: 6,
        textShadowColor: inPath ? '#fbbf24' : 'transparent',
        textShadowBlur: inPath ? 8 : 0,
      },
      emphasis: {
        scale: 1.3,
        itemStyle: {
          shadowBlur: 30,
          shadowColor: inPath ? '#fbbf24' : color,
        },
        label: {
          fontSize: 14,
          fontWeight: 'bold',
          color: '#ffffff',
        },
      },
    }
  })

  const chartEdges = edges.map(e => {
    const edgeKey = `${e.source}->${e.target}`
    const reverseKey = `${e.target}->${e.source}`
    const inPath = pathEdgeSet.has(edgeKey) || pathEdgeSet.has(reverseKey)
    const dimmed = isPathActive && !inPath

    return {
      source: e.source,
      target: e.target,
      name: e.label,
      _rawLabel: e.label,
      lineStyle: {
        color: inPath ? '#fbbf24' : 'rgba(148,163,184,0.35)',
        width: inPath ? 2.5 : 1,
        opacity: dimmed ? 0.1 : (inPath ? 1 : 0.7),
        curveness: 0.15,
        shadowColor: inPath ? '#fbbf24' : 'transparent',
        shadowBlur: inPath ? 6 : 0,
      },
      emphasis: {
        lineStyle: {
          color: '#fbbf24',
          width: 3,
          opacity: 1,
        },
      },
    }
  })

  return {
    backgroundColor: 'transparent',
    tooltip: {
      show: true,
      backgroundColor: 'rgba(15,23,42,0.95)',
      borderColor: 'rgba(148,163,184,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 13 },
      formatter: (params: any) => {
        if (params.dataType === 'edge') {
          const srcName = allNodes.value.find(n => n.id === params.data.source)?.label || params.data.source
          const tgtName = allNodes.value.find(n => n.id === params.data.target)?.label || params.data.target
          return `<span style="color:#94a3b8">${srcName}</span>
                  <span style="color:#fbbf24;margin:0 6px">—${params.data._rawLabel || params.data.name || '关联'}→</span>
                  <span style="color:#94a3b8">${tgtName}</span>`
        }
        const type = params.data._rawType || params.data.category || ''
        const color = getTypeColor(type)
        return `<b style="font-size:14px;color:#fff">${params.data.name || params.name}</b>
                <br/><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};margin-right:6px"></span>
                <span style="color:#94a3b8">${type}</span>`
      },
    },
    animationDuration: 800,
    animationEasing: 'cubicInOut' as const,
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        zoom: zoomLevel.value,
        center: ['50%', '50%'],
        force: {
          initIterations: 300,
          repulsion: 350,
          gravity: 0.06,
          edgeLength: [120, 250],
          layoutAnimation: true,
          friction: 0.6,
        },
        data: chartNodes,
        edges: chartEdges,
        // 分类颜色
        categories: Object.entries(TYPE_COLORS).map(([name, color]) => ({
          name,
          itemStyle: { color },
        })),
        emphasis: {
          focus: 'adjacency' as const,
          blur: {
            itemStyle: { opacity: 0.3 },
            lineStyle: { opacity: 0.1 },
          },
        },
        scaleLimit: {
          min: 0.1,
          max: 5,
        },
      },
    ],
  }
}

function initChart() {
  if (!chartRef.value) return
  if (chartInstance) {
    chartInstance.dispose()
  }

  chartInstance = echarts.init(chartRef.value, undefined, {
    devicePixelRatio: window.devicePixelRatio || 1,
  })

  // 监听缩放变化
  chartInstance.on('graphroam', () => {
    if (chartInstance) {
      const option = chartInstance.getOption() as any
      const seriesOpt = option.series?.[0]
      if (seriesOpt && typeof seriesOpt.zoom === 'number') {
        zoomLevel.value = Math.round(seriesOpt.zoom * 100) / 100
      }
    }
  })

  // 监听节点点击
  chartInstance.on('click', (params: any) => {
    if (params.dataType === 'node') {
      const nodeId = params.data?._rawId || params.data?.id
      if (nodeId) {
        handleNodeClick(nodeId)
      }
    }
  })

  renderChart()
}

function renderChart(highlightPath?: { nodes: string[]; edges: [string, string][] }) {
  if (!chartInstance) return
  const nodes = filteredNodes.value
  const edges = filteredEdges.value
  if (nodes.length === 0) {
    chartInstance.setOption({
      backgroundColor: 'transparent',
      series: [{ type: 'graph', data: [], edges: [] }],
    }, true)
    return
  }
  const option = buildChartOption(nodes, edges, highlightPath)
  chartInstance.setOption(option, true)
}

function resizeChart() {
  if (chartInstance && chartRef.value) {
    chartInstance.resize()
  }
}

// ==================== 数据加载 ====================

async function loadGraphData() {
  loading.value = true
  try {
    const response: any = await graphApi.getFullGraph()
    if (response?.data && response.data.nodes?.length > 0) {
      allNodes.value = response.data.nodes
      allEdges.value = response.data.edges || []
    } else if (response?.nodes?.length > 0) {
      allNodes.value = response.nodes
      allEdges.value = response.edges || []
    } else {
      useMockGraphData()
    }
  } catch {
    console.log('API 未就绪，使用模拟图谱数据')
    useMockGraphData()
  } finally {
    loading.value = false
    await nextTick()
    initChart()
    updateHotEntities()
  }
}

function useMockGraphData() {
  allNodes.value = [
    { id: 'H001', label: '酸枣仁', type: '药材' },
    { id: 'H002', label: '远志', type: '药材' },
    { id: 'H003', label: '人参', type: '药材' },
    { id: 'H004', label: '黄芪', type: '药材' },
    { id: 'H005', label: '当归', type: '药材' },
    { id: 'H006', label: '茯苓', type: '药材' },
    { id: 'H007', label: '甘草', type: '药材' },
    { id: 'H008', label: '白术', type: '药材' },
    { id: 'H009', label: '麻黄', type: '药材' },
    { id: 'H010', label: '桂枝', type: '药材' },
    { id: 'H011', label: '杏仁', type: '药材' },
    { id: 'H012', label: '柴胡', type: '药材' },
    { id: 'H013', label: '黄芩', type: '药材' },
    { id: 'H014', label: '陈皮', type: '药材' },
    { id: 'H015', label: '升麻', type: '药材' },
    { id: 'F001', label: '归脾汤', type: '方剂' },
    { id: 'F002', label: '麻黄汤', type: '方剂' },
    { id: 'F003', label: '小柴胡汤', type: '方剂' },
    { id: 'F004', label: '补中益气汤', type: '方剂' },
    { id: 'F005', label: '四物汤', type: '方剂' },
    { id: 'S001', label: '失眠', type: '症状' },
    { id: 'S002', label: '心悸', type: '症状' },
    { id: 'S003', label: '畏寒', type: '症状' },
    { id: 'S004', label: '咳嗽', type: '症状' },
    { id: 'S005', label: '食少', type: '症状' },
    { id: 'Z001', label: '心脾两虚', type: '证候' },
    { id: 'Z002', label: '外感风寒', type: '证候' },
    { id: 'Z003', label: '少阳证', type: '证候' },
    { id: 'Z004', label: '脾虚气陷', type: '证候' },
    { id: 'Z005', label: '血虚证', type: '证候' },
  ]

  allEdges.value = [
    { source: 'F001', target: 'H001', label: '包含' },
    { source: 'F001', target: 'H002', label: '包含' },
    { source: 'F001', target: 'H003', label: '包含' },
    { source: 'F001', target: 'H004', label: '包含' },
    { source: 'F001', target: 'H005', label: '包含' },
    { source: 'F001', target: 'H006', label: '包含' },
    { source: 'F001', target: 'Z001', label: '主治' },
    { source: 'S001', target: 'Z001', label: '提示' },
    { source: 'S002', target: 'Z001', label: '提示' },
    { source: 'S005', target: 'Z001', label: '提示' },
    { source: 'F002', target: 'H009', label: '包含' },
    { source: 'F002', target: 'H010', label: '包含' },
    { source: 'F002', target: 'H011', label: '包含' },
    { source: 'F002', target: 'H007', label: '包含' },
    { source: 'F002', target: 'Z002', label: '主治' },
    { source: 'S003', target: 'Z002', label: '提示' },
    { source: 'S004', target: 'Z002', label: '提示' },
    { source: 'F003', target: 'H012', label: '包含' },
    { source: 'F003', target: 'H013', label: '包含' },
    { source: 'F003', target: 'H003', label: '包含' },
    { source: 'F003', target: 'H007', label: '包含' },
    { source: 'F003', target: 'Z003', label: '主治' },
    { source: 'F004', target: 'H004', label: '包含' },
    { source: 'F004', target: 'H008', label: '包含' },
    { source: 'F004', target: 'H005', label: '包含' },
    { source: 'F004', target: 'H014', label: '包含' },
    { source: 'F004', target: 'H015', label: '包含' },
    { source: 'F004', target: 'Z004', label: '主治' },
    { source: 'F005', target: 'H005', label: '包含' },
    { source: 'F005', target: 'H006', label: '包含' },
    { source: 'F005', target: 'Z005', label: '主治' },
    { source: 'H009', target: 'H007', label: '配伍' },
    { source: 'H003', target: 'H004', label: '配伍' },
    { source: 'H005', target: 'H003', label: '配伍' },
  ]
}

function updateHotEntities() {
  // 根据度中心性计算热门实体
  const degreeMap = calculateDegree(allNodes.value, allEdges.value)
  const sorted = [...allNodes.value]
    .sort((a, b) => (degreeMap[b.id] || 0) - (degreeMap[a.id] || 0))
    .slice(0, 6)

  hotEntities.value = sorted.map(n => ({
    id: n.id,
    label: n.label,
    type: n.type,
    color: getTypeColor(n.type),
  }))
}

// ==================== 搜索 ====================

async function handleSearch() {
  const keyword = searchKeyword.value.trim()
  if (!keyword) {
    ElMessage.warning('请输入搜索关键词')
    return
  }

  searchLoading.value = true
  try {
    const checkedTypes = filterTypes.filter(f => f.checked).map(f => f.type)
    const response: any = await graphApi.searchEntities(keyword, checkedTypes)

    let newNodes: GraphNode[] = []
    let newEdges: GraphEdge[] = []

    if (response?.data && response.data.nodes?.length > 0) {
      newNodes = response.data.nodes
      newEdges = response.data.edges || []
    } else if (response?.nodes?.length > 0) {
      newNodes = response.nodes
      newEdges = response.edges || []
    }

    if (newNodes.length === 0) {
      ElMessage.info(`未找到与"${keyword}"相关的实体`)
      return
    }

    // 合并到全量数据（去重）
    const existingIds = new Set(allNodes.value.map(n => n.id))
    newNodes.forEach(n => {
      if (!existingIds.has(n.id)) {
        allNodes.value.push(n)
        existingIds.add(n.id)
      }
    })
    const existingEdgeKeys = new Set(allEdges.value.map(e => `${e.source}->${e.target}`))
    newEdges.forEach(e => {
      const key = `${e.source}->${e.target}`
      if (!existingEdgeKeys.has(key)) {
        allEdges.value.push(e)
        existingEdgeKeys.add(key)
      }
    })

    await nextTick()
    renderChart()
    updateHotEntities()

    // 对第一个结果闪烁
    const targetNode = allNodes.value.find(n => n.id === newNodes[0].id)
    if (targetNode) {
      blinkNode(targetNode.id)
    }
  } catch {
    ElMessage.error('搜索失败，请稍后重试')
  } finally {
    searchLoading.value = false
  }
}

function clearSearch() {
  searchKeyword.value = ''
}

// ==================== 筛选 ====================

function handleFilterChange() {
  renderChart(activePath.value.nodes.length > 0 ? activePath.value : undefined)
}

// ==================== 节点交互 ====================

function handleNodeClick(nodeId: string) {
  const node = allNodes.value.find(n => n.id === nodeId)
  if (!node) return

  // 清除路径高亮
  if (activePath.value.nodes.length > 0) {
    activePath.value = { nodes: [], edges: [] }
  }

  selectedNode.value = node
  loadEntityDetail(nodeId)

  // 高亮选中节点
  if (chartInstance) {
    chartInstance.dispatchAction({ type: 'highlight', seriesIndex: 0, name: node.label })
  }

  // 更新 store
  graphStore.selectNode(node)
}

function clearSelection() {
  selectedNode.value = null
  entityDetail.value = null
  graphStore.clearSelection()
  if (chartInstance) {
    chartInstance.dispatchAction({ type: 'downplay', seriesIndex: 0 })
  }
}

async function loadEntityDetail(nodeId: string) {
  detailLoading.value = true
  entityDetail.value = null
  try {
    const response: any = await graphApi.getEntityDetail(nodeId)
    if (response?.data) {
      entityDetail.value = response.data
    } else if (response) {
      entityDetail.value = response
    } else {
      // 使用图谱节点自身属性
      const node = allNodes.value.find(n => n.id === nodeId)
      entityDetail.value = node?.properties || node || {}
    }
  } catch {
    const node = allNodes.value.find(n => n.id === nodeId)
    entityDetail.value = node?.properties || {}
  } finally {
    detailLoading.value = false
  }
}

// ==================== 路径查询 ====================

async function handlePathQuery() {
  if (!pathSource.value || !pathTarget.value) return
  if (pathSource.value === pathTarget.value) {
    ElMessage.warning('起点和终点不能相同')
    return
  }

  pathLoading.value = true
  try {
    const response: any = await graphApi.findRelationPath(pathSource.value, pathTarget.value)

    let pathNodes: GraphNode[] = []
    let pathEdges: GraphEdge[] = []

    if (response?.data) {
      pathNodes = response.data.nodes || []
      pathEdges = response.data.edges || []
    } else if (response) {
      pathNodes = response.nodes || []
      pathEdges = response.edges || []
    }

    if (pathNodes.length === 0) {
      ElMessage.info('未找到两个实体之间的关联路径')
      activePath.value = { nodes: [], edges: [] }
      return
    }

    // 合并路径数据到全量数据
    const existingIds = new Set(allNodes.value.map(n => n.id))
    pathNodes.forEach(n => {
      if (!existingIds.has(n.id)) {
        allNodes.value.push(n)
        existingIds.add(n.id)
      }
    })
    const existingEdgeKeys = new Set(allEdges.value.map(e => `${e.source}->${e.target}`))
    pathEdges.forEach(e => {
      const key = `${e.source}->${e.target}`
      if (!existingEdgeKeys.has(key)) {
        allEdges.value.push(e)
        existingEdgeKeys.add(key)
      }
    })

    const nodeIds = pathNodes.map(n => n.id)
    const edgePairs: [string, string][] = pathEdges.map(e => [e.source, e.target] as [string, string])

    activePath.value = { nodes: nodeIds, edges: edgePairs }

    await nextTick()
    renderChart(activePath.value)

    ElMessage.success(`找到路径，共 ${nodeIds.length} 个节点，${edgePairs.length} 条关系`)
  } catch {
    // 客户端计算简单路径
    const found = findLocalPath(pathSource.value, pathTarget.value)
    if (found) {
      activePath.value = found
      renderChart(activePath.value)
      ElMessage.success(`找到本地路径，共 ${found.nodes.length} 个节点，${found.edges.length} 条关系`)
    } else {
      ElMessage.info('未找到两个实体之间的关联路径')
      activePath.value = { nodes: [], edges: [] }
    }
  } finally {
    pathLoading.value = false
  }
}

function findLocalPath(sourceId: string, targetId: string): { nodes: string[]; edges: [string, string][] } | null {
  // BFS 最短路径
  const adj: Record<string, Array<{ node: string; edgeLabel: string }>> = {}
  allEdges.value.forEach(e => {
    if (!adj[e.source]) adj[e.source] = []
    if (!adj[e.target]) adj[e.target] = []
    adj[e.source].push({ node: e.target, edgeLabel: e.label })
    adj[e.target].push({ node: e.source, edgeLabel: e.label })
  })

  if (!adj[sourceId] || !adj[targetId]) return null

  const visited = new Set<string>()
  const parent: Record<string, { node: string; from: string; label: string } | null> = { [sourceId]: null }
  const queue = [sourceId]
  visited.add(sourceId)

  while (queue.length > 0) {
    const current = queue.shift()!
    if (current === targetId) break
    for (const neighbor of adj[current] || []) {
      if (!visited.has(neighbor.node)) {
        visited.add(neighbor.node)
        parent[neighbor.node] = { node: neighbor.node, from: current, label: neighbor.edgeLabel }
        queue.push(neighbor.node)
      }
    }
  }

  if (!parent[targetId]) return null

  // 回溯路径
  const nodes: string[] = []
  const edges: [string, string][] = []
  let current: string | null = targetId
  while (current && parent[current]) {
    nodes.unshift(current)
    const p = parent[current]!
    edges.unshift([p.from, current])
    current = p.from
  }
  nodes.unshift(sourceId)

  return { nodes, edges }
}

function clearPath() {
  activePath.value = { nodes: [], edges: [] }
  renderChart()
}

// ==================== 画面控制 ====================

function zoomIn() {
  zoomLevel.value = Math.min(zoomLevel.value * 1.4, 5)
  applyZoom()
}

function zoomOut() {
  zoomLevel.value = Math.max(zoomLevel.value / 1.4, 0.1)
  applyZoom()
}

function applyZoom() {
  if (!chartInstance) return
  chartInstance.setOption({
    series: [{ zoom: zoomLevel.value }],
  })
}

function resetView() {
  zoomLevel.value = 1
  if (chartInstance) {
    chartInstance.dispatchAction({ type: 'restore' })
  }
}

function exportImage() {
  if (!chartInstance) return
  const url = chartInstance.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#0a1628',
  })
  const link = document.createElement('a')
  link.href = url
  link.download = `知识图谱截图_${new Date().toISOString().slice(0, 10)}.png`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  ElMessage.success('截图已导出')
}

// ==================== 闪烁 & 跳转 ====================

function blinkNode(nodeId: string) {
  if (!chartInstance) return
  const node = allNodes.value.find(n => n.id === nodeId)
  if (!node) return

  let count = 0
  const maxBlinks = 6 // 3次闪烁 = 6次切换

  // 先居中
  centerOnNode(nodeId)

  const interval = setInterval(() => {
    if (!chartInstance || count >= maxBlinks) {
      clearInterval(interval)
      if (chartInstance && count >= maxBlinks) {
        chartInstance.dispatchAction({ type: 'downplay', seriesIndex: 0, name: node.label })
      }
      return
    }
    if (count % 2 === 0) {
      chartInstance.dispatchAction({ type: 'highlight', seriesIndex: 0, name: node.label })
    } else {
      chartInstance.dispatchAction({ type: 'downplay', seriesIndex: 0, name: node.label })
    }
    count++
  }, 350)
}

function centerOnNode(nodeId: string) {
  if (!chartInstance) return
  const node = allNodes.value.find(n => n.id === nodeId)
  if (!node) return

  // 通过 setOption 定位到节点
  chartInstance.setOption({
    series: [{
      center: [nodeId],
    }],
  })
}

function jumpToEntity(nodeId: string) {
  clearSearch()
  centerOnNode(nodeId)
  handleNodeClick(nodeId)
  blinkNode(nodeId)
}

function jumpToRelatedEntity(rel: { otherId: string; otherType: string }) {
  clearSearch()
  centerOnNode(rel.otherId)
  handleNodeClick(rel.otherId)
  blinkNode(rel.otherId)
}

// ==================== 收藏 & 跳转 ====================

function toggleFavorite() {
  if (!selectedNode.value) return
  const id = selectedNode.value.id
  if (favorites.value.has(id)) {
    favorites.value.delete(id)
    ElMessage.success('已取消收藏')
  } else {
    favorites.value.add(id)
    ElMessage.success('已收藏节点')
  }
  localStorage.setItem('graph_favorites', JSON.stringify(Array.from(favorites.value)))
}

function goToAdminDetail() {
  if (!selectedNode.value) return
  const type = selectedNode.value.type
  const id = selectedNode.value.id as string
  const routeMap: Record<string, string> = {
    '药材': `/admin/herbs`,
    '方剂': `/admin/prescriptions`,
    '症状': `/admin/symptoms`,
    '证候': `/admin/syndromes`,
  }
  const path = routeMap[type] || '/admin/herbs'
  router.push(path)
}

// ==================== 生命周期 ====================

onMounted(() => {
  loadGraphData()
  window.addEventListener('resize', resizeChart)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

// 数据变化时重新渲染
watch([filteredNodes, filteredEdges], () => {
  if (chartInstance) {
    const hasPath = activePath.value.nodes.length > 0
    renderChart(hasPath ? activePath.value : undefined)
  }
}, { deep: true })
</script>

<style scoped lang="scss">
// ==================== 变量 ====================
$bg-dark: #0a1628;
$bg-mid: #111d32;
$card-bg: #ffffff;
$card-radius: 12px;
$panel-width: 20%;
$center-width: 60%;
$text-muted: #94a3b8;
$text-dark: #1e293b;
$indigo: #6366f1;
$emerald: #10b981;
$amber: #f59e0b;
$rose: #b91c1c;

// ==================== 主容器 ====================
.graph-browse {
  display: flex;
  height: calc(100vh - 64px - 60px); // 减去 header 和 footer
  min-height: 700px;
  max-width: 1600px;
  margin: 0 auto;
  background: $bg-dark;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5);
}

// ==================== 左侧面板 ====================
.left-panel {
  width: $panel-width;
  min-width: 260px;
  max-width: 320px;
  background: #f8fafc;
  border-right: 1px solid rgba(148, 163, 184, 0.2);
  display: flex;
  flex-direction: column;
  z-index: 10;

  .panel-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 16px 12px;
    display: flex;
    flex-direction: column;
    gap: 12px;

    &::-webkit-scrollbar {
      width: 4px;
    }
    &::-webkit-scrollbar-thumb {
      background: #cbd5e1;
      border-radius: 4px;
    }
  }
}

.panel-card {
  background: $card-bg;
  border-radius: $card-radius;
  padding: 16px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.06);

  .card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 600;
    color: $text-dark;
    margin-bottom: 12px;

    .el-icon {
      color: $indigo;
    }
  }
}

// 搜索
.search-box {
  display: flex;
  gap: 8px;

  :deep(.el-input) {
    flex: 1;
  }

  .search-icon {
    cursor: pointer;
    color: $indigo;

    &:hover {
      color: darken($indigo, 10%);
    }
  }

  .search-btn {
    flex-shrink: 0;
    background: linear-gradient(135deg, $indigo, #4f46e5);
    border: none;

    &:hover {
      background: linear-gradient(135deg, #4f46e5, #4338ca);
    }
  }
}

// 筛选
.filter-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: opacity 0.3s;

  &.unchecked {
    opacity: 0.45;
  }

  .filter-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
    box-shadow: 0 0 6px currentColor;
  }

  .filter-label {
    font-size: 13px;
    color: $text-dark;
  }
}

// 概览统计
.stats-overview {
  .stats-count {
    text-align: center;
    padding: 8px 0 14px;
    font-size: 14px;

    .count-num {
      font-size: 22px;
      font-weight: 700;
      color: $indigo;
    }
    .count-unit {
      color: $text-muted;
      font-size: 12px;
      margin: 0 2px;
    }
    .count-divider {
      margin: 0 8px;
      color: #cbd5e1;
    }
  }

  .legend-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;

    .legend-item {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: #475569;

      .legend-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        flex-shrink: 0;
      }
    }
  }
}

// 路径查询
.path-query {
  display: flex;
  flex-direction: column;
  gap: 10px;

  .path-arrow {
    text-align: center;
    font-size: 20px;
    color: $text-muted;
    line-height: 1;
  }

  .path-btn {
    width: 100%;
    background: linear-gradient(135deg, $emerald, #059669);
    border: none;

    &:hover {
      background: linear-gradient(135deg, #059669, #047857);
    }
  }

  .entity-option {
    display: flex;
    align-items: center;
    gap: 8px;

    .option-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
    }

    .option-type {
      margin-left: auto;
      font-size: 11px;
      color: $text-muted;
    }
  }
}

// 热门实体
.hot-entities {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;

  .hot-tag {
    padding: 4px 12px;
    border: 1px solid;
    border-radius: 20px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.25s;
    background: rgba(255, 255, 255, 0.8);

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
      filter: brightness(1.1);
    }
  }
}

// ==================== 中央画布 ====================
.center-canvas {
  width: $center-width;
  flex: 1;
  position: relative;
  background: linear-gradient(135deg, $bg-dark 0%, #1a2a3a 50%, #0f2335 100%);
  overflow: hidden;

  .starfield-bg {
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    // CSS 星空背景
    background-image:
      radial-gradient(1px 1px at 10% 15%, rgba(255,255,255,0.6), transparent),
      radial-gradient(1px 1px at 25% 35%, rgba(255,255,255,0.5), transparent),
      radial-gradient(1.5px 1.5px at 40% 10%, rgba(255,255,255,0.7), transparent),
      radial-gradient(1px 1px at 55% 45%, rgba(255,255,255,0.4), transparent),
      radial-gradient(1.5px 1.5px at 70% 20%, rgba(255,255,255,0.6), transparent),
      radial-gradient(1px 1px at 85% 55%, rgba(255,255,255,0.5), transparent),
      radial-gradient(1px 1px at 15% 70%, rgba(255,255,255,0.5), transparent),
      radial-gradient(1.5px 1.5px at 35% 80%, rgba(255,255,255,0.6), transparent),
      radial-gradient(1px 1px at 50% 65%, rgba(255,255,255,0.4), transparent),
      radial-gradient(1px 1px at 65% 75%, rgba(255,255,255,0.5), transparent),
      radial-gradient(1.5px 1.5px at 80% 85%, rgba(255,255,255,0.6), transparent),
      radial-gradient(1px 1px at 90% 35%, rgba(255,255,255,0.5), transparent),
      radial-gradient(1px 1px at 20% 90%, rgba(255,255,255,0.4), transparent),
      radial-gradient(1.5px 1.5px at 60% 55%, rgba(255,255,255,0.5), transparent),
      radial-gradient(1px 1px at 95% 5%, rgba(255,255,255,0.6), transparent),
      radial-gradient(1px 1px at 5% 50%, rgba(255,255,255,0.4), transparent),
      radial-gradient(1.5px 1.5px at 45% 90%, rgba(255,255,255,0.5), transparent),
      radial-gradient(1px 1px at 75% 40%, rgba(255,255,255,0.4), transparent);
    background-size: 100% 100%;
    animation: starTwinkle 4s ease-in-out infinite alternate;
  }

  .chart-container {
    position: absolute;
    inset: 0;
    z-index: 1;
  }

  .empty-state,
  .loading-state {
    position: absolute;
    inset: 0;
    z-index: 5;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(10, 22, 40, 0.85);
    backdrop-filter: blur(4px);
  }

  .loading-state {
    flex-direction: column;
    gap: 16px;
    color: $text-muted;

    .loading-icon {
      font-size: 40px;
      animation: spin 1.2s linear infinite;
      color: $indigo;
    }

    p {
      font-size: 15px;
    }
  }

  // 定位标签
  .location-tag {
    position: absolute;
    top: 16px;
    left: 16px;
    z-index: 10;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    background: rgba(15, 23, 42, 0.9);
    border: 1px solid rgba(251, 191, 36, 0.5);
    border-radius: 20px;
    color: #fbbf24;
    font-size: 14px;
    font-weight: 500;
    backdrop-filter: blur(8px);
    pointer-events: none;
  }

  // 工具栏
  .canvas-toolbar {
    position: absolute;
    top: 16px;
    right: 16px;
    z-index: 10;
    display: flex;
    flex-direction: column;
    gap: 6px;

    .tool-btn {
      width: 38px;
      height: 38px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid rgba(148, 163, 184, 0.3);
      border-radius: 8px;
      color: #e2e8f0;
      cursor: pointer;
      transition: all 0.2s;
      backdrop-filter: blur(8px);
      font-size: 16px;

      &:hover:not(:disabled) {
        background: rgba(99, 102, 241, 0.3);
        border-color: $indigo;
        color: #fff;
      }

      &:disabled {
        opacity: 0.35;
        cursor: not-allowed;
      }
    }
  }
}

// ==================== 右侧详情面板 ====================
.right-panel {
  width: $panel-width;
  min-width: 260px;
  max-width: 320px;
  background: #f8fafc;
  border-left: 1px solid rgba(148, 163, 184, 0.2);
  z-index: 10;
  position: relative;
  overflow: hidden;

  .detail-scroll {
    height: 100%;
    overflow-y: auto;
    padding: 20px 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;

    &::-webkit-scrollbar {
      width: 4px;
    }
    &::-webkit-scrollbar-thumb {
      background: #cbd5e1;
      border-radius: 4px;
    }
  }

  .close-btn {
    position: absolute;
    top: 12px;
    right: 12px;
    width: 32px;
    height: 32px;
    border: none;
    background: #f1f5f9;
    border-radius: 50%;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #64748b;
    z-index: 2;
    transition: all 0.2s;

    &:hover {
      background: #e2e8f0;
      color: #1e293b;
    }
  }

  .detail-header {
    text-align: center;
    padding-bottom: 12px;
    border-bottom: 1px solid #e2e8f0;

    .detail-name {
      margin: 0 0 10px 0;
      font-size: 22px;
      color: $text-dark;
      font-weight: 700;
    }

    .detail-type-tag {
      display: inline-block;
      padding: 4px 16px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 500;
    }
  }

  .detail-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 40px 0;
    color: $text-muted;

    .loading-icon {
      font-size: 30px;
      animation: spin 1.2s linear infinite;
    }
  }

  .detail-section {
    .section-label {
      font-size: 14px;
      font-weight: 600;
      color: $text-dark;
      margin: 0 0 10px 0;
    }
  }

  .property-list {
    background: #fff;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);

    .property-row {
      display: flex;
      padding: 10px 14px;
      border-bottom: 1px solid #f1f5f9;

      &:last-child {
        border-bottom: none;
      }

      .prop-label {
        width: 80px;
        flex-shrink: 0;
        font-size: 12px;
        color: $text-muted;
        font-weight: 500;
      }

      .prop-value {
        flex: 1;
        font-size: 13px;
        color: $text-dark;
        line-height: 1.5;
      }
    }
  }

  .relation-list {
    display: flex;
    flex-direction: column;
    gap: 6px;

    .relation-item {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 8px 10px;
      background: #fff;
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.2s;
      font-size: 12px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);

      &:hover {
        transform: translateX(4px);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        background: #f0f9ff;
      }

      .rel-source,
      .rel-target {
        color: $text-dark;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 4px;
      }

      .rel-type-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        flex-shrink: 0;
      }

      .rel-arrow {
        color: #cbd5e1;
        font-size: 10px;
      }

      .rel-label-tag {
        padding: 2px 8px;
        background: #fef3c7;
        color: #b45309;
        border-radius: 10px;
        font-size: 11px;
        font-weight: 500;
        white-space: nowrap;
      }
    }
  }

  .detail-actions {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: auto;
    padding-top: 12px;
    border-top: 1px solid #e2e8f0;

    .el-button {
      width: 100%;
    }
  }
}

.no-data {
  text-align: center;
  color: $text-muted;
  font-size: 13px;
  padding: 16px 0;
}

// ==================== 过渡动画 ====================
.slide-right-enter-active,
.slide-right-leave-active {
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-right-enter-from {
  transform: translateX(100%);
  opacity: 0;
}

.slide-right-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

// ==================== 动画 ====================
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes starTwinkle {
  0% { opacity: 0.7; }
  50% { opacity: 1; }
  100% { opacity: 0.8; }
}

// ==================== 响应式 ====================
@media (max-width: 1200px) {
  .graph-browse {
    flex-wrap: wrap;
    height: auto;
    min-height: 100vh;

    .left-panel {
      width: 100%;
      max-width: 100%;
      min-width: 0;
      max-height: 400px;
      border-right: none;
      border-bottom: 1px solid rgba(148, 163, 184, 0.2);
    }

    .center-canvas {
      width: 100%;
      min-height: 500px;
      order: 1;
    }

    .right-panel {
      width: 100%;
      max-width: 100%;
      min-width: 0;
      max-height: 50vh;
      border-left: none;
      border-top: 1px solid rgba(148, 163, 184, 0.2);
      order: 2;
    }
  }
}

@media (max-width: 768px) {
  .graph-browse {
    .left-panel {
      max-height: 350px;

      .panel-scroll {
        padding: 10px 8px;
        gap: 8px;
      }
    }

    .panel-card {
      padding: 12px;

      .card-header {
        font-size: 13px;
        margin-bottom: 8px;
      }
    }

    .center-canvas {
      min-height: 400px;
    }

    .canvas-toolbar {
      top: 8px;
      right: 8px;
      gap: 4px;

      .tool-btn {
        width: 32px;
        height: 32px;
        font-size: 14px;
      }
    }
  }
}

.graph-browse {
  margin-top: -800px;
  
  @media (max-width: 1200px) {
    margin-top: -1020px;
  }
}
</style>
