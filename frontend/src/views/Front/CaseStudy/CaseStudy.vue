<template>
  <div class="case-study">
    <!-- ==================== 主体：左右两栏 ==================== -->
    <div class="case-main" :class="{ 'has-analysis': analysisResult }">
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
              <el-button plain class="tcm-btn ghost-tcm" @click="toggleHistory" :loading="historyLoading">
                <el-icon><Clock /></el-icon>
                历史病例
              </el-button>
            </div>
          </div>

          <!-- 表单内容 -->
          <div class="form-body">
            <!-- 患者信息区（三列网格） -->
            <div class="form-section">
              <h3 class="section-label">
                <el-icon><User /></el-icon>
                <span>患者信息</span>
              </h3>
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
              <h3 class="section-label">
                <el-icon><EditPen /></el-icon>
                <span>主诉与症状</span>
              </h3>
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
              </div>
            </div>

            <!-- 舌脉体征区（两列网格） -->
            <div class="form-section">
              <h3 class="section-label">
                <el-icon><FirstAidKit /></el-icon>
                <span>舌脉体征</span>
              </h3>
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
              智能分析
            </el-button>
            <el-button text type="info" size="large" @click="handleClearForm">
              清空
            </el-button>
          </div>
        </div>

        <!-- 总控 Agent 放在病例录入与执行流程之间 -->
        <div v-if="analysisResult?.agent_steps?.length" class="orchestrator-card left-orchestrator-card">
          <div class="orchestrator-heading">
            <div>
              <span class="orchestrator-kicker">TASK 4 · 诊疗教学多 AGENT</span>
              <h3>诊疗教学总控 Agent</h3>
              <p>{{ analysisResult.agent_plan?.reason || '根据病例意图动态选择并调用中医药教学工具' }}</p>
            </div>
            <span class="run-status"><i></i> 执行完成</span>
          </div>
          <div class="orchestrator-meta">
            <span>识别意图<strong>{{ formatIntent(analysisResult.agent_plan?.intent) }}</strong></span>
            <span>规划方式<strong>{{ formatPlanner(analysisResult.agent_plan?.planner) }}</strong></span>
            <span>执行模块<strong>{{ analysisResult.agent_steps.length }} 步</strong></span>
          </div>
          <div class="agent-chain">
            <template v-for="(step, index) in analysisResult.agent_steps" :key="`chain-${step.name}-${index}`">
              <span class="agent-chip">{{ shortAgentName(step.name) }}</span>
              <span v-if="index < analysisResult.agent_steps.length - 1" class="chain-arrow">→</span>
            </template>
          </div>
        </div>

        <!-- Agent 执行流程放在病例录入区下方，平衡左右栏高度 -->
        <div v-if="analysisResult?.agent_steps?.length" class="diagnosis-card agent-execution-card left-agent-execution">
          <h3 class="block-title"><span>Agent 执行流程</span><em>真实后端调用轨迹</em></h3>
          <div class="execution-list">
            <div v-for="(step, index) in analysisResult.agent_steps" :key="`${step.name}-${index}`" class="execution-step">
              <span class="step-index">{{ index + 1 }}</span>
              <div class="step-content">
                <strong>{{ step.name }}</strong>
                <p>{{ step.summary }}</p>
                <details v-if="step.output && Object.keys(step.output).length" class="structured-output">
                  <summary>查看该步结构化输出</summary>
                  <pre>{{ formatJson(step.output) }}</pre>
                </details>
              </div>
              <span class="step-status">
                <el-icon v-if="step.status === 'completed'"><CircleCheck /></el-icon>
                {{ step.status === 'completed' ? '已完成' : step.status }}
              </span>
            </div>
          </div>
        </div>
      </section>

      <!-- ========== 右侧：分析结果区（50%） ========== -->
      <section class="right-panel">
        <div class="panel-card">
          <!-- 小型关联图谱 -->
          <div class="analysis-block">
            <h3 class="block-title">
              <el-icon><DataAnalysis /></el-icon>
              <span>辨证论治图谱</span>
            </h3>
            <div class="mini-graph-wrapper" ref="miniGraphContainer">
              <div v-if="!analysisResult" class="graph-placeholder">
                <el-icon><DataAnalysis /></el-icon>
                <p>录入症状后点击分析，将自动生成关联图谱</p>
              </div>
              <template v-else>
                <div class="graph-tools">
                  <el-button text class="graph-tool-btn" title="放大" @click.stop="zoomMiniGraph(0.12)">
                    <el-icon><ZoomIn /></el-icon>
                  </el-button>
                  <el-button text class="graph-tool-btn" title="缩小" @click.stop="zoomMiniGraph(-0.12)">
                    <el-icon><ZoomOut /></el-icon>
                  </el-button>
                  <el-button text class="graph-tool-btn" title="重置" @click.stop="resetMiniGraphZoom">
                    <el-icon><RefreshLeft /></el-icon>
                  </el-button>
                </div>
                <div ref="miniChartRef" class="mini-chart"></div>
              </template>
            </div>
          </div>

          <!-- 证候诊断卡片 -->
          <div class="diagnosis-card syndrome-card">
            <h3 class="block-title">
              <el-icon><Tickets /></el-icon>
              <span>证候诊断</span>
            </h3>
            <div class="diagnosis-scroll">
              <template v-if="analysisResult">
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
                <div class="diagnosis-basis markdown-body" v-html="renderedDiagnosis"></div>
              </template>
              <div v-else class="diagnosis-empty">录入症状后点击分析，将自动生成证候诊断与辨证依据</div>
            </div>
          </div>

          <!-- 推荐方剂卡片 -->
          <div class="diagnosis-card formula-card">
            <h3 class="block-title">
              <el-icon><Collection /></el-icon>
              <span>推荐方剂</span>
            </h3>
            <div class="diagnosis-scroll">
              <template v-if="analysisResult">
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
              </template>
              <div v-else class="diagnosis-empty">录入症状后点击分析，将自动生成推荐方剂、核心药材与依据片段</div>
            </div>
          </div>

          <!-- 症状追问 Agent -->
          <div v-if="analysisResult?.follow_up_questions?.length" class="diagnosis-card tool-output-card followup-output">
            <h3 class="block-title"><span>症状追问 Agent</span><em>上下文补充</em></h3>
            <p class="tool-description">当前四诊信息仍可补充，系统生成以下教学追问：</p>
            <div class="followup-questions">
              <button v-for="(question, index) in analysisResult.follow_up_questions" :key="question" type="button" @click="addFollowupToNote(question)">
                <b>{{ index + 1 }}</b>{{ question }}
              </button>
            </div>
          </div>

          <!-- 图谱数据 SQL Agent -->
          <div v-if="analysisResult?.sql_result" class="diagnosis-card tool-output-card sql-output">
            <h3 class="block-title"><span>图谱数据 SQL Agent</span><em>只读结构化查询</em></h3>
            <div class="sql-metrics">
              <span>执行状态<strong>{{ analysisResult.sql_result.text_to_sql?.status || analysisResult.sql_result.status || 'completed' }}</strong></span>
              <span>返回记录<strong>{{ analysisResult.sql_result.text_to_sql?.row_count ?? analysisResult.sql_result.row_count ?? analysisResult.sql_result.text_to_sql?.rows?.length ?? analysisResult.sql_result.rows?.length ?? 0 }}</strong></span>
              <span>安全模式<strong>SELECT 只读</strong></span>
            </div>
            <details v-if="analysisResult.sql_result.text_to_sql?.rows?.length || analysisResult.sql_result.rows?.length" class="structured-output">
              <summary>查看 SQL 结构化结果</summary>
              <pre>{{ formatJson(analysisResult.sql_result.text_to_sql?.rows || analysisResult.sql_result.rows) }}</pre>
            </details>
          </div>

          <!-- 方剂说明 Agent -->
          <div v-if="analysisResult?.formula_explanations?.length" class="diagnosis-card tool-output-card formula-output">
            <h3 class="block-title"><span>方剂说明 Agent</span><em>组成 · 功效 · 证候</em></h3>
            <div v-for="item in analysisResult.formula_explanations" :key="item.name" class="formula-explanation">
              <strong>{{ item.name }}</strong>
              <p><b>组成：</b>{{ item.composition?.join('、') || '暂无组成数据' }}</p>
              <p><b>功效：</b>{{ item.effects?.join('；') || '暂无功效数据' }}</p>
              <p><b>适用证候：</b>{{ item.main_indications?.join('、') || '暂无对应证候' }}</p>
              <small v-if="item.notes">依据：{{ item.notes }}</small>
            </div>
          </div>

          <!-- 文献检索 Agent -->
          <div v-if="analysisResult?.evidence?.length" class="diagnosis-card tool-output-card literature-output">
            <h3 class="block-title"><span>文献检索 Agent</span><em>可追溯依据 · {{ formatConfidence(analysisResult.evidence_confidence) }}</em></h3>
            <div class="literature-list">
              <div v-for="(ev, index) in analysisResult.evidence" :key="`${ev.title}-${index}`" class="literature-item">
                <b>[{{ index + 1 }}]</b>
                <div><strong>{{ ev.title }}</strong><p>{{ ev.content }}</p><small v-if="ev.citation || ev.source">来源：{{ ev.citation || ev.source }}</small></div>
              </div>
            </div>
          </div>

          <el-alert v-if="analysisResult?.safety_notice" :title="analysisResult.safety_notice" type="warning" :closable="false" show-icon />

          <!-- 教学笔记区 -->
          <div class="analysis-block">
            <h3 class="block-title">
              <el-icon><Memo /></el-icon>
              <span>教学笔记</span>
            </h3>
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
      <div v-if="showHistory" ref="historySectionRef" class="case-history">
        <div class="history-header">
          <h3>
            <el-icon><Clock /></el-icon>
            <span>历史病例</span>
          </h3>
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
                  {{ historySyndromeText(c) }}
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
  DataAnalysis, Refresh, Loading, User,
  EditPen, FirstAidKit, Tickets, Collection, Memo,
  ZoomIn, ZoomOut, RefreshLeft, CircleCheck
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import MarkdownIt from 'markdown-it'
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
const historySectionRef = ref<HTMLElement>()

