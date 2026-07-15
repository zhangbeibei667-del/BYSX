<template>
  <div class="front-index">
    <!-- 1. 欢迎首屏横幅 -->
    <div class="welcome-banner">
      <div class="banner-content">
        <p class="banner-en-sub">TRADITIONAL CHINESE MEDICINE AGENT</p>
        <h1 class="banner-title">中医药诊疗智能体</h1>
        <p class="banner-subtitle">基于知识图谱的中医药学习与教学辅助平台</p>
        <div class="banner-capabilities">
          <span class="cap-kg">知识图谱驱动</span>
          <i></i>
          <span class="cap-rag">RAG 智能检索</span>
          <i></i>
          <span class="cap-case">病例辅助教学</span>
        </div>
      </div>
    </div>
    
    <!-- 2. 核心功能特性 -->
    <div class="features-section">
      <p class="section-en-title">SEASONAL WELLNESS</p>
      <h2 class="section-title">核心功能特性</h2>
      <div class="features-grid">
        <div class="feature-card card-spring" @click="goToChat">
          <div class="feature-icon">
            <el-icon><ChatDotRound /></el-icon>
          </div>
          <h3>智能问答</h3>
          <p>基于 RAG 和 Agent 的流式对话，支持症状咨询、方剂查询、药材辨析</p>
        </div>

        <div class="feature-card card-summer" @click="goToGraph">
          <div class="feature-icon">
            <el-icon><DataAnalysis /></el-icon>
          </div>
          <h3>知识图谱</h3>
          <p>可视化展示药材、方剂、症状、证候间的复杂关系，支持路径查询</p>
        </div>

        <div class="feature-card card-autumn" @click="goToCaseStudy">
          <div class="feature-icon">
            <el-icon><Notebook /></el-icon>
          </div>
          <h3>病例教学</h3>
          <p>病例录入与分析，自动匹配证候和方剂，辅助中医临床教学</p>
        </div>

        <div class="feature-card card-winter" @click="goToHistory">
          <div class="feature-icon">
            <el-icon><Clock /></el-icon>
          </div>
          <h3>历史记录</h3>
          <p>统一管理问答对话、收藏知识和教学病例，回顾学习轨迹</p>
        </div>
      </div>
    </div>
    
    <!-- 3. 热门推荐 -->
    <div class="recommendations-section">
      <p class="section-en-title">FEATURED HERBS</p>
      <h2 class="section-title">热门知识推荐</h2>
      <div class="recommendations-outer">
        <!-- 标签栏 -->
        <div class="card-tabs-bar">
          <div class="tabs-pill-track">
            <span
              v-for="tab in recommendationTabs"
              :key="tab.name"
              class="tabs-pill"
              :class="{ active: activeTab === tab.name }"
              @click="activeTab = tab.name"
            >{{ tab.label }}</span>
          </div>
        </div>

        <!-- 加载中 -->
        <div v-if="loadingPrescriptions || loadingHerbs || loadingSymptoms" class="loading-content">
          <div class="loading-spinner"><el-icon><Loading /></el-icon></div>
          <p>正在加载数据...</p>
        </div>

        <!-- 空状态 -->
        <div v-else-if="activeTab === 'prescriptions' && recommendedPrescriptions.length === 0" class="empty-content">
          <el-empty description="暂无方剂数据" />
        </div>
        <div v-else-if="activeTab === 'herbs' && recommendedHerbs.length === 0" class="empty-content">
          <el-empty description="暂无药材数据" />
        </div>
        <div v-else-if="activeTab === 'symptoms' && recommendedSymptoms.length === 0" class="empty-content">
          <el-empty description="暂无症状数据" />
        </div>

        <!-- 方剂列表 -->
        <div v-show="activeTab === 'prescriptions'" class="recommendations-list">
          <div
            v-for="item in recommendedPrescriptions"
            :key="item.id"
            class="recommendation-item herb-card-greens"
          >
            <div class="card-big-char">方</div>
            <h4>{{ item.name }}</h4>
            <p class="item-desc">{{ item.description }}</p>
            <div class="item-tags">
              <el-tag size="small" class="tag-green">{{ item.category }}</el-tag>
              <el-tag size="small" class="tag-earth">{{ item.source }}</el-tag>
            </div>
            <div class="card-arrow" @click.stop="viewDetail('prescription', item.id)">
              <el-icon><ArrowRight /></el-icon>
            </div>
          </div>
        </div>

        <!-- 药材列表 -->
        <div v-show="activeTab === 'herbs'" class="recommendations-list">
          <div
            v-for="item in recommendedHerbs"
            :key="item.id"
            class="recommendation-item herb-card-yellow"
          >
            <div class="card-big-char">药</div>
            <h4>{{ item.name }}</h4>
            <p class="item-desc">{{ item.description }}</p>
            <div class="item-tags">
              <el-tag size="small" class="tag-pink">{{ item.nature_and_flavor }}</el-tag>
              <el-tag size="small" class="tag-olive">{{ item.efficacy }}</el-tag>
            </div>
            <div class="card-arrow" @click.stop="viewDetail('herb', item.id)">
              <el-icon><ArrowRight /></el-icon>
            </div>
          </div>
        </div>

        <!-- 症状列表 -->
        <div v-show="activeTab === 'symptoms'" class="recommendations-list">
          <div
            v-for="item in recommendedSymptoms"
            :key="item.id"
            class="recommendation-item herb-card-pink"
          >
            <div class="card-big-char">症</div>
            <h4>{{ item.name }}</h4>
            <p class="item-desc">{{ item.description }}</p>
            <div class="item-tags">
              <el-tag size="small" class="tag-warm">{{ item.category }}</el-tag>
            </div>
            <div class="card-arrow" @click.stop="viewDetail('symptom', item.id)">
              <el-icon><ArrowRight /></el-icon>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 4. 平台统计 -->
    <div class="stats-section">
      <div class="stats-dark-wrap">
        <div class="container-wrap">
          <p class="section-en-title dark-en">THE ART OF TCM</p>
          <h2 class="section-title dark-title">平台数据概览</h2>
          <div class="stats-grid">
            <div class="stat-card" @click="goToAdminHerbs">
              <div class="stat-icon stat-herb">
                <el-icon><Orange /></el-icon>
              </div>
              <div class="stat-info">
                <h3 v-if="loadingStats">-</h3>
                <h3 v-else>{{ formatNumber(stats.totalHerbs) }}</h3>
                <p>药材数量</p>
              </div>
            </div>

            <div class="stat-card" @click="goToAdminPrescriptions">
              <div class="stat-icon stat-pres">
                <el-icon><Document /></el-icon>
              </div>
              <div class="stat-info">
                <h3 v-if="loadingStats">-</h3>
                <h3 v-else>{{ formatNumber(stats.totalPrescriptions) }}</h3>
                <p>方剂数量</p>
              </div>
            </div>

            <div class="stat-card" @click="goToAdminRelations">
              <div class="stat-icon stat-rel">
                <el-icon><Connection /></el-icon>
              </div>
              <div class="stat-info">
                <h3 v-if="loadingStats">-</h3>
                <h3 v-else>{{ formatNumber(stats.totalRelations) }}</h3>
                <p>关系数量</p>
              </div>
            </div>

            <div class="stat-card" @click="goToAdminRecords">
              <div class="stat-icon stat-msg">
                <el-icon><Message /></el-icon>
              </div>
              <div class="stat-info">
                <h3 v-if="loadingStats">-</h3>
                <h3 v-else>{{ formatNumber(stats.totalQuestions) }}</h3>
                <p>问答记录</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store'
