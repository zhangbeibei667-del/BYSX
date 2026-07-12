<template>
  <div class="front-index">
    <!-- 1. 欢迎首屏横幅 -->
    <div class="welcome-banner">
      <div class="banner-content">
        <p class="banner-en-sub">TRADITIONAL CHINESE MEDICINE AGENT</p>
        <h1 class="banner-title">中医药诊疗智能体</h1>
        <p class="banner-subtitle">基于知识图谱的中医药学习与教学辅助平台</p>
        <div class="banner-actions">
          <el-button size="large" @click="goToChat" class="tcm-btn primary-tcm">
            <el-icon><ChatDotRound /></el-icon>
            开始问答
          </el-button>
          <el-button size="large" @click="goToGraph" class="tcm-btn green-tcm">
            <el-icon><DataAnalysis /></el-icon>
            知识图谱
          </el-button>
          <el-button size="large" @click="goToCaseStudy" class="tcm-btn earth-tcm">
            <el-icon><Notebook /></el-icon>
            病例教学
          </el-button>
          <el-button size="large" @click="goToHistory" class="tcm-btn brown-tcm">
            <el-icon><Clock /></el-icon>
            历史记录
          </el-button>
          <el-button size="large" @click="goToAdmin" class="tcm-btn dark-tcm admin-btn">
            <el-icon><Setting /></el-icon>
            后台管理
          </el-button>
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
      <el-tabs v-model="activeTab" type="border-card" class="tcm-tabs">
        <el-tab-pane label="常用方剂" name="prescriptions">
          <div v-if="loadingPrescriptions" class="loading-content">
            <div class="loading-spinner"><el-icon><Loading /></el-icon></div>
            <p>正在加载方剂数据...</p>
          </div>
          <div v-else-if="recommendedPrescriptions.length === 0" class="empty-content">
            <el-empty description="暂无方剂数据" />
          </div>
          <div v-else class="recommendations-list">
            <div
              v-for="item in recommendedPrescriptions"
              :key="item.id"
              class="recommendation-item herb-card-greens"
              @click="viewDetail('prescription', item.id)"
            >
              <div class="card-big-char">方</div>
              <h4>{{ item.name }}</h4>
              <p>{{ item.description }}</p>
              <div class="item-tags">
                <el-tag size="small" class="tag-green">{{ item.category }}</el-tag>
                <el-tag size="small" class="tag-earth">{{ item.source }}</el-tag>
              </div>
            </div>
          </div>
        </el-tab-pane>
        
        <el-tab-pane label="常用药材" name="herbs">
          <div v-if="loadingHerbs" class="loading-content">
            <div class="loading-spinner"><el-icon><Loading /></el-icon></div>
            <p>正在加载药材数据...</p>
          </div>
          <div v-else-if="recommendedHerbs.length === 0" class="empty-content">
            <el-empty description="暂无药材数据" />
          </div>
          <div v-else class="recommendations-list">
            <div
              v-for="item in recommendedHerbs"
              :key="item.id"
              class="recommendation-item herb-card-yellow"
              @click="viewDetail('herb', item.id)"
            >
              <div class="card-big-char">药</div>
              <h4>{{ item.name }}</h4>
              <p>{{ item.description }}</p>
              <div class="item-tags">
                <el-tag size="small" class="tag-pink">{{ item.nature_and_flavor }}</el-tag>
                <el-tag size="small" class="tag-olive">{{ item.efficacy }}</el-tag>
              </div>
            </div>
          </div>
        </el-tab-pane>
        
        <el-tab-pane label="常见症状" name="symptoms">
          <div v-if="loadingSymptoms" class="loading-content">
            <div class="loading-spinner"><el-icon><Loading /></el-icon></div>
            <p>正在加载症状数据...</p>
          </div>
          <div v-else-if="recommendedSymptoms.length === 0" class="empty-content">
            <el-empty description="暂无症状数据" />
          </div>
          <div v-else class="recommendations-list">
            <div
              v-for="item in recommendedSymptoms"
              :key="item.id"
              class="recommendation-item herb-card-pink"
              @click="viewDetail('symptom', item.id)"
            >
              <div class="card-big-char">症</div>
              <h4>{{ item.name }}</h4>
              <p>{{ item.description }}</p>
              <div class="item-tags">
                <el-tag size="small" class="tag-warm">{{ item.category }}</el-tag>
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
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

    <!-- 人机验证弹窗 -->
    <CaptchaVerify ref="captchaRef" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
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
  Clock
} from '@element-plus/icons-vue'
import { entityApi, statsApi } from '@/api'
import CaptchaVerify from '@/components/Common/CaptchaVerify.vue'

const router = useRouter()
const activeTab = ref('prescriptions')
const captchaRef = ref<InstanceType<typeof CaptchaVerify>>()

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

const goToAdmin = async () => {
  const passed = await captchaRef.value?.requireVerify()
  if (passed) router.push('/admin/herbs')
}