// 迷你图谱
const miniChartRef = ref<HTMLDivElement>()
const miniGraphContainer = ref<HTMLElement>()
let miniChartInstance: echarts.ECharts | null = null
const miniGraphZoom = ref(0.9)

// ==================== 计算属性 ====================
const canAnalyze = computed(() => {
  return form.chiefComplaint.trim().length > 0
})

const markdown = new MarkdownIt({
  html: false,
  linkify: false,
  breaks: true,
  typographer: true,
})

const renderedDiagnosis = computed(() => {
  return markdown.render(analysisResult.value?.answer || '')
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
  miniGraphZoom.value = 0.9

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
      roam: true,
      draggable: true,
      zoom: miniGraphZoom.value,
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

function zoomMiniGraph(delta: number) {
  if (!miniChartInstance) return
  miniGraphZoom.value = Math.min(1.6, Math.max(0.55, miniGraphZoom.value + delta))
  miniChartInstance.setOption({
    series: [{
      zoom: miniGraphZoom.value,
    }],
  })
}

function resetMiniGraphZoom() {
  if (!miniChartInstance) return
  miniGraphZoom.value = 0.9
  miniChartInstance.setOption({
    series: [{
      zoom: miniGraphZoom.value,
      center: ['50%', '50%'],
    }],
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
    ElMessage.success('病例已保存')
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
    if (Array.isArray(res?.data?.list)) {
      historyCases.value = res.data.list
    } else if (res?.data?.length > 0) {
      historyCases.value = res.data
    } else if (Array.isArray(res?.list)) {
      historyCases.value = res.list
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

async function toggleHistory() {
  showHistory.value = !showHistory.value
  if (!showHistory.value) return

  await loadHistoryCases()
  await nextTick()
  historySectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
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

function historySyndromeText(caseItem: any): string {
  const syndromes = caseItem?.analysisResult?.syndromes || caseItem?.syndromes || []
  return Array.isArray(syndromes) && syndromes.length > 0 ? syndromes.join('、') : '待分析'
}

const intentLabels: Record<string, string> = {
  case_analysis: '病例辨证教学',
  formula_query: '方剂知识查询',
  literature_query: '文献依据查询',
  knowledge_query: '中医药知识解释',
}

function formatIntent(intent?: string): string {
  return intentLabels[intent || ''] || intent || '自动识别'
}

function formatPlanner(planner?: string): string {
  if (planner === 'llm-dynamic') return '大模型动态规划'
  if (planner === 'local-dynamic') return '本地动态规划'
  return planner || '动态工具规划'
}

function shortAgentName(name: string): string {
  return name
    .replace('动态工具规划', '总控规划')
    .replace('图谱数据 Text-to-SQL Agent', '图谱 SQL')
    .replace('向量文献检索 Agent', '文献检索')
    .replace('流式语音问答 Agent', '流式语音')
    .replace('症状分析 Agent', '症状分析')
    .replace('症状追问 Agent', '症状追问')
    .replace('图谱查询 Agent', '图谱查询')
    .replace('方剂说明 Agent', '方剂说明')
    .replace('知识解释 Agent', '知识解释')
    .replace('安全审查 Agent', '安全审查')
}

function formatConfidence(confidence?: string): string {
  const labels: Record<string, string> = { high: '高可信度', medium: '中可信度', low: '低可信度', insufficient: '资料不足' }
  return labels[confidence || ''] || confidence || '待评估'
}

function formatJson(value: any): string {
  return JSON.stringify(value, null, 2)
}

function addFollowupToNote(question: string) {
  const line = `待追问：${question}`
  if (!teachingNote.value.includes(line)) {
    teachingNote.value = teachingNote.value ? `${teachingNote.value}\n${line}` : line
  }
  ElMessage.success('已加入教学笔记')
}

// ==================== 监听 ====================

watch(() => analysisResult.value, async (newVal) => {
  if (newVal?.graph?.nodes?.length) {
    await nextTick()
    renderMiniGraph()
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
$card-shadow: 0 6px 24px rgba(42, 64, 48, 0.08);
$card-border: rgba(110, 135, 120, 0.14);
$white: #ffffff;

$syndrome-red: #b13e3e;
$formula-brown: #8c6e4a;
$herb-green: #588264;

// ==================== 主容器 ====================
.case-study {
  margin: 0 auto;
  padding: 18px 32px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background-color: $cream-bg;
  min-height: calc(100vh - 64px);
}

// ==================== 两栏主体 ====================
.case-main {
  display: flex;
  align-items: stretch;
  gap: 18px;
  min-height: calc(100vh - 64px - 220px);

  &.has-analysis {
    align-items: flex-start;

    .left-panel {
      .panel-card {
        height: auto;
      }

      .form-body {
        flex: none;
        overflow-y: visible;
      }
    }

    .form-actions {
      margin-top: 18px;
    }
  }
}

// ==================== 面板通用 ====================
.panel-card {
  background: #fffefb;
  border: 1px solid $card-border;
  border-radius: 12px;
  box-shadow: $card-shadow;
  padding: 22px;
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
    margin-bottom: 18px;
    padding-bottom: 14px;
    border-bottom: 1px solid $card-border;

    .panel-title {
      display: flex;
      align-items: center;
      gap: 10px;
      margin: 0;
      font-size: 18px;
      font-weight: 600;
      color: $dark-green;

      .el-icon {
        color: $mid-green;
        font-size: 20px;
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
    gap: 18px;

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
  padding: 9px 18px;
  font-size: 14px;
  font-weight: 500;
  transition: background-color 0.2s, border-color 0.2s, color 0.2s, box-shadow 0.2s, transform 0.2s;

  &.primary-tcm {
    background: $dark-green;
    color: #fff;
    border-color: $dark-green;
    &:hover {
      background: $mid-green;
      border-color: $mid-green;
      box-shadow: 0 6px 16px rgba(42, 64, 48, 0.16);
    }
  }

  &.ghost-tcm {
    color: $text-light;
    border-color: $card-border;
    background: rgba(255, 254, 251, 0.72);
    &:hover {
      color: $dark-green;
      background: $light-cream;
      border-color: rgba(70, 99, 80, 0.24);
    }
  }

  &.analyze-btn {
    background: $dark-green;
    color: #fff;
    border: none;
    padding: 11px 28px;
    font-size: 15px;
    font-weight: 600;
    border-radius: 9px;

    &:hover:not(:disabled) {
      background: $mid-green;
      transform: translateY(-1px);
      box-shadow: 0 8px 20px rgba(42, 64, 48, 0.18);
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
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    color: $dark-green;
    margin: 0 0 10px 0;

    .el-icon {
      color: $mid-green;
      font-size: 15px;
    }
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
    font-size: 12px;
    color: $text-light;
    margin-bottom: 6px;
    font-weight: 500;
  }

  :deep(.el-input__wrapper) {
    border-radius: 8px;
    background: #fff;
    box-shadow: 0 0 0 1px $card-border inset;
    transition: box-shadow 0.2s, background-color 0.2s;
    &:hover { box-shadow: 0 0 0 1px rgba(70, 99, 80, 0.28) inset; }
    &.is-focus { box-shadow: 0 0 0 1px $mid-green inset, 0 0 0 3px rgba(70, 99, 80, 0.1); }
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
    font-size: 13px;
    border-radius: 8px;
    background: #fff;
    border-color: transparent;
    box-shadow: 0 0 0 1px $card-border inset;
    &:focus { box-shadow: 0 0 0 1px $mid-green inset, 0 0 0 3px rgba(70, 99, 80, 0.1); }
  }

}

// 表单底部操作
.form-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 18px;
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

.orchestrator-card {
  padding: 18px;
  border: 1px solid rgba(200, 168, 110, 0.3);
  border-radius: 12px;
  color: #f7f3eb;
  background:
    radial-gradient(circle at 90% 0%, rgba(200, 168, 110, 0.2), transparent 34%),
    linear-gradient(135deg, #263b2c, $dark-green 55%, #3d5946);
  box-shadow: 0 10px 26px rgba(42, 64, 48, 0.18);

  .orchestrator-heading {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 14px;
    h3 { margin: 4px 0; color: #fff; font-size: 18px; }
    p { margin: 0; color: #d9e2d9; font-size: 11px; }
  }

  .orchestrator-kicker { color: $soft-gold; font-size: 9px; letter-spacing: 0.14em; }
  .run-status {
    flex: 0 0 auto;
    padding: 5px 9px;
    border: 1px solid rgba(220, 235, 222, 0.22);
    border-radius: 999px;
    color: #d9eadb;
    background: rgba(255, 255, 255, 0.08);
    font-size: 10px;
    i { display: inline-block; width: 6px; height: 6px; margin-right: 4px; border-radius: 50%; background: #8fc49a; box-shadow: 0 0 7px #8fc49a; }
  }

  .orchestrator-meta {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 7px;
    margin: 13px 0;
    span { padding: 7px 9px; border-radius: 7px; background: rgba(255, 255, 255, 0.07); color: #c8d3ca; font-size: 10px; }
    strong { display: block; margin-top: 2px; color: #fff; font-size: 11px; }
  }

  .agent-chain { display: flex; align-items: center; gap: 5px; overflow-x: auto; padding-bottom: 3px; }
  .agent-chip { flex: 0 0 auto; padding: 5px 8px; border: 1px solid rgba(200, 168, 110, 0.2); border-radius: 7px; background: rgba(255, 255, 255, 0.07); color: #f7f3eb; font-size: 10px; }
  .chain-arrow { color: $soft-gold; font-size: 10px; }
}

.left-orchestrator-card {
  margin-top: 16px;
}

.analysis-block {
  .block-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    font-weight: 600;
    color: $dark-green;
    margin: 0 0 10px 0;

    .el-icon {
      color: $mid-green;
      font-size: 16px;
    }
  }
}

// 迷你图谱 - 国风浅色背景
.mini-graph-wrapper {
  background: #fffdfb;
  border: 1px solid rgba(110, 135, 120, 0.14);
  border-radius: 10px;
  min-height: 220px;
  position: relative;
  overflow: hidden;
  box-shadow: 0 6px 18px rgba(42, 64, 48, 0.06);

  .mini-chart {
    width: 100%;
    height: 220px;
    cursor: grab;

    &:active {
      cursor: grabbing;
    }
  }

  .graph-tools {
    position: absolute;
    top: 8px;
    right: 8px;
    z-index: 2;
    display: flex;
    gap: 4px;
    padding: 4px;
    border: 1px solid rgba(110, 135, 120, 0.14);
    border-radius: 8px;
    background: rgba(255, 254, 251, 0.88);
    box-shadow: 0 4px 14px rgba(42, 64, 48, 0.08);
    backdrop-filter: blur(6px);
  }

  .graph-tool-btn {
    width: 26px;
    height: 26px;
    min-height: 26px;
    padding: 0;
    border-radius: 7px;
    color: $mid-green;

    &:hover {
      color: $dark-green;
      background: rgba(70, 99, 80, 0.08);
    }

    .el-icon {
      font-size: 15px;
    }
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
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid $card-border;
  background: #fffefb;
  display: flex;
  flex-direction: column;
  min-height: 0;
  box-shadow: 0 6px 18px rgba(42, 64, 48, 0.06);

  > .block-title {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 0 0 10px 0;
    font-size: 14px;
    font-weight: 600;
    line-height: 18px;
    color: $dark-green;

    .el-icon {
      flex: 0 0 auto;
      width: 18px;
      height: 18px;
      color: $mid-green;
      font-size: 16px;
    }

    span {
      line-height: 18px;
    }
  }

  .diagnosis-scroll {
    min-height: 0;
    overflow-y: auto;
    padding-right: 4px;

    &::-webkit-scrollbar {
      width: 5px;
    }

    &::-webkit-scrollbar-thumb {
      background: rgba(110, 135, 120, 0.24);
      border-radius: 5px;
    }
  }

  .diagnosis-empty {
    display: flex;
    align-items: center;
    min-height: 56px;
    color: rgba(107, 122, 114, 0.78);
    font-size: 12px;
    line-height: 1.6;
  }

  &.syndrome-card {
    background: #fffefb;
    border-color: rgba(110, 135, 120, 0.14);
    max-height: 190px;

    .diagnosis-scroll {
      max-height: 132px;
    }

    .syndrome-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin-bottom: 8px;

      .syndrome-tag {
        display: inline-block;
        padding: 4px 10px;
        background: rgba(177, 62, 62, 0.08);
        color: #8f3434;
        border: 1px solid rgba(177, 62, 62, 0.16);
        border-radius: 999px;
        font-size: 12px;
        font-weight: 500;
        line-height: 1.35;
        cursor: pointer;
        transition: all 0.25s;

        &:hover {
          transform: translateY(-2px);
          background: rgba(177, 62, 62, 0.12);
          box-shadow: 0 6px 14px rgba(177, 62, 62, 0.12);
        }
      }
    }

    .diagnosis-basis {
      margin: 0;
      font-size: 12px;
      color: $text-light;
      line-height: 1.65;

      :deep(p) {
        margin: 0 0 6px;
      }

      :deep(p:last-child) {
        margin-bottom: 0;
      }

      :deep(ul),
      :deep(ol) {
        margin: 4px 0 6px;
        padding-left: 20px;
      }

      :deep(strong) {
        color: $text-dark;
        font-weight: 600;
      }
    }
  }

  &.formula-card {
    background: #fffefb;
    border-color: rgba(110, 135, 120, 0.14);
    max-height: 220px;

    .diagnosis-scroll {
      max-height: 162px;
    }

    .formula-header {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin-bottom: 10px;

      .formula-tag {
        display: inline-block;
        padding: 4px 10px;
        background: rgba(200, 168, 110, 0.14);
        color: #7d623c;
        border: 1px solid rgba(200, 168, 110, 0.22);
        border-radius: 999px;
        font-size: 12px;
        font-weight: 500;
        line-height: 1.35;
        cursor: pointer;
        transition: all 0.25s;

        &:hover {
          transform: translateY(-2px);
          background: rgba(200, 168, 110, 0.2);
          box-shadow: 0 6px 14px rgba(140, 110, 74, 0.12);
        }
      }
    }

    .herb-list {
      margin-bottom: 10px;
      line-height: 1.7;

      .herb-label {
        font-size: 12px;
        color: $text-light;
        font-weight: 500;
      }

      .herb-tag {
        font-size: 12px;
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

.tool-output-card,
.agent-execution-card {
  .block-title {
    justify-content: space-between;
    span { color: $dark-green; }
    em { color: $text-light; font-size: 10px; font-style: normal; font-weight: 400; }
  }
}

.tool-description { margin: -3px 0 9px; color: $text-light; font-size: 11px; }

.followup-output {
  background: #f4f8f3;
  .followup-questions { display: flex; flex-direction: column; gap: 7px; }
  button { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border: 1px solid rgba(70, 99, 80, 0.16); border-radius: 8px; background: #fffefb; color: $dark-green; text-align: left; cursor: pointer; }
  button:hover { border-color: $mid-green; }
  button b { color: $mid-green; }
}

.sql-output {
  background: #f8f6ef;
  .sql-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .sql-metrics span { padding: 8px; border-radius: 8px; background: #fffefb; color: $text-light; font-size: 10px; }
  .sql-metrics strong { display: block; margin-top: 3px; color: $dark-green; font-size: 12px; }
}

.formula-output {
  background: #fbf7ee;
  .formula-explanation > strong { display: block; margin-bottom: 6px; color: $formula-brown; }
  p { margin: 4px 0; color: $text-light; font-size: 11px; line-height: 1.55; }
  p b { color: $text-dark; }
  small { display: block; margin-top: 7px; padding-top: 6px; border-top: 1px dashed rgba(200, 168, 110, 0.36); color: $text-light; }
}

.literature-output {
  background: #faf8f2;
  .literature-list { display: flex; flex-direction: column; gap: 8px; }
  .literature-item { display: flex; gap: 8px; padding: 9px; border: 1px solid $card-border; border-radius: 8px; background: #fffefb; }
  .literature-item > b { color: $formula-brown; font-size: 11px; }
  .literature-item strong { color: $dark-green; font-size: 11px; }
  .literature-item p { margin: 3px 0; color: $text-light; font-size: 11px; line-height: 1.5; }
  .literature-item small { color: #8a938d; font-size: 9px; }
}

.agent-execution-card {
  background: #f3f7f3;
  border-color: rgba(70, 99, 80, 0.2);
  .execution-list { display: flex; flex-direction: column; gap: 7px; }
  .execution-step { display: flex; align-items: flex-start; gap: 9px; padding: 9px; border: 1px solid rgba(70, 99, 80, 0.12); border-radius: 8px; background: #fffefb; }
  .step-index { display: inline-flex; align-items: center; justify-content: center; flex: 0 0 23px; height: 23px; border-radius: 50%; background: $mid-green; color: #fff; font-size: 10px; font-weight: 700; }
  .step-content { flex: 1; min-width: 0; }
  .step-content strong { color: $dark-green; font-size: 11px; }
  .step-content p { margin: 2px 0; color: $text-light; font-size: 10px; line-height: 1.45; }
  .step-status {
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    gap: 3px;
    color: $herb-green;
    font-size: 9px;
    font-weight: 600;

    .el-icon {
      font-size: 11px;
    }
  }
}

.left-agent-execution {
  margin-top: 16px;
  box-shadow: $card-shadow;
}

.structured-output {
  margin-top: 6px;
  summary { width: fit-content; color: $mid-green; font-size: 9px; cursor: pointer; }
  pre { max-height: 210px; margin: 6px 0 0; padding: 9px; overflow: auto; border-radius: 7px; background: #213126; color: #d9e2d9; font: 9px/1.5 Consolas, monospace; white-space: pre-wrap; word-break: break-all; }
}

// 教学笔记
.note-textarea {
  :deep(.el-textarea__inner) {
    border-style: dashed;
    border-color: transparent;
    background: #fffdfb;
    font-size: 13px;
    line-height: 1.7;
    border-radius: 8px;
    box-shadow: 0 0 0 1px rgba(110, 135, 120, 0.14) inset, 0 6px 18px rgba(42, 64, 48, 0.06);

    &:focus {
      border-color: $mid-green;
      border-style: dashed;
      box-shadow: 0 0 0 2px rgba(70, 99, 80, 0.08);
    }
  }
}

// ==================== 历史病例 ====================
.case-history {
  background: #fffefb;
  border: 1px solid $card-border;
  border-radius: 12px;
  box-shadow: $card-shadow;
  padding: 18px 20px;

  .history-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    h3 {
      display: flex;
      align-items: center;
      gap: 6px;
      margin: 0;
      font-size: 15px;
      font-weight: 600;
      color: $dark-green;

      .el-icon {
        color: $mid-green;
        font-size: 16px;
      }
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
    padding: 12px;
    border: 1px solid rgba(110, 135, 120, 0.12);
    border-radius: 10px;
    cursor: pointer;
    transition: background-color 0.2s, border-color 0.2s, box-shadow 0.2s, transform 0.2s;
    flex-shrink: 0;
    background: #fbf7ee;

    &:hover {
      transform: translateY(-2px);
      border-color: rgba(70, 99, 80, 0.22);
      box-shadow: 0 8px 18px rgba(42, 64, 48, 0.08);
      background: #fffefb;
    }

    &.active {
      border-color: rgba(200, 168, 110, 0.36);
      box-shadow: inset 0 0 0 1px rgba(200, 168, 110, 0.18);
      background: #fffefb;
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