import {
  ChatDotRound,
  DataAnalysis,
  Notebook,
  Document,
  Orange,
  Connection,
  Message,
  Loading,
  Setting,
  Clock,
  ArrowRight
} from '@element-plus/icons-vue'
import { entityApi, statsApi } from '@/api'



const router = useRouter()
const userStore = useUserStore()
userStore.checkAuth()
const isAdmin = computed(() => userStore.userInfo.role === 'admin')
const activeTab = ref('prescriptions')
const recommendationTabs = [
  { name: 'prescriptions', label: '常用方剂' },
  { name: 'herbs', label: '常用药材' },
  { name: 'symptoms', label: '常见症状' }
]


const loadingStats = ref(true)
const loadingPrescriptions = ref(true)
const loadingHerbs = ref(true)
const loadingSymptoms = ref(true)

const stats = ref({
  totalHerbs: 0,
  totalPrescriptions: 0,
  totalRelations: 0,
  totalQuestions: 0
})

const recommendedPrescriptions = ref<any[]>([])
const recommendedHerbs = ref<any[]>([])
const recommendedSymptoms = ref<any[]>([])

onMounted(() => {
  loadStats()
  loadRecommendedPrescriptions()
  loadRecommendedHerbs()
  loadRecommendedSymptoms()
})

