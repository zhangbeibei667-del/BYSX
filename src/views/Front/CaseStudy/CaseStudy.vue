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
              <el-button type="success" @click="handleSaveCase" :loading="saving">
                <el-icon><FolderChecked /></el-icon>
                保存病例
              </el-button>
              <el-button plain @click="showHistory = !showHistory">
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
              type="primary"
              size="large"
              class="analyze-btn"
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
          <el-button text type="primary" @click="loadHistoryCases" :loading="historyLoading">
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

// ==================== 图谱颜色常量 ====================
const TYPE_COLORS: Record<string, string> = {
  '药材': '#10b981',
  '方剂': '#6366f1',
  '症状': '#f59e0b',
  '证候': '#b91c1c',
  '功效': '#06b6d4',
  '禁忌': '#ef4444',
  '文献': '#8b5cf6',
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

    try {
      const createRes: any = await caseApi.create(caseData)
      if (createRes?.data?.id) {
        caseId = createRes.data.id
      } else if (createRes?.id) {
        caseId = createRes.id
      } else if (typeof createRes === 'string') {
        caseId = createRes
      }
      currentCaseId.value = caseId
    } catch {
      // 如果后端 API 未就绪，继续使用模拟数据
      console.log('病例创建 API 未就绪，使用本地分析')
    }

    // 分析病例
    if (caseId) {
      try {
        const analyzeRes: any = await caseApi.analyze(caseId)
        if (analyzeRes?.data) {
          analysisResult.value = analyzeRes.data
        } else if (analyzeRes?.answer) {
          analysisResult.value = analyzeRes
        } else {
          useMockAnalysis()
        }
      } catch {
        useMockAnalysis()
      }
    } else {
      useMockAnalysis()
    }

    // 渲染迷你图谱
    await nextTick()
    renderMiniGraph()
  } catch (err) {
    console.error('分析失败:', err)
    ElMessage.error('分析失败，请稍后重试')
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

function useMockAnalysis() {
  // 根据症状关键词模拟分析
  const text = form.chiefComplaint + form.tongueExam + form.pulseExam

  // 心脾两虚模式
  const hasHeartSpleen = /(失眠|多梦|心悸|健忘|食少|乏力|面色萎黄|舌淡|脉细弱|脉细)/.test(text)
  // 外感风寒模式
  const hasWindCold = /(畏寒|发热|咳嗽|鼻塞|流清涕|头痛|身痛|舌苔薄白|脉浮|脉浮紧)/.test(text)
  // 少阳证模式
  const hasShaoyang = /(口苦|咽干|目眩|胸胁|往来寒热|心烦|喜呕)/.test(text)
  // 血虚模式
  const hasBloodDeficiency = /(头晕|目眩|面色苍白|爪甲|月经|手足麻木|舌淡白|脉细无力)/.test(text)
  // 肝气郁结模式
  const hasLiverQi = /(胁痛|胁肋|抑郁|善太息|胸闷|嗳气|情绪低落|脉弦|急躁|易怒|乳房胀|痛经|月经不调).*(抑郁|胸闷|胁|善太息|嗳气|叹息)/.test(text)
    || /(抑郁|胸闷|胁|善太息).*(胁痛|胁肋|嗳气|情绪|脉弦)/.test(text)
  // 肾阴虚模式
  const hasKidneyYin = /(腰膝酸软|五心烦热|潮热|盗汗|口干咽燥|手足心热|耳鸣|遗精|舌红少苔|脉细数)/.test(text)
  // 脾胃湿热模式
  const hasSpleenStomachDamp = /(脘腹|痞满|恶心|呕吐|纳呆|大便黏滞|里急后重|舌红苔黄腻|脉滑数|黄疸|身目发黄)/.test(text)
  // 痰湿内阻模式
  const hasPhlegmDamp = /(痰多|胸闷|头重|肢体困重|眩晕|呕恶|舌苔白腻|脉濡滑|形体肥胖|嗜睡)/.test(text)
  // 气虚模式
  const hasQiDeficiency = /(气短|懒言|自汗|神疲|乏力|面色.*白|舌淡胖|脉虚|脉弱).*(乏力|气短|自汗)/.test(text)
    || /(乏力|气短|自汗|神疲|懒言).*(乏力|气短|自汗|神疲|懒言)/.test(text)

  let graph: GraphResponse = { nodes: [], edges: [] }
  let syndromes: string[] = []
  let formulas: string[] = []
  let herbs: string[] = []
  let answer = ''
  let evidence: any[] = []

  if (hasHeartSpleen) {
    syndromes = ['心脾两虚']
    formulas = ['归脾汤']
    herbs = ['酸枣仁', '远志', '人参', '黄芪', '当归', '茯苓', '白术', '甘草']
    answer = '患者表现为失眠多梦、心悸健忘，伴食少乏力、面色萎黄，舌淡苔白、脉细弱。四诊合参，辨证为心脾两虚证。心主血脉而藏神，脾主运化而为气血生化之源。思虑过度，劳伤心脾，气血亏虚，心神失养，故失眠、心悸、健忘；脾气虚则运化失职，故食少、乏力。治宜益气补血、健脾养心，方选归脾汤加减。'
    evidence = [
      { title: '归脾汤方解', content: '归脾汤出自《济生方》，具有益气补血、健脾养心之功效，是治疗心脾两虚证的代表方剂。' },
    ]

    graph = {
      nodes: [
        { id: 'S_XP', label: '失眠多梦', type: '症状' },
        { id: 'S_XJ', label: '心悸健忘', type: '症状' },
        { id: 'S_SL', label: '食少乏力', type: '症状' },
        { id: 'Z_XPLX', label: '心脾两虚', type: '证候' },
        { id: 'F_GPT', label: '归脾汤', type: '方剂' },
        { id: 'H_SZR', label: '酸枣仁', type: '药材' },
        { id: 'H_YZ', label: '远志', type: '药材' },
        { id: 'H_RS', label: '人参', type: '药材' },
        { id: 'H_HQ', label: '黄芪', type: '药材' },
        { id: 'H_DG', label: '当归', type: '药材' },
        { id: 'H_FL', label: '茯苓', type: '药材' },
        { id: 'H_BZ', label: '白术', type: '药材' },
        { id: 'H_GC', label: '甘草', type: '药材' },
      ],
      edges: [
        { source: 'S_XP', target: 'Z_XPLX', label: '提示' },
        { source: 'S_XJ', target: 'Z_XPLX', label: '提示' },
        { source: 'S_SL', target: 'Z_XPLX', label: '提示' },
        { source: 'Z_XPLX', target: 'F_GPT', label: '对应' },
        { source: 'F_GPT', target: 'H_SZR', label: '包含' },
        { source: 'F_GPT', target: 'H_YZ', label: '包含' },
        { source: 'F_GPT', target: 'H_RS', label: '包含' },
        { source: 'F_GPT', target: 'H_HQ', label: '包含' },
        { source: 'F_GPT', target: 'H_DG', label: '包含' },
        { source: 'F_GPT', target: 'H_FL', label: '包含' },
        { source: 'F_GPT', target: 'H_BZ', label: '包含' },
        { source: 'F_GPT', target: 'H_GC', label: '包含' },
      ],
    }
  } else if (hasWindCold) {
    syndromes = ['外感风寒']
    formulas = ['麻黄汤']
    herbs = ['麻黄', '桂枝', '杏仁', '甘草']
    answer = '患者表现为恶寒发热、头痛身痛、咳嗽、鼻塞流清涕，舌苔薄白、脉浮紧。四诊合参，辨证为外感风寒表实证。风寒之邪外束肌表，卫阳被遏，正邪交争，故恶寒发热；寒邪凝滞经络，故头痛身痛；肺气不宣，故咳嗽鼻塞。治宜发汗解表、宣肺平喘，方选麻黄汤加减。'
    evidence = [
      { title: '麻黄汤方解', content: '麻黄汤出自《伤寒论》，为辛温解表之峻剂，主治外感风寒表实证。麻黄、桂枝相须为用，发汗力强。' },
    ]

    graph = {
      nodes: [
        { id: 'S_WH', label: '畏寒发热', type: '症状' },
        { id: 'S_KS', label: '咳嗽', type: '症状' },
        { id: 'S_BS', label: '鼻塞', type: '症状' },
        { id: 'Z_WGHF', label: '外感风寒', type: '证候' },
        { id: 'F_MHT', label: '麻黄汤', type: '方剂' },
        { id: 'H_MH', label: '麻黄', type: '药材' },
        { id: 'H_GZ', label: '桂枝', type: '药材' },
        { id: 'H_XR', label: '杏仁', type: '药材' },
        { id: 'H_GC2', label: '甘草', type: '药材' },
      ],
      edges: [
        { source: 'S_WH', target: 'Z_WGHF', label: '提示' },
        { source: 'S_KS', target: 'Z_WGHF', label: '提示' },
        { source: 'S_BS', target: 'Z_WGHF', label: '提示' },
        { source: 'Z_WGHF', target: 'F_MHT', label: '对应' },
        { source: 'F_MHT', target: 'H_MH', label: '包含' },
        { source: 'F_MHT', target: 'H_GZ', label: '包含' },
        { source: 'F_MHT', target: 'H_XR', label: '包含' },
        { source: 'F_MHT', target: 'H_GC2', label: '包含' },
      ],
    }
  } else if (hasShaoyang) {
    syndromes = ['少阳证']
    formulas = ['小柴胡汤']
    herbs = ['柴胡', '黄芩', '人参', '半夏', '生姜', '大枣', '甘草']
    answer = '患者表现为口苦咽干、目眩、胸胁苦满、心烦喜呕、往来寒热。四诊合参，辨证为少阳证。邪入少阳，枢机不利，正邪分争于半表半里之间，故见寒热往来、胸胁苦满。治宜和解少阳，方选小柴胡汤加减。'
    evidence = [
      { title: '小柴胡汤方解', content: '小柴胡汤出自《伤寒论》，为和解少阳之代表方，具有和解少阳、调达枢机之功效。' },
    ]

    graph = {
      nodes: [
        { id: 'S_KK', label: '口苦咽干', type: '症状' },
        { id: 'S_XF', label: '心烦喜呕', type: '症状' },
        { id: 'S_MX', label: '目眩', type: '症状' },
        { id: 'Z_SYZ', label: '少阳证', type: '证候' },
        { id: 'F_XCHT', label: '小柴胡汤', type: '方剂' },
        { id: 'H_CH', label: '柴胡', type: '药材' },
        { id: 'H_HQ2', label: '黄芩', type: '药材' },
        { id: 'H_BX', label: '半夏', type: '药材' },
        { id: 'H_SJ', label: '生姜', type: '药材' },
      ],
      edges: [
        { source: 'S_KK', target: 'Z_SYZ', label: '提示' },
        { source: 'S_XF', target: 'Z_SYZ', label: '提示' },
        { source: 'S_MX', target: 'Z_SYZ', label: '提示' },
        { source: 'Z_SYZ', target: 'F_XCHT', label: '对应' },
        { source: 'F_XCHT', target: 'H_CH', label: '包含' },
        { source: 'F_XCHT', target: 'H_HQ2', label: '包含' },
        { source: 'F_XCHT', target: 'H_BX', label: '包含' },
        { source: 'F_XCHT', target: 'H_SJ', label: '包含' },
      ],
    }
  } else if (hasBloodDeficiency) {
    syndromes = ['血虚证']
    formulas = ['四物汤']
    herbs = ['当归', '熟地黄', '白芍', '川芎']
    answer = '患者表现为头晕目眩、面色苍白、手足麻木、舌淡白、脉细无力。四诊合参，辨证为血虚证。血虚不能上荣头面，故头晕目眩、面白；不能濡养四肢，故手足麻木。治宜补血养血，方选四物汤加减。'
    evidence = [
      { title: '四物汤方解', content: '四物汤为补血基础方，由当归、熟地黄、白芍、川芎组成，具有补血调血之功效。' },
    ]

    graph = {
      nodes: [
        { id: 'S_TY', label: '头晕目眩', type: '症状' },
        { id: 'S_MS', label: '手足麻木', type: '症状' },
        { id: 'Z_XXZ', label: '血虚证', type: '证候' },
        { id: 'F_SWT', label: '四物汤', type: '方剂' },
        { id: 'H_DG2', label: '当归', type: '药材' },
        { id: 'H_SDH', label: '熟地黄', type: '药材' },
        { id: 'H_BS', label: '白芍', type: '药材' },
        { id: 'H_CX', label: '川芎', type: '药材' },
      ],
      edges: [
        { source: 'S_TY', target: 'Z_XXZ', label: '提示' },
        { source: 'S_MS', target: 'Z_XXZ', label: '提示' },
        { source: 'Z_XXZ', target: 'F_SWT', label: '对应' },
        { source: 'F_SWT', target: 'H_DG2', label: '包含' },
        { source: 'F_SWT', target: 'H_SDH', label: '包含' },
        { source: 'F_SWT', target: 'H_BS', label: '包含' },
        { source: 'F_SWT', target: 'H_CX', label: '包含' },
      ],
    }
  } else if (hasLiverQi) {
    syndromes = ['肝气郁结']
    formulas = ['柴胡疏肝散']
    herbs = ['柴胡', '白芍', '枳壳', '香附', '川芎', '陈皮', '甘草']
    answer = '患者表现为胸胁胀痛、善太息、情志抑郁或急躁易怒，脉弦。四诊合参，辨证为肝气郁结证。肝主疏泄，调畅气机与情志。情志不遂，郁怒伤肝，肝失调达，气机郁滞，故胸胁胀痛、善太息。治宜疏肝解郁、行气止痛，方选柴胡疏肝散加减。'
    evidence = [
      { title: '柴胡疏肝散方解', content: '柴胡疏肝散出自《景岳全书》，具有疏肝理气、活血止痛之功效，是治疗肝气郁结证的代表方剂。' },
    ]

    graph = {
      nodes: [
        { id: 'S_XT', label: '胸胁胀痛', type: '症状' },
        { id: 'S_STX', label: '善太息', type: '症状' },
        { id: 'S_QZ', label: '情志抑郁', type: '症状' },
        { id: 'Z_GQYJ', label: '肝气郁结', type: '证候' },
        { id: 'F_CHSGS', label: '柴胡疏肝散', type: '方剂' },
        { id: 'H_CH2', label: '柴胡', type: '药材' },
        { id: 'H_BS2', label: '白芍', type: '药材' },
        { id: 'H_ZK', label: '枳壳', type: '药材' },
        { id: 'H_XF', label: '香附', type: '药材' },
      ],
      edges: [
        { source: 'S_XT', target: 'Z_GQYJ', label: '提示' },
        { source: 'S_STX', target: 'Z_GQYJ', label: '提示' },
        { source: 'S_QZ', target: 'Z_GQYJ', label: '提示' },
        { source: 'Z_GQYJ', target: 'F_CHSGS', label: '对应' },
        { source: 'F_CHSGS', target: 'H_CH2', label: '包含' },
        { source: 'F_CHSGS', target: 'H_BS2', label: '包含' },
        { source: 'F_CHSGS', target: 'H_ZK', label: '包含' },
        { source: 'F_CHSGS', target: 'H_XF', label: '包含' },
      ],
    }
  } else if (hasKidneyYin) {
    syndromes = ['肾阴虚']
    formulas = ['六味地黄丸']
    herbs = ['熟地黄', '山茱萸', '山药', '泽泻', '牡丹皮', '茯苓']
    answer = '患者表现为腰膝酸软、五心烦热、潮热盗汗、口干咽燥、舌红少苔、脉细数。四诊合参，辨证为肾阴虚证。肾主骨生髓，腰为肾之府。肾阴不足，髓海亏虚，骨骼失养，故腰膝酸软；阴虚生内热，故五心烦热、潮热盗汗。治宜滋补肾阴，方选六味地黄丸加减。'
    evidence = [
      { title: '六味地黄丸方解', content: '六味地黄丸出自《小儿药证直诀》，三补三泻，以补肾阴为主，是治疗肾阴虚证的基础方。' },
    ]

    graph = {
      nodes: [
        { id: 'S_YXSS', label: '腰膝酸软', type: '症状' },
        { id: 'S_WXFR', label: '五心烦热', type: '症状' },
        { id: 'S_CSDH', label: '潮热盗汗', type: '症状' },
        { id: 'Z_SYX', label: '肾阴虚', type: '证候' },
        { id: 'F_LWDHW', label: '六味地黄丸', type: '方剂' },
        { id: 'H_SDH2', label: '熟地黄', type: '药材' },
        { id: 'H_SZY', label: '山茱萸', type: '药材' },
        { id: 'H_SY2', label: '山药', type: '药材' },
        { id: 'H_ZX', label: '泽泻', type: '药材' },
      ],
      edges: [
        { source: 'S_YXSS', target: 'Z_SYX', label: '提示' },
        { source: 'S_WXFR', target: 'Z_SYX', label: '提示' },
        { source: 'S_CSDH', target: 'Z_SYX', label: '提示' },
        { source: 'Z_SYX', target: 'F_LWDHW', label: '对应' },
        { source: 'F_LWDHW', target: 'H_SDH2', label: '包含' },
        { source: 'F_LWDHW', target: 'H_SZY', label: '包含' },
        { source: 'F_LWDHW', target: 'H_SY2', label: '包含' },
        { source: 'F_LWDHW', target: 'H_ZX', label: '包含' },
      ],
    }
  } else if (hasSpleenStomachDamp) {
    syndromes = ['脾胃湿热']
    formulas = ['半夏泻心汤']
    herbs = ['半夏', '黄连', '黄芩', '干姜', '人参', '甘草', '大枣']
    answer = '患者表现为脘腹痞满、恶心呕吐、口苦口黏、大便黏滞、舌红苔黄腻、脉滑数。四诊合参，辨证为脾胃湿热证。湿热中阻，脾胃升降失常，气机壅滞，故脘腹痞满；胃气上逆，故恶心呕吐。治宜清热化湿、和胃降逆，方选半夏泻心汤加减。'
    evidence = [
      { title: '半夏泻心汤方解', content: '半夏泻心汤出自《伤寒论》，具有寒热平调、消痞散结之功效，是治疗脾胃湿热痞满证的代表方。' },
    ]

    graph = {
      nodes: [
        { id: 'S_WFPM', label: '脘腹痞满', type: '症状' },
        { id: 'S_EXOT', label: '恶心呕吐', type: '症状' },
        { id: 'S_KKNK', label: '口苦口黏', type: '症状' },
        { id: 'Z_PWSR', label: '脾胃湿热', type: '证候' },
        { id: 'F_BXXX', label: '半夏泻心汤', type: '方剂' },
        { id: 'H_BX2', label: '半夏', type: '药材' },
        { id: 'H_HL', label: '黄连', type: '药材' },
        { id: 'H_HQ3', label: '黄芩', type: '药材' },
        { id: 'H_GJ', label: '干姜', type: '药材' },
      ],
      edges: [
        { source: 'S_WFPM', target: 'Z_PWSR', label: '提示' },
        { source: 'S_EXOT', target: 'Z_PWSR', label: '提示' },
        { source: 'S_KKNK', target: 'Z_PWSR', label: '提示' },
        { source: 'Z_PWSR', target: 'F_BXXX', label: '对应' },
        { source: 'F_BXXX', target: 'H_BX2', label: '包含' },
        { source: 'F_BXXX', target: 'H_HL', label: '包含' },
        { source: 'F_BXXX', target: 'H_HQ3', label: '包含' },
        { source: 'F_BXXX', target: 'H_GJ', label: '包含' },
      ],
    }
  } else if (hasPhlegmDamp) {
    syndromes = ['痰湿内阻']
    formulas = ['二陈汤']
    herbs = ['半夏', '陈皮', '茯苓', '甘草', '生姜', '乌梅']
    answer = '患者表现为胸闷痰多、头重如裹、肢体困重、舌苔白腻、脉濡滑。四诊合参，辨证为痰湿内阻证。脾为生痰之源，肺为储痰之器。脾失健运，水湿内停，聚而为痰，痰湿中阻，清阳不升，故头重、胸闷、肢体困重。治宜燥湿化痰、理气和中，方选二陈汤加减。'
    evidence = [
      { title: '二陈汤方解', content: '二陈汤出自《太平惠民和剂局方》，为燥湿化痰的基础方，具有燥湿化痰、理气和中之功效。' },
    ]

    graph = {
      nodes: [
        { id: 'S_XM', label: '胸闷痰多', type: '症状' },
        { id: 'S_TZ', label: '头重如裹', type: '症状' },
        { id: 'S_ZTKZ', label: '肢体困重', type: '症状' },
        { id: 'Z_TSNZ', label: '痰湿内阻', type: '证候' },
        { id: 'F_ECT', label: '二陈汤', type: '方剂' },
        { id: 'H_BX3', label: '半夏', type: '药材' },
        { id: 'H_CP', label: '陈皮', type: '药材' },
        { id: 'H_FL2', label: '茯苓', type: '药材' },
        { id: 'H_GC3', label: '甘草', type: '药材' },
      ],
      edges: [
        { source: 'S_XM', target: 'Z_TSNZ', label: '提示' },
        { source: 'S_TZ', target: 'Z_TSNZ', label: '提示' },
        { source: 'S_ZTKZ', target: 'Z_TSNZ', label: '提示' },
        { source: 'Z_TSNZ', target: 'F_ECT', label: '对应' },
        { source: 'F_ECT', target: 'H_BX3', label: '包含' },
        { source: 'F_ECT', target: 'H_CP', label: '包含' },
        { source: 'F_ECT', target: 'H_FL2', label: '包含' },
        { source: 'F_ECT', target: 'H_GC3', label: '包含' },
      ],
    }
  } else if (hasQiDeficiency) {
    syndromes = ['气虚证']
    formulas = ['四君子汤']
    herbs = ['人参', '白术', '茯苓', '甘草']
    answer = '患者表现为气短懒言、神疲乏力、自汗、舌淡胖、脉虚。四诊合参，辨证为气虚证。元气不足，脏腑功能减退，故气短懒言、神疲乏力；卫气不固，故自汗。治宜益气健脾，方选四君子汤加减。'
    evidence = [
      { title: '四君子汤方解', content: '四君子汤出自《太平惠民和剂局方》，为补气基础方，具有益气健脾之功效。' },
    ]

    graph = {
      nodes: [
        { id: 'S_QD', label: '气短懒言', type: '症状' },
        { id: 'S_SPFL', label: '神疲乏力', type: '症状' },
        { id: 'S_ZH', label: '自汗', type: '症状' },
        { id: 'Z_QXZ', label: '气虚证', type: '证候' },
        { id: 'F_SJZT', label: '四君子汤', type: '方剂' },
        { id: 'H_RS2', label: '人参', type: '药材' },
        { id: 'H_BZ2', label: '白术', type: '药材' },
        { id: 'H_FL3', label: '茯苓', type: '药材' },
        { id: 'H_GC4', label: '甘草', type: '药材' },
      ],
      edges: [
        { source: 'S_QD', target: 'Z_QXZ', label: '提示' },
        { source: 'S_SPFL', target: 'Z_QXZ', label: '提示' },
        { source: 'S_ZH', target: 'Z_QXZ', label: '提示' },
        { source: 'Z_QXZ', target: 'F_SJZT', label: '对应' },
        { source: 'F_SJZT', target: 'H_RS2', label: '包含' },
        { source: 'F_SJZT', target: 'H_BZ2', label: '包含' },
        { source: 'F_SJZT', target: 'H_FL3', label: '包含' },
        { source: 'F_SJZT', target: 'H_GC4', label: '包含' },
      ],
    }
  } else {
    syndromes = ['需进一步辨证']
    formulas = ['请补充更多症状信息']
    herbs = []
    answer = '当前提供的症状信息不够充分，建议补充更多四诊信息（舌象、脉象等），以便进行准确的辨证分析。'
    evidence = []
    graph = { nodes: [], edges: [] }
  }

  // 从主诉中提取症状关键词作为节点
  if (graph.nodes.length === 0) {
    const symptomKeywords = extractSymptoms(form.chiefComplaint)
    graph.nodes = symptomKeywords.map((s, i) => ({ id: `S_LOCAL_${i}`, label: s, type: '症状' }))
  }

  analysisResult.value = {
    answer,
    symptoms: extractSymptoms(form.chiefComplaint),
    syndromes,
    formulas,
    herbs,
    graph,
    evidence,
    follow_up_questions: [],
    safety_notice: '本分析结果仅用于中医药知识学习和教学辅助，不构成医疗诊断或用药建议。',
  }
}

// 从文本中提取症状关键词
function extractSymptoms(text: string): string[] {
  const keywordList = ['失眠', '多梦', '心悸', '健忘', '乏力', '食少', '面色萎黄',
    '头晕', '目眩', '耳鸣', '畏寒', '发热', '咳嗽', '鼻塞', '流清涕',
    '口苦', '咽干', '胸胁苦满', '心烦', '喜呕', '往来寒热',
    '头痛', '身痛', '手足麻木', '爪甲不荣', '月经不调']
  return keywordList.filter(k => text.includes(k))
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
        color: '#e2e8f0',
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
      color: 'rgba(148,163,184,0.5)',
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
      backgroundColor: 'rgba(15,23,42,0.9)',
      borderColor: 'rgba(148,163,184,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter: (params: any) => {
        if (params.dataType === 'edge') {
          return `<span style="color:#94a3b8">${params.data.sourceLabel || ''}</span>
                  <span style="color:#fbbf24"> → ${params.data.name}</span>`
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
          color: '#ffffff',
        },
      },
    }],
  })

  // 点击节点跳转图谱页
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
    // 本地保存降级
    saveToLocal()
    ElMessage.success('✅ 病例已保存（本地）')
  } finally {
    saving.value = false
  }
}

