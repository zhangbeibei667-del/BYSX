<template>
  <div class="case-study">
    <!-- ==================== 主体：左右两栏 ==================== -->
    <div class="case-main">
      <!-- ========== 左侧：病例录入区（50%） ========== -->
      <section class="left-panel">
        <div class="panel-card">
          <!-- 顶部标题栏 -->
          <div class="panel-header">
            <h2 class="panel-title">
              <el-icon><Notebook /></el-icon>
              <span>病例教学</span>
            </h2>
            <div class="header-actions">
              <el-button class="tcm-btn primary-tcm" @click="handleSaveCase" :loading="saving">
                <el-icon><FolderChecked /></el-icon>
                保存病例
              </el-button>
              <el-button plain class="tcm-btn ghost-tcm" @click="showHistory = !showHistory">
                <el-icon><Clock /></el-icon>
                历史病例
              </el-button>
            </div>
          </div>

          <!-- 表单内容 -->
          <div class="form-body">
            <!-- 患者信息区（三列网格） -->
            <div class="form-section">
              <h3 class="section-label">👤 患者信息</h3>
              <div class="info-grid">
                <div class="form-item">
                  <label>姓名</label>
                  <el-input
                    v-model="form.name"
                    placeholder="请输入"
                    clearable
                  />
                </div>
                <div class="form-item">
                  <label>年龄</label>
                  <el-input
                    v-model.number="form.age"
                    placeholder="岁"
                    type="number"
                    :min="0"
                    :max="150"
                  >
                    <template #suffix><span class="input-suffix">岁</span></template>
                  </el-input>
                </div>
                <div class="form-item">
                  <label>性别</label>
                  <el-select v-model="form.gender" placeholder="请选择" style="width: 100%">
                    <el-option label="男" value="男" />
                    <el-option label="女" value="女" />
                  </el-select>
                </div>
              </div>
            </div>

            <!-- 主诉与症状区 -->
            <div class="form-section">
              <h3 class="section-label">📝 主诉与症状</h3>
              <div class="symptom-textarea-wrapper">
                <el-input
                  v-model="form.chiefComplaint"
                  type="textarea"
                  :rows="8"
                  placeholder="请描述患者的主要症状，例如：&#10;· 失眠多梦、心悸健忘&#10;· 食少乏力、面色萎黄&#10;· 头晕目眩、耳鸣"
                  resize="none"
                  :maxlength="2000"
                  show-word-limit
                />
                <span class="char-count">{{ form.chiefComplaint.length }} / 2000</span>
              </div>
            </div>

            <!-- 舌脉体征区（两列网格） -->
            <div class="form-section">
              <h3 class="section-label">👅 舌脉体征</h3>
              <div class="info-grid two-col">
                <div class="form-item">
                  <label>舌象</label>
                  <el-input
                    v-model="form.tongueExam"
                    placeholder="如：舌淡苔白"
                    clearable
                  />
                </div>
                <div class="form-item">
                  <label>脉象</label>
                  <el-input
                    v-model="form.pulseExam"
                    placeholder="如：脉细弱"
                    clearable
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- 底部操作行 -->
          <div class="form-actions">
            <el-button
              class="tcm-btn analyze-btn"
              size="large"
              @click="handleAnalyze"
              :loading="analyzing"
              :disabled="!canAnalyze"
            >
              <el-icon v-if="!analyzing"><Search /></el-icon>
              🔍 智能分析
            </el-button>
            <el-button text type="info" size="large" @click="handleClearForm">
              清空
            </el-button>
          </div>
        </div>
      </section>

      <!-- ========== 右侧：分析结果区（50%） ========== -->
      <section class="right-panel">
        <div class="panel-card">
          <!-- 小型关联图谱 -->
          <div class="analysis-block">
            <h3 class="block-title">🔬 辨证论治图谱</h3>
            <div class="mini-graph-wrapper" ref="miniGraphContainer">
              <div v-if="!analysisResult" class="graph-placeholder">
                <el-icon><DataAnalysis /></el-icon>
                <p>录入症状后点击分析，将自动生成关联图谱</p>
              </div>
              <div v-else ref="miniChartRef" class="mini-chart"></div>
            </div>
          </div>

          <!-- 证候诊断卡片 -->
          <transition name="fade-up">
            <div v-if="analysisResult" class="diagnosis-card syndrome-card">
              <h3 class="block-title">🏥 证候诊断</h3>
              <div class="syndrome-tags">
                <span
                  v-for="s in analysisResult.syndromes"
                  :key="s"
                  class="syndrome-tag"
                  @click="goToGraphPage(s)"
                >
                  {{ s }}
                </span>
                <span v-if="analysisResult.syndromes.length === 0" class="no-result">
                  未匹配到对应证候
                </span>
              </div>
              <p class="diagnosis-basis">{{ analysisResult.answer }}</p>
            </div>
          </transition>

          <!-- 推荐方剂卡片 -->
          <transition name="fade-up">
            <div v-if="analysisResult" class="diagnosis-card formula-card">
              <h3 class="block-title">💊 推荐方剂</h3>
              <div class="formula-header">
                <span
                  v-for="f in analysisResult.formulas"
                  :key="f"
                  class="formula-tag"
                  @click="goToGraphPage(f)"
                >
                  {{ f }}
                </span>
                <span v-if="analysisResult.formulas.length === 0" class="no-result">
                  未匹配到对应方剂
                </span>
              </div>
              <div class="herb-list">
                <span class="herb-label">核心药材：</span>
                <span
                  v-for="(h, i) in analysisResult.herbs"
                  :key="h"
                  class="herb-tag"
                  @click="goToGraphPage(h)"
                >
                  {{ h }}<span v-if="i < analysisResult.herbs.length - 1" class="herb-sep"> · </span>
                </span>
                <span v-if="analysisResult.herbs.length === 0" class="no-result">
                  暂无药材信息
                </span>
              </div>
              <div v-if="analysisResult.evidence.length > 0" class="evidence-list">
                <div
                  v-for="ev in analysisResult.evidence"
                  :key="ev.title"
                  class="evidence-item"
                >
                  <span class="evidence-title">{{ ev.title }}：</span>
                  <span class="evidence-content">{{ ev.content }}</span>
                </div>
              </div>
            </div>
          </transition>

          <!-- 教学笔记区 -->
          <div class="analysis-block">
            <h3 class="block-title">📒 教学笔记</h3>
            <el-input
              v-model="teachingNote"
              type="textarea"
              :rows="4"
              placeholder="记录教学要点、辨证思路或学生提问..."
              class="note-textarea"
              resize="none"
            />
          </div>
        </div>
      </section>
    </div>

    <!-- ==================== 底部：历史病例（横向滚动） ==================== -->
    <transition name="fade-up">
      <div v-if="showHistory" class="case-history">
        <div class="history-header">
          <h3>📚 历史病例</h3>
          <el-button text class="tcm-btn ghost-tcm" @click="loadHistoryCases" :loading="historyLoading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>

        <div v-if="historyCases.length > 0" class="history-scroll">
          <div
            v-for="c in historyCases"
            :key="c.id"
            class="history-card"
            :class="{ active: currentCaseId === c.id }"
            @click="loadCaseFromHistory(c.id)"
          >
            <div class="hc-header">
              <span class="hc-id">{{ c.id?.slice(0, 8) || '--' }}</span>
              <span class="hc-date">{{ formatDate(c.createdAt || c.date) }}</span>
            </div>
            <div class="hc-body">
              <div class="hc-item">
                <span class="hc-label">主诉</span>
                <span class="hc-value">{{ truncate(c.chiefComplaint || c.symptoms, 30) }}</span>
              </div>
              <div class="hc-item">
                <span class="hc-label">证候</span>
                <span class="hc-value syndrome-name">
                  {{ (c.syndromes || []).join('、') || '待分析' }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="!historyLoading" class="history-empty">
          <el-empty description="暂无历史病例" :image-size="80" />
        </div>

        <div v-if="historyLoading" class="history-loading">
          <el-icon class="loading-icon"><Loading /></el-icon>
          <span>加载中...</span>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Notebook, FolderChecked, Clock, Search,
  DataAnalysis, Refresh, Loading
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { caseApi } from '@/api'
import type { GraphResponse, AnswerResponse } from '@/types'

const router = useRouter()

// ==================== 表单数据 ====================
const form = reactive({
  name: '',
  age: null as number | null,
  gender: '' as string,
  chiefComplaint: '',
  tongueExam: '',
  pulseExam: '',
})

// ==================== 状态 ====================
const analyzing = ref(false)
const saving = ref(false)
const analysisResult = ref<AnswerResponse | null>(null)
const teachingNote = ref('')

// 历史病例
const showHistory = ref(false)
const historyCases = ref<any[]>([])
const historyLoading = ref(false)
const currentCaseId = ref<string | null>(null)

// 迷你图谱
const miniChartRef = ref<HTMLDivElement>()
const miniGraphContainer = ref<HTMLElement>()
let miniChartInstance: echarts.ECharts | null = null

// ==================== 计算属性 ====================
const canAnalyze = computed(() => {
  return form.chiefComplaint.trim().length > 0
})

// ==================== 图谱颜色常量（国风色系） ====================
const TYPE_COLORS: Record<string, string> = {
  '药材': '#588264',
  '方剂': '#8c6e4a',
  '症状': '#c8a86e',
  '证候': '#b13e3e',
  '功效': '#5a8c7a',
  '禁忌': '#b13e3e',
  '文献': '#7a6a8a',
}

// ==================== API 调用 ====================

async function handleAnalyze() {
  if (!canAnalyze.value) {
    ElMessage.warning('请至少填写主诉与症状')
    return
  }

  analyzing.value = true
  analysisResult.value = null

  try {
    // 先创建/保存病例
    const caseData = buildCaseData()
    let caseId = currentCaseId.value

    const createRes: any = await caseApi.create(caseData)
    if (createRes?.data?.id) {
      caseId = createRes.data.id
    } else if (createRes?.id) {
      caseId = createRes.id
    } else if (typeof createRes === 'string') {
      caseId = createRes
    }
    if (!caseId) throw new Error('后端未返回病例编号')
    currentCaseId.value = caseId

    // 分析病例
    const analyzeRes: any = await caseApi.analyze(caseId)
    if (analyzeRes?.data?.answer) {
      analysisResult.value = analyzeRes.data
    } else if (analyzeRes?.answer) {
      analysisResult.value = analyzeRes
    } else {
      throw new Error('病例分析接口未返回有效结果')
    }

    // 渲染迷你图谱
    await nextTick()
    renderMiniGraph()
  } catch (err) {
    console.error('分析失败:', err)
    analysisResult.value = null
    ElMessage.error(err instanceof Error ? err.message : '分析失败，请检查后端服务后重试')
  } finally {
    analyzing.value = false
  }
}

function buildCaseData() {
  return {
    name: form.name || '未命名',
    age: form.age,
    gender: form.gender || '未指定',
    chiefComplaint: form.chiefComplaint,
    tongueExam: form.tongueExam,
    pulseExam: form.pulseExam,
  }
}

// ==================== 迷你图谱渲染 ====================

function renderMiniGraph() {
  if (!miniChartRef.value) return
  if (!analysisResult.value || analysisResult.value.graph.nodes.length === 0) return

  if (miniChartInstance) {
    miniChartInstance.dispose()
  }

  miniChartInstance = echarts.init(miniChartRef.value)

  const { nodes, edges } = analysisResult.value.graph

  const chartNodes = nodes.map(n => {
    const color = TYPE_COLORS[n.type] || '#94a3b8'
    return {
      id: n.id,
      name: n.label,
      symbol: n.type === '方剂' ? 'diamond' as const : 'circle' as const,
      symbolSize: n.type === '证候' ? 28 : (n.type === '方剂' ? 26 : 22),
      category: n.type,
      _rawType: n.type,
      _rawId: n.id,
      itemStyle: {
        color,
        borderColor: 'rgba(255,255,255,0.4)',
        borderWidth: 0.5,
        shadowColor: color,
        shadowBlur: 10,
      },
      label: {
        show: true,
        color: '#4a5a4a',
        fontSize: 10,
        position: 'bottom' as const,
        distance: 4,
      },
    }
  })

  const chartEdges = edges.map(e => ({
    source: e.source,
    target: e.target,
    name: e.label,
    lineStyle: {
      color: 'rgba(120,140,120,0.4)',
      width: 1.2,
      curveness: 0.15,
    },
    label: {
      show: false,
    },
  }))

  miniChartInstance.setOption({
    backgroundColor: 'transparent',
    animationDuration: 1000,
    animationEasing: 'cubicInOut' as const,
    tooltip: {
      show: true,
      backgroundColor: 'rgba(247,243,235,0.95)',
      borderColor: 'rgba(200,168,110,0.4)',
      textStyle: { color: '#2a4030', fontSize: 12 },
      formatter: (params: any) => {
        if (params.dataType === 'edge') {
          return `<span style="color:#6b7a72">${params.data.sourceLabel || ''}</span>
                  <span style="color:#c8a86e"> → ${params.data.name}</span>`
        }
        return `<b>${params.data.name}</b>`
      },
    },
    series: [{
      type: 'graph',
      layout: 'force',
      roam: false,
      draggable: false,
      zoom: 0.9,
      center: ['50%', '50%'],
      force: {
        initIterations: 200,
        repulsion: 200,
        gravity: 0.08,
        edgeLength: [80, 150],
        layoutAnimation: true,
      },
      data: chartNodes,
      edges: chartEdges,
      categories: Object.entries(TYPE_COLORS).map(([name, color]) => ({
        name,
        itemStyle: { color },
      })),
      emphasis: {
        focus: 'adjacency' as const,
        itemStyle: {
          shadowBlur: 20,
        },
        label: {
          fontSize: 12,
          fontWeight: 'bold',
          color: '#2a4030',
        },
      },
    }],
  })

  miniChartInstance.off('click')
  miniChartInstance.on('click', (params: any) => {
    if (params.dataType === 'node') {
      router.push('/graph')
    }
  })
}

function disposeMiniChart() {
  if (miniChartInstance) {
    miniChartInstance.dispose()
    miniChartInstance = null
  }
}

// ==================== 病例保存 ====================

async function handleSaveCase() {
  if (!canAnalyze.value && !form.name) {
    ElMessage.warning('请至少填写主诉与症状')
    return
  }

  saving.value = true
  try {
    const caseData = {
      ...buildCaseData(),
      teachingNote: teachingNote.value,
      analysisResult: analysisResult.value,
    }

    const res: any = await caseApi.create(caseData)
    let caseId: string | null = null
    if (res?.data?.id) caseId = res.data.id
    else if (res?.id) caseId = res.id
    else if (typeof res === 'string') caseId = res

    currentCaseId.value = caseId || currentCaseId.value
    ElMessage.success('✅ 病例已保存')
  } catch {
    ElMessage.error('病例服务不可用，未保存本次病例')
  } finally {
    saving.value = false
  }
}

// ==================== 历史病例 ====================

async function loadHistoryCases() {
  historyLoading.value = true
  try {
    const res: any = await caseApi.list({ page: 1, pageSize: 20 })
    if (res?.data?.length > 0) {
      historyCases.value = res.data
    } else if (Array.isArray(res)) {
      historyCases.value = res
    } else {
      loadLocalCases()
    }
  } catch {
    loadLocalCases()
  } finally {
    historyLoading.value = false
  }
}

function loadLocalCases() {
  historyCases.value = JSON.parse(localStorage.getItem('tcm_cases') || '[]')
}

async function loadCaseFromHistory(caseId: string) {
  historyLoading.value = true
  try {
    const res: any = await caseApi.detail(caseId)
    const detail = res?.data || res || {}

    form.name = detail.name || ''
    form.age = detail.age || null
    form.gender = detail.gender || ''
    form.chiefComplaint = detail.chiefComplaint || detail.symptoms || ''
    form.tongueExam = detail.tongueExam || ''
    form.pulseExam = detail.pulseExam || ''
    teachingNote.value = detail.teachingNote || ''
    currentCaseId.value = caseId

    if (detail.analysisResult) {
      analysisResult.value = detail.analysisResult
      await nextTick()
      renderMiniGraph()
    } else if (detail.syndromes?.length > 0) {
      analysisResult.value = {
        answer: detail.answer || '',
        symptoms: [],
        syndromes: detail.syndromes || [],
        formulas: detail.formulas || [],
        herbs: detail.herbs || [],
        graph: detail.graph || { nodes: [], edges: [] },
        evidence: detail.evidence || [],
        follow_up_questions: [],
        safety_notice: '',
      }
      await nextTick()
      renderMiniGraph()
    }

    ElMessage.success('病例已加载')
  } catch {
    ElMessage.error('加载病例失败')
  } finally {
    historyLoading.value = false
  }
}

// ==================== 清空 ====================

function handleClearForm() {
  ElMessageBox.confirm('确定清空当前表单吗？未保存的内容将丢失。', '确认操作', {
    confirmButtonText: '确定清空',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(() => {
    form.name = ''
    form.age = null
    form.gender = ''
    form.chiefComplaint = ''
    form.tongueExam = ''
    form.pulseExam = ''
    teachingNote.value = ''
    analysisResult.value = null
    currentCaseId.value = null
    disposeMiniChart()
    ElMessage.info('表单已清空')
  }).catch(() => {})
}

// ==================== 跳转 ====================

function goToGraphPage(keyword?: string) {
  router.push(keyword ? `/graph?search=${encodeURIComponent(keyword)}` : '/graph')
}

// ==================== 工具函数 ====================

function formatDate(dateStr: string): string {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return dateStr.slice(0, 10)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function truncate(text: string, maxLen: number): string {
  if (!text) return '--'
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text
}

// ==================== 监听 ====================

watch(() => analysisResult.value, async (newVal) => {
  if (newVal?.graph?.nodes?.length) {
    await nextTick()
    renderMiniGraph()
  }
})

watch(showHistory, (val) => {
  if (val && historyCases.value.length === 0) {
    loadHistoryCases()
  }
})

// ==================== 生命周期 ====================

onMounted(() => {
  loadLocalCases()
})

onBeforeUnmount(() => {
  disposeMiniChart()
  window.removeEventListener('resize', disposeMiniChart)
})
</script>

<style scoped lang="scss">
// ==================== 国风变量 ====================
$dark-green: #2a4030;
$mid-green: #466350;
$soft-gold: #c8a86e;
$cream-bg: #f7f3eb;
$light-cream: #faf6ef;
$text-dark: #2c3630;
$text-light: #6b7a72;
$card-shadow: 0 2px 16px rgba(42, 64, 48, 0.08);
$card-border: rgba(110, 135, 120, 0.12);
$white: #ffffff;

$syndrome-red: #b13e3e;
$formula-brown: #8c6e4a;
$herb-green: #588264;

// ==================== 主容器 ====================
.case-study {
  margin: 0 auto;
  padding: 16px 32px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background-color: $cream-bg;
}

// ==================== 两栏主体 ====================
.case-main {
  display: flex;
  gap: 20px;
  min-height: calc(100vh - 64px - 220px);
}

// ==================== 面板通用 ====================
.panel-card {
  background: $white;
  border-radius: 14px;
  box-shadow: $card-shadow;
  padding: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

// ==================== 左侧面板 ====================
.left-panel {
  width: 50%;

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid $card-border;

    .panel-title {
      display: flex;
      align-items: center;
      gap: 10px;
      margin: 0;
      font-size: 20px;
      color: $dark-green;

      .el-icon {
        color: $mid-green;
        font-size: 22px;
      }
    }

    .header-actions {
      display: flex;
      gap: 10px;
    }
  }

  .form-body {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 20px;

    &::-webkit-scrollbar {
      width: 4px;
    }
    &::-webkit-scrollbar-thumb {
      background: rgba(110, 135, 120, 0.25);
      border-radius: 4px;
    }
  }
}

// 国风按钮
.tcm-btn {
  border-radius: 8px;
  border: 1px solid transparent;
  padding: 10px 22px;
  font-size: 15px;
  transition: all 0.3s ease;

  &.primary-tcm {
    background: rgba(70, 99, 80, 0.08);
    color: $dark-green;
    border-color: rgba(70, 99, 80, 0.2);
    &:hover { background: $mid-green; color: #fff; }
  }

  &.ghost-tcm {
    color: $text-light;
    border-color: $card-border;
    background: transparent;
    &:hover { background: $cream-bg; border-color: $mid-green; }
  }

  &.analyze-btn {
    background: $mid-green;
    color: #fff;
    border: none;
    padding: 12px 32px;
    font-size: 16px;
    font-weight: 600;
    border-radius: 10px;

    &:hover:not(:disabled) {
      background: $dark-green;
      transform: translateY(-1px);
      box-shadow: 0 6px 20px rgba(70, 99, 80, 0.35);
    }

    &:disabled {
      background: rgba(110, 135, 120, 0.3);
      cursor: not-allowed;
    }
  }
}

// 表单区块
.form-section {
  .section-label {
    font-size: 14px;
    font-weight: 600;
    color: $dark-green;
    margin: 0 0 12px 0;
  }
}

// 患者信息三列网格
.info-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;

  &.two-col {
    grid-template-columns: repeat(2, 1fr);
  }
}

.form-item {
  label {
    display: block;
    font-size: 13px;
    color: $text-light;
    margin-bottom: 6px;
    font-weight: 500;
  }

  :deep(.el-input__wrapper) {
    border-radius: 8px;
    border-color: $card-border;
    box-shadow: none;
    &:hover { border-color: $mid-green; }
    &.is-focus { border-color: $mid-green; box-shadow: 0 0 0 2px rgba(70, 99, 80, 0.12); }
  }

  :deep(.el-select) {
    .el-input__wrapper {
      border-radius: 8px;
    }
  }

  .input-suffix {
    color: $text-light;
    font-size: 13px;
  }
}

// 症状输入区
.symptom-textarea-wrapper {
  position: relative;

  :deep(.el-textarea__inner) {
    line-height: 1.7;
    font-size: 14px;
    border-radius: 8px;
    border-color: $card-border;
    &:focus { border-color: $mid-green; box-shadow: 0 0 0 2px rgba(70, 99, 80, 0.12); }
  }

  .char-count {
    position: absolute;
    bottom: 8px;
    right: 14px;
    font-size: 11px;
    color: $text-light;
    pointer-events: none;
    background: rgba(255, 255, 255, 0.8);
    padding: 2px 6px;
    border-radius: 4px;
  }
}

// 表单底部操作
.form-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-top: 20px;
  border-top: 1px solid $card-border;
  margin-top: auto;
}

// ==================== 右侧面板 ====================
.right-panel {
  width: 50%;

  .panel-card {
    gap: 16px;
  }
}

.analysis-block {
  .block-title {
    font-size: 15px;
    font-weight: 600;
    color: $dark-green;
    margin: 0 0 12px 0;
  }
}

// 迷你图谱 - 国风浅色背景
.mini-graph-wrapper {
  background: $light-cream;
  border: 1px solid $card-border;
  border-radius: 10px;
  min-height: 200px;
  position: relative;
  overflow: hidden;

  .mini-chart {
    width: 100%;
    height: 200px;
  }

  .graph-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 200px;
    color: $text-light;
    gap: 12px;

    .el-icon {
      font-size: 36px;
      opacity: 0.4;
      color: $mid-green;
    }

    p {
      margin: 0;
      font-size: 13px;
      text-align: center;
      line-height: 1.6;
      max-width: 280px;
      color: $text-light;
    }
  }
}

// 诊断卡片 - 国风配色
.diagnosis-card {
  padding: 16px;
  border-radius: 12px;
  border: 1px solid $card-border;

  &.syndrome-card {
    background: #fdf6f0;
    border-color: rgba(177, 62, 62, 0.15);

    .syndrome-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 10px;

      .syndrome-tag {
        display: inline-block;
        padding: 8px 20px;
        background: $syndrome-red;
        color: #fff;
        border-radius: 24px;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.25s;

        &:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 16px rgba(177, 62, 62, 0.35);
        }
      }
    }

    .diagnosis-basis {
      margin: 0;
      font-size: 13px;
      color: $text-light;
      line-height: 1.7;
    }
  }

  &.formula-card {
    background: #f8f4ed;
    border-color: rgba(140, 110, 74, 0.15);

    .formula-header {
      margin-bottom: 12px;

      .formula-tag {
        display: inline-block;
        padding: 8px 20px;
        background: $formula-brown;
        color: #fff;
        border-radius: 24px;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.25s;

        &:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 16px rgba(140, 110, 74, 0.35);
        }
      }
    }

    .herb-list {
      margin-bottom: 12px;
      line-height: 1.8;

      .herb-label {
        font-size: 13px;
        color: $text-light;
        font-weight: 500;
      }

      .herb-tag {
        font-size: 14px;
        color: $herb-green;
        font-weight: 500;
        cursor: pointer;
        transition: color 0.2s;

        &:hover {
          color: $dark-green;
          text-decoration: underline;
        }

        .herb-sep {
          color: #cbd5e1;
          cursor: default;
        }
      }
    }

    .evidence-list {
      .evidence-item {
        font-size: 12px;
        line-height: 1.6;
        color: $text-light;

        .evidence-title {
          font-weight: 600;
          color: $dark-green;
        }
      }
    }
  }

  .no-result {
    color: $text-light;
    font-size: 14px;
    font-style: italic;
  }
}