const loadStats = async () => {
  try {
    loadingStats.value = true
    try {
      const res: any = await statsApi.getPlatformStats()
      const data = res?.data || res
      if (data && typeof data === 'object') {
        stats.value = {
          totalHerbs: data.totalHerbs || 0,
          totalPrescriptions: data.totalPrescriptions || 0,
          totalRelations: data.totalRelations || 0,
          totalQuestions: data.totalQuestions || 0
        }
        return
      }
    } catch (apiError) {
      console.log('statsApi 未就绪，使用模拟数据:', apiError)
    }
    useMockStats()
  } catch (error) {
    console.error('加载统计数据失败:', error)
    useMockStats()
  } finally {
    loadingStats.value = false
  }
}

const useMockStats = () => {
  stats.value = {
    totalHerbs: 156,
    totalPrescriptions: 89,
    totalRelations: 234,
    totalQuestions: 567
  }
}

const loadRecommendedPrescriptions = async () => {
  try {
    loadingPrescriptions.value = true
    try {
      const res: any = await statsApi.getPopularEntities('prescriptions', 4)
      const data = res?.data || res
      if (Array.isArray(data) && data.length > 0) {
        recommendedPrescriptions.value = data
        return
      }
    } catch { }
    try {
      const response = await entityApi.prescriptions.list({ page: 1, pageSize: 4, sortBy: 'usage_count', sortOrder: 'desc' })
      if (response && response.data && response.data.length > 0) {
        recommendedPrescriptions.value = response.data
        return
      }
    } catch { }
    useMockPrescriptions()
  } catch (error) {
    console.error('加载推荐方剂失败:', error)
    useMockPrescriptions()
  } finally {
    loadingPrescriptions.value = false
  }
}

const useMockPrescriptions = () => {
  recommendedPrescriptions.value = [
    { id: 'F001', name: '归脾汤', description: '益气补血、健脾养心，主治心脾两虚、气血不足证', category: '补益剂', source: '《济生方》' },
    { id: 'F002', name: '麻黄汤', description: '发汗解表、宣肺平喘，主治外感风寒表实证', category: '解表剂', source: '《伤寒论》' },
    { id: 'F003', name: '小柴胡汤', description: '和解少阳，主治伤寒少阳证', category: '和解剂', source: '《伤寒论》' },
    { id: 'F004', name: '补中益气汤', description: '补中益气、升阳举陷，主治脾虚气陷证', category: '补益剂', source: '《脾胃论》' }
  ]
}

const loadRecommendedHerbs = async () => {
  try {
    loadingHerbs.value = true
    try {
      const res: any = await statsApi.getPopularEntities('herbs', 4)
      const data = res?.data || res
      if (Array.isArray(data) && data.length > 0) {
        recommendedHerbs.value = data
        return
      }
    } catch { }
    try {
      const response = await entityApi.herbs.list({ page: 1, pageSize: 4, sortBy: 'usage_count', sortOrder: 'desc' })
      if (response && response.data && response.data.length > 0) {
        recommendedHerbs.value = response.data
        return
      }
    } catch { }
    useMockHerbs()
  } catch (error) {
    console.error('加载推荐药材失败:', error)
    useMockHerbs()
  } finally {
    loadingHerbs.value = false
  }
}

const useMockHerbs = () => {
  recommendedHerbs.value = [
    { id: 'H001', name: '人参', description: '大补元气、复脉固脱、补脾益肺、生津养血', nature_and_flavor: '甘、微苦，微温', efficacy: '补气固脱' },
    { id: 'H002', name: '黄芪', description: '补气升阳、固表止汗、利水消肿、生津养血', nature_and_flavor: '甘，微温', efficacy: '补气固表' },
    { id: 'H003', name: '当归', description: '补血活血、调经止痛、润肠通便', nature_and_flavor: '甘、辛，温', efficacy: '补血活血' },
    { id: 'H004', name: '茯苓', description: '利水渗湿、健脾宁心', nature_and_flavor: '甘、淡，平', efficacy: '利水渗湿' }
  ]
}