const goToAdminHerbs = async () => {
  const passed = await captchaRef.value?.requireVerify()
  if (passed) router.push('/admin/herbs')
}

const goToAdminPrescriptions = async () => {
  const passed = await captchaRef.value?.requireVerify()
  if (passed) router.push('/admin/prescriptions')
}

const goToAdminRelations = async () => {
  const passed = await captchaRef.value?.requireVerify()
  if (passed) router.push('/admin/relations')
}

const goToAdminRecords = async () => {
  const passed = await captchaRef.value?.requireVerify()
  if (passed) router.push('/admin/records')
}

const viewDetail = (type: string, id: string) => {
  let entityName = ''
  if (type === 'prescription') entityName = recommendedPrescriptions.value.find(p => p.id === id)?.name || ''
  if (type === 'herb') entityName = recommendedHerbs.value.find(h => h.id === id)?.name || ''
  if (type === 'symptom') entityName = recommendedSymptoms.value.find(s => s.id === id)?.name || ''
  if (entityName) router.push(`/graph?search=${encodeURIComponent(entityName)}`)
  else router.push('/graph')
}

const formatNumber = (num: number) => num.toLocaleString()
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
  padding-top: 1400px;  // ✅ 新增：给导航栏留出空间
  padding-bottom: 24px;

  .container-wrap {
    max-width: 1440px;
    margin: 0 auto;
    width: 100%;
    padding: 0 24px;
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
        margin-bottom: 36px;
      }
      .banner-actions {
        display: flex;
        gap: 14px;
        justify-content: center;
        flex-wrap: wrap;
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
          &.green-tcm {
            background: rgba(100, 145, 110, 0.08);
            color: $mid-green;
            border-color: rgba(100, 145, 110, 0.2);
            &:hover { background: #588264; color: #fff; }
          }
          &.earth-tcm {
            background: rgba(200, 168, 110, 0.1);
            color: #926f3e;
            border-color: rgba(200, 168, 110, 0.25);
            &:hover { background: $soft-gold; color: #fff; }
          }
          &.brown-tcm {
            background: rgba(130, 100, 70, 0.08);
            color: #725439;
            border-color: rgba(130, 100, 70, 0.2);
            &:hover { background: #8c6747; color: #fff; }
          }
          &.dark-tcm {
            background: rgba(42, 64, 48, 0.08);
            color: $dark-green;
            border-color: rgba(42, 64, 48, 0.2);
            &:hover { background: $dark-green; color: #fff; }
          }
        }
        .admin-btn {
          border-style: dashed;
          opacity: 0.9;
          &:hover { opacity: 1; border-style: solid; }
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
        cursor: pointer;
        transition: transform 0.3s ease;
        border: 1px solid $card-border;
        &:hover { transform: translateY(-6px); }
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
    .tcm-tabs {
      :deep(.el-tabs__content) {
        padding: 24px;
      }
      :deep(.el-tabs__header) { margin-bottom: 16px; padding: 0 24px; }
      :deep(.el-tabs__nav-wrap::after) { background: $card-border; }
      :deep(.el-tabs__item) { color: $text-light; font-size: 16px; &.is-active { color: $dark-green; } &.is-active::after { background: $soft-gold; } }
      
      .recommendations-list {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 20px;
        .recommendation-item {
          border-radius: 12px;
          padding: 20px;
          cursor: pointer;
          transition: transform 0.3s ease;
          border: 1px solid $card-border;
          position: relative;
          overflow: hidden;
          &:hover { transform: translateY(-4px); }
          .card-big-char {
            position: absolute;
            top: 8px;
            right: 14px;
            font-size: 52px;
            opacity: 0.12;
            font-weight: 500;
          }
          &.herb-card-greens { background: $herb-green; }
          &.herb-card-yellow { background: $herb-yellow; }
          &.herb-card-pink { background: $herb-pink; }
          h4 { margin: 0 0 10px 0; color: $dark-green; font-size: 18px; font-weight: 500; }
          p { color: $text-light; font-size: 13px; line-height: 1.5; margin: 0 0 14px 0; }
          .item-tags {
            display: flex;
            gap: 8px;
            .el-tag { border: none; font-size: 12px; padding: 2px 6px; border-radius: 4px;
              &.tag-green { background: rgba(88, 130, 100, 0.15); color: #3c6048; }
              &.tag-earth { background: rgba(200, 168, 110, 0.18); color: #8c6747; }
              &.tag-pink { background: rgba(216, 178, 178, 0.2); color: #945b5b; }
              &.tag-olive { background: rgba(160, 170, 130, 0.18); color: #5c6642; }
              &.tag-warm { background: rgba(212, 182, 140, 0.18); color: #916c3e; }
            }
          }
        }
      }
      .loading-content, .empty-content { text-align: center; padding: 50px 20px;
        .loading-spinner { display: inline-block; animation: spin 1s linear infinite; font-size: 32px; color: $mid-green; margin-bottom: 14px; }
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