// 教学笔记
.note-textarea {
  :deep(.el-textarea__inner) {
    border-style: dashed;
    border-color: $card-border;
    background: $cream-bg;
    font-size: 14px;
    line-height: 1.7;
    border-radius: 8px;

    &:focus {
      border-color: $mid-green;
      border-style: dashed;
      box-shadow: 0 0 0 2px rgba(70, 99, 80, 0.08);
    }
  }
}

// ==================== 历史病例 ====================
.case-history {
  background: $white;
  border-radius: 14px;
  box-shadow: $card-shadow;
  padding: 20px 24px;

  .history-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;

    h3 {
      margin: 0;
      font-size: 16px;
      color: $dark-green;
    }
  }

  .history-scroll {
    display: flex;
    gap: 14px;
    overflow-x: auto;
    padding-bottom: 8px;

    &::-webkit-scrollbar {
      height: 6px;
    }
    &::-webkit-scrollbar-thumb {
      background: rgba(110, 135, 120, 0.25);
      border-radius: 4px;
    }
  }

  .history-card {
    min-width: 200px;
    max-width: 220px;
    padding: 14px;
    border: 2px solid $card-border;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.25s;
    flex-shrink: 0;
    background: $cream-bg;

    &:hover {
      transform: translateY(-3px);
      box-shadow: 0 6px 18px rgba(42, 64, 48, 0.1);
    }

    &.active {
      border-color: $mid-green;
      box-shadow: 0 0 0 3px rgba(70, 99, 80, 0.15);
      background: #f0f5ed;
    }

    .hc-header {
      display: flex;
      justify-content: space-between;
      margin-bottom: 10px;

      .hc-id {
        font-size: 12px;
        color: $text-light;
        font-family: monospace;
      }

      .hc-date {
        font-size: 11px;
        color: $text-light;
      }
    }

    .hc-body {
      .hc-item {
        margin-bottom: 6px;

        .hc-label {
          display: block;
          font-size: 11px;
          color: $text-light;
          margin-bottom: 2px;
        }

        .hc-value {
          font-size: 13px;
          color: $text-dark;
          line-height: 1.4;
        }

        .syndrome-name {
          color: $syndrome-red;
          font-weight: 500;
        }
      }
    }
  }

  .history-empty,
  .history-loading {
    text-align: center;
    padding: 16px 0;
    color: $text-light;

    .loading-icon {
      font-size: 22px;
      animation: spin 1.2s linear infinite;
    }
  }
}