const loadRecommendedSymptoms = async () => {
  try {
    loadingSymptoms.value = true
    try {
      const res: any = await statsApi.getPopularEntities('symptoms', 4)
      const data = res?.data || res
      if (Array.isArray(data) && data.length > 0) {
        recommendedSymptoms.value = data
        return
      }
    } catch { }
    try {
      const response = await entityApi.symptoms.list({ page: 1, pageSize: 4, sortBy: 'frequency', sortOrder: 'desc' })
      if (response && response.data && response.data.length > 0) {
        recommendedSymptoms.value = response.data
        return
      }
    } catch { }
    useMockSymptoms()
  } catch (error) {
    console.error('加载推荐症状失败:', error)
    useMockSymptoms()
  } finally {
    loadingSymptoms.value = false
  }
}

const useMockSymptoms = () => {
  recommendedSymptoms.value = [
    { id: 'S001', name: '失眠', description: '难以入眠、睡中易醒、早醒、睡眠质量差', category: '心神症状' },
    { id: 'S002', name: '畏寒', description: '怕冷，尤以背部、四肢为甚', category: '寒热症状' },
    { id: 'S003', name: '咳嗽', description: '肺气上逆作声，咯吐痰涎', category: '肺系症状' },
    { id: 'S004', name: '腹泻', description: '大便次数增多，粪质稀薄或完全不化', category: '脾胃症状' }
  ]
}

const goToChat = () => router.push('/chat')
const goToGraph = () => router.push('/graph')
const goToCaseStudy = () => router.push('/case-study')
const goToHistory = () => router.push('/history')

const goToAdminHerbs = () => { if (isAdmin.value) router.push('/admin/herbs') }
const goToAdminPrescriptions = () => { if (isAdmin.value) router.push('/admin/prescriptions') }
const goToAdminRelations = () => { if (isAdmin.value) router.push('/admin/relations') }
const goToAdminRecords = () => { if (isAdmin.value) router.push('/admin/records') }

const formatNumber = (num: number) => num.toLocaleString()

const viewDetail = (type: string, id: string) => {
  let entityName = ''
  if (type === 'prescription') entityName = recommendedPrescriptions.value.find(p => p.id === id)?.name || ''
  if (type === 'herb') entityName = recommendedHerbs.value.find(h => h.id === id)?.name || ''
  if (type === 'symptom') entityName = recommendedSymptoms.value.find(s => s.id === id)?.name || ''
  if (entityName) router.push(`/graph?search=${encodeURIComponent(entityName)}`)
  else router.push('/graph')
}
</script>

<style scoped lang="scss">
$cream-bg: #f7f3eb;
$light-cream: #faf6ef;
$dark-green: #2a4030;
$mid-green: #466350;
$soft-gold: #c8a86e;
$text-dark: #2c3630;
$text-light: #6b7a72;
$card-border: rgba(110, 135, 120, 0.12);

$spring-card: #e8f1e5;
$summer-card: #fff8e0;
$autumn-card: #f8ede3;
$winter-card: #e6ecef;

$herb-green: #e4efe4;
$herb-yellow: #fff7e0;
$herb-pink: #f9e6e6;