function saveToLocal() {
  const cases = JSON.parse(localStorage.getItem('tcm_cases') || '[]')
  cases.push({
    id: Date.now().toString(),
    ...buildCaseData(),
    teachingNote: teachingNote.value,
    syndromes: analysisResult.value?.syndromes || [],
    formulas: analysisResult.value?.formulas || [],
    herbs: analysisResult.value?.herbs || [],
    createdAt: new Date().toISOString(),
  })
  localStorage.setItem('tcm_cases', JSON.stringify(cases))
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
      // 从历史数据构建分析结果
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

// 当分析结果变化时重新渲染图谱
watch(() => analysisResult.value, async (newVal) => {
  if (newVal?.graph?.nodes?.length) {
    await nextTick()
    renderMiniGraph()
  }
})

// 历史病例展开时自动加载
watch(showHistory, (val) => {
  if (val && historyCases.value.length === 0) {
    loadHistoryCases()
  }
})

// ==================== 生命周期 ====================

onMounted(() => {
  // 预加载历史病例到本地缓存
  loadLocalCases()
})

onBeforeUnmount(() => {
  disposeMiniChart()
  window.removeEventListener('resize', disposeMiniChart)
})
</script>

<style scoped lang="scss">
// ==================== 变量 ====================
$card-bg: #ffffff;
$card-radius: 14px;
$text-dark: #1e293b;
$text-muted: #94a3b8;
$text-body: #475569;
$indigo: #6366f1;
$emerald: #10b981;
$amber: #f59e0b;
$rose: #b91c1c;
$border-light: #e2e8f0;

// ==================== 主容器 ====================
.case-study {
  max-width: 1400px;
  margin: 0 auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

// ==================== 两栏主体 ====================
.case-main {
  display: flex;
  gap: 20px;
  min-height: calc(100vh - 64px - 220px);
}

// ==================== 面板通用 ====================
.panel-card {
  background: $card-bg;
  border-radius: $card-radius;
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.07);
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
    border-bottom: 1px solid $border-light;

    .panel-title {
      display: flex;
      align-items: center;
      gap: 10px;
      margin: 0;
      font-size: 20px;
      color: $text-dark;

      .el-icon {
        color: $indigo;
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
      background: #cbd5e1;
      border-radius: 4px;
    }
  }
}

// 表单区块
.form-section {
  .section-label {
    font-size: 14px;
    font-weight: 600;
    color: $text-dark;
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
    color: $text-muted;
    margin-bottom: 6px;
    font-weight: 500;
  }

  .input-suffix {
    color: $text-muted;
    font-size: 13px;
  }
}

// 症状输入区
.symptom-textarea-wrapper {
  position: relative;

  :deep(.el-textarea__inner) {
    line-height: 1.7;
    font-size: 14px;
  }

  .char-count {
    position: absolute;
    bottom: 8px;
    right: 14px;
    font-size: 11px;
    color: $text-muted;
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
  border-top: 1px solid $border-light;
  margin-top: auto;

  .analyze-btn {
    background: linear-gradient(135deg, $indigo, #4f46e5);
    border: none;
    padding: 12px 32px;
    font-size: 16px;
    font-weight: 600;
    border-radius: 10px;
    transition: all 0.3s;

    &:hover:not(:disabled) {
      background: linear-gradient(135deg, #4f46e5, #4338ca);
      transform: translateY(-1px);
      box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4);
    }

    &:disabled {
      background: #cbd5e1;
      cursor: not-allowed;
    }
  }
}

// ==================== 右侧面板 ====================
.right-panel {
  width: 50%;

  .panel-card {
    gap: 16px;
  }
}

// 分析区块
.analysis-block {
  .block-title {
    font-size: 15px;
    font-weight: 600;
    color: $text-dark;
    margin: 0 0 12px 0;
  }
}

// 迷你图谱
.mini-graph-wrapper {
  background: linear-gradient(135deg, #0a1628 0%, #1a2a3a 100%);
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
    color: $text-muted;
    gap: 12px;

    .el-icon {
      font-size: 36px;
      opacity: 0.5;
    }

    p {
      margin: 0;
      font-size: 13px;
      text-align: center;
      line-height: 1.6;
      max-width: 280px;
    }
  }
}

// 诊断卡片
.diagnosis-card {
  padding: 16px;
  border-radius: 12px;
  border: 1px solid $border-light;

  &.syndrome-card {
    background: #fdf2f8;
    border-color: #fce7f3;

    .syndrome-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 10px;

      .syndrome-tag {
        display: inline-block;
        padding: 8px 20px;
        background: linear-gradient(135deg, $rose, #9d174d);
        color: #fff;
        border-radius: 24px;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.25s;

        &:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 16px rgba(185, 28, 28, 0.35);
        }
      }
    }

    .diagnosis-basis {
      margin: 0;
      font-size: 13px;
      color: #6b7280;
      line-height: 1.7;
    }
  }

  &.formula-card {
    background: #eff6ff;
    border-color: #dbeafe;

    .formula-header {
      margin-bottom: 12px;

      .formula-tag {
        display: inline-block;
        padding: 8px 20px;
        background: linear-gradient(135deg, $indigo, #4f46e5);
        color: #fff;
        border-radius: 24px;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.25s;

        &:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 16px rgba(99, 102, 241, 0.35);
        }
      }
    }

    .herb-list {
      margin-bottom: 12px;
      line-height: 1.8;

      .herb-label {
        font-size: 13px;
        color: $text-muted;
        font-weight: 500;
      }

      .herb-tag {
        font-size: 14px;
        color: $emerald;
        font-weight: 500;
        cursor: pointer;
        transition: color 0.2s;

        &:hover {
          color: #059669;
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
        color: #64748b;

        .evidence-title {
          font-weight: 600;
          color: #475569;
        }
      }
    }
  }

  .no-result {
    color: $text-muted;
    font-size: 14px;
    font-style: italic;
  }
}

// 教学笔记
.note-textarea {
  :deep(.el-textarea__inner) {
    border-style: dashed;
    border-color: #cbd5e1;
    background: #fafbfc;
    font-size: 14px;
    line-height: 1.7;

    &:focus {
      border-color: $indigo;
      border-style: dashed;
    }
  }
}

// ==================== 历史病例 ====================
.case-history {
  background: $card-bg;
  border-radius: $card-radius;
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.07);
  padding: 20px 24px;

  .history-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;

    h3 {
      margin: 0;
      font-size: 16px;
      color: $text-dark;
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
      background: #cbd5e1;
      border-radius: 4px;
    }
  }

  .history-card {
    min-width: 200px;
    max-width: 220px;
    padding: 14px;
    border: 2px solid $border-light;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.25s;
    flex-shrink: 0;
    background: #fafbfc;

    &:hover {
      transform: translateY(-3px);
      box-shadow: 0 6px 18px rgba(0, 0, 0, 0.1);
    }

    &.active {
      border-color: $indigo;
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
      background: #eef2ff;
    }

    .hc-header {
      display: flex;
      justify-content: space-between;
      margin-bottom: 10px;

      .hc-id {
        font-size: 12px;
        color: $text-muted;
        font-family: monospace;
      }

      .hc-date {
        font-size: 11px;
        color: #a1a1aa;
      }
    }

    .hc-body {
      .hc-item {
        margin-bottom: 6px;

        .hc-label {
          display: block;
          font-size: 11px;
          color: $text-muted;
          margin-bottom: 2px;
        }

        .hc-value {
          font-size: 13px;
          color: $text-dark;
          line-height: 1.4;
        }

        .syndrome-name {
          color: $rose;
          font-weight: 500;
        }
      }
    }
  }

  .history-empty,
  .history-loading {
    text-align: center;
    padding: 16px 0;
    color: $text-muted;

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
  margin-top: -800px;
  
  @media (max-width: 1200px) {
    margin-top: -1020px;
  }
}
</style>