// ==================== 过渡动画 ====================
.fade-up-enter-active {
  transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

.fade-up-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.fade-up-leave-active {
  transition: all 0.3s ease-in;
}

.fade-up-leave-to {
  opacity: 0;
}

// ==================== 动画 ====================
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

// ==================== Element Plus 样式覆盖 ====================
:deep(.el-empty__description) {
  color: $text-light;
}

:deep(.el-button) {
  --el-button-border-radius: 8px;
}

// ==================== 响应式 ====================
@media (max-width: 1024px) {
  .case-main {
    flex-direction: column;
  }

  .left-panel,
  .right-panel {
    width: 100%;
  }

  .info-grid {
    grid-template-columns: repeat(2, 1fr);

    &.two-col {
      grid-template-columns: 1fr;
    }
  }

  .history-scroll {
    .history-card {
      min-width: 160px;
    }
  }
}

@media (max-width: 640px) {
  .case-study {
    padding: 10px;
  }

  .panel-card {
    padding: 16px;
  }

  .info-grid {
    grid-template-columns: 1fr;
  }

  .panel-header {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }

  .form-actions {
    flex-direction: column;

    .analyze-btn {
      width: 100%;
    }
  }
}

.case-study {
  margin-top: 50px;
  
  @media (max-width: 1200px) {
    margin-top: -1020px;
  }
}
</style>