.front-index {
  background-color: $cream-bg;
  // 增加顶部内边距，避开 sticky 导航栏的高度
  padding-top: 0px;  // ✅ 新增：给导航栏留出空间
  padding-bottom: 24px;

  .container-wrap {
    max-width: 1800px;
    margin: 0 auto;
    width: 100%;
    padding: 0 32px;
  }

  .section-en-title {
    text-align: center;
    font-size: 13px;
    color: $text-light;
    letter-spacing: 2px;
    margin: 0 0 6px;
  }

  .section-title {
    text-align: center;
    margin: 0 0 40px;
    color: $text-dark;
    font-size: 26px;
    font-weight: 500;
    position: relative;
    &::after {
      content: '';
      display: block;
      width: 70px;
      height: 1px;
      background: $soft-gold;
      margin: 14px auto 0;
    }
  }

  .welcome-banner {
    background: $light-cream;
    border-radius: 18px;
    padding: 48px 20px;
    margin: 0 0 70px;
    text-align: center;
    border: 1px solid $card-border;
    .banner-content {
      max-width: 900px;
      margin: 0 auto;
      .banner-en-sub {
        font-size: 14px;
        letter-spacing: 3px;
        color: $text-light;
        margin: 0 0 10px;
      }
      .banner-title {
        font-size: 40px;
        margin: 0 0 16px 0;
        color: $dark-green;
        font-weight: 500;
      }
      .banner-subtitle {
        font-size: 17px;
        color: $text-light;
        margin-bottom: 20px;
      }
      .banner-capabilities {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 20px;
        margin-top: 0;

        span {
          font-size: 15px;
          font-weight: 500;
          background: rgba(70, 99, 80, 0.1);
          border: 1px solid rgba(70, 99, 80, 0.25);
          border-radius: 22px;
          padding: 8px 22px;
          white-space: nowrap;
          color: $dark-green;
          &.cap-rag { background: rgba(200, 168, 110, 0.12); border-color: rgba(200, 168, 110, 0.35); color: #926f3e; }
          &.cap-case { background: rgba(130, 100, 70, 0.1); border-color: rgba(130, 100, 70, 0.3); color: #725439; }
        }

        i {
          width: 5px;
          height: 5px;
          background: $soft-gold;
          border-radius: 50%;
          flex-shrink: 0;
        }
      }
    }
  }

  .features-section {
    margin-bottom: 70px;
    .features-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 24px;
        .feature-card {
        border-radius: 14px;
        padding: 32px 20px;
        text-align: center;
        border: 1px solid $card-border;
        cursor: pointer;
        transition: transform 0.25s ease, box-shadow 0.25s ease;
        &:hover {
          transform: translateY(-4px);
          box-shadow: 0 8px 28px rgba(42, 64, 48, 0.14);
        }
        &.card-spring { background: $spring-card; }
        &.card-summer { background: $summer-card; }
        &.card-autumn { background: $autumn-card; }
        &.card-winter { background: $winter-card; }

        .feature-icon {
          width: 72px;
          height: 72px;
          background: rgba(70, 99, 80, 0.12);
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          margin: 0 auto 20px;
          .el-icon { font-size: 32px; color: $mid-green; }
        }
        h3 { margin: 0 0 14px 0; color: $text-dark; font-size: 19px; font-weight: 500; }
        p { color: $text-light; line-height: 1.6; margin: 0; font-size: 14px; }
      }
    }
  }
  
  .recommendations-section {
    margin-bottom: 70px;

    /* 白色外层容器 */
    .recommendations-outer {
      background: #fff;
      border-radius: 16px;
      border: 1px solid $card-border;
      box-shadow: 0 4px 24px rgba(42, 64, 48, 0.06);
      padding: 20px 20px 16px;

      .card-tabs-bar {
        margin-bottom: 16px;

        .tabs-pill-track {
          display: inline-flex;
          gap: 8px;

          .tabs-pill {
            padding: 4px 14px;
            border-radius: 16px;
            font-size: 16px;
            font-weight: 500;
            color: $text-light;
            cursor: pointer;
            transition: all 0.28s ease;
            white-space: nowrap;
            user-select: none;
            border: 1px solid transparent;

            &:hover { color: $dark-green; }

            &.active {
              background: $dark-green;
              color: #f7f3eb;
              border-color: $dark-green;
              box-shadow: 0 2px 8px rgba(42, 64, 48, 0.18);
            }
          }
        }
      }

      .recommendations-list {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;

        .recommendation-item {
          border-radius: 12px;
          padding: 16px;
          transition: transform 0.3s ease, box-shadow 0.3s ease;
          border: 1px solid $card-border;
          position: relative;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          height: 160px;

          &:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(42, 64, 48, 0.1);
          }

          &.herb-card-greens { background: $herb-green; }
          &.herb-card-yellow { background: $herb-yellow; }
          &.herb-card-pink { background: $herb-pink; }

          .card-big-char {
            position: absolute;
            top: 4px;
            right: 10px;
            font-size: 38px;
            opacity: 0.09;
            font-weight: 500;
            line-height: 1;
            pointer-events: none;
          }

          h4 {
            margin: 0 0 15px 0;
            color: $dark-green;
            font-size: 16px;
            font-weight: 700;
            flex-shrink: 0;
          }

          .item-desc {
            color: $text-light;
            font-size: 13px;
            line-height: 1.55;
            margin: 0;
            overflow: hidden;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            flex: 1;
            min-height: 0;
          }

          .item-tags {
            display: flex;
            gap: 4px;
            flex-wrap: wrap;
            flex-shrink: 0;
            margin-top: auto;

            .el-tag {
              border: none;
              font-size: 11px;
              padding: 1px 5px;
              border-radius: 4px;

              &.tag-green { background: rgba(88, 130, 100, 0.15); color: #3c6048; }
              &.tag-earth { background: rgba(200, 168, 110, 0.18); color: #8c6747; }
              &.tag-pink { background: rgba(216, 178, 178, 0.2); color: #945b5b; }
              &.tag-olive { background: rgba(160, 170, 130, 0.18); color: #5c6642; }
              &.tag-warm { background: rgba(212, 182, 140, 0.18); color: #916c3e; }
            }
          }

          .card-arrow {
            position: absolute;
            bottom: 12px;
            right: 12px;
            width: 24px;
            height: 24px;
            background: rgba(42, 64, 48, 0.1);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: background 0.2s, transform 0.2s;
            .el-icon { font-size: 12px; color: $dark-green; }
            &:hover {
              background: rgba(42, 64, 48, 0.2);
              transform: translateX(2px);
            }
          }
        }
      }

      .loading-content, .empty-content {
        text-align: center;
        padding: 50px 20px;
        .loading-spinner {
          display: inline-block;
          animation: spin 1s linear infinite;
          font-size: 32px;
          color: $mid-green;
          margin-bottom: 14px;
        }
        p { color: $text-light; margin: 0; }
      }
    }
  }
  
  .stats-section {
    width: 100%;
    margin-top: 20px;
    .stats-dark-wrap {
      background: $dark-green;
      padding: 60px 0;
      .dark-en { color: rgba(255,255,255,0.6); }
      .dark-title { color: #f7f3eb; &::after { background: rgba(200, 168, 110, 0.6); } }
      .stats-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 24px;
        .stat-card {
          background: rgba(255,255,255,0.08);
          border: 1px solid rgba(255,255,255,0.12);
          border-radius: 14px;
          padding: 24px;
          display: flex;
          align-items: center;
          gap: 20px;
          cursor: pointer;
          transition: transform 0.3s ease, background 0.3s;
          &:hover { transform: translateY(-5px); background: rgba(255,255,255,0.14); }
          .stat-icon {
            width: 60px;
            height: 60px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            &.stat-herb { background: rgba(200, 168, 110, 0.22); .el-icon { color: $soft-gold; } }
            &.stat-pres { background: rgba(170, 195, 170, 0.2); .el-icon { color: #a8c4a8; } }
            &.stat-rel { background: rgba(140, 180, 190, 0.2); .el-icon { color: #94c0ca; } }
            &.stat-msg { background: rgba(220, 190, 160, 0.2); .el-icon { color: #d8b898; } }
            .el-icon { font-size: 28px; }
          }
          .stat-info {
            h3 { margin: 0 0 6px 0; font-size: 28px; color: #f7f3eb; font-weight: 500; }
            p { margin: 0; color: rgba(255,255,255,0.65); font-size: 14px; }
          }
        }
      }
    }
  }
}

@media (max-width: 992px) {
  .front-index {
    .features-section .features-grid,
    .recommendations-section .tcm-tabs .recommendations-list,
    .stats-section .stats-dark-wrap .stats-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }
}

@media (max-width: 768px) {
  .front-index {
    padding-top: 70px; // 移动端导航栏稍矮，减少一些内边距
    
    .features-section .features-grid,
    .recommendations-section .tcm-tabs .recommendations-list,
    .stats-section .stats-dark-wrap .stats-grid {
      grid-template-columns: 1fr;
    }
    .welcome-banner .banner-content .banner-title { font-size: 32px; }
  }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>