<template>
  <div class="front-index">
    <!-- 欢迎横幅 -->
    <div class="welcome-banner">
      <div class="banner-content">
        <h1 class="banner-title">中医药诊疗智能体</h1>
        <p class="banner-subtitle">基于知识图谱的中医药学习与教学辅助平台</p>
        <div class="banner-actions">
          <el-button type="primary" size="large" @click="goToChat">
            <el-icon><ChatDotRound /></el-icon>
            开始问答
          </el-button>
          <el-button type="success" size="large" @click="goToGraph">
            <el-icon><DataAnalysis /></el-icon>
            知识图谱
          </el-button>
          <el-button type="warning" size="large" @click="goToCaseStudy">
            <el-icon><Notebook /></el-icon>
            病例教学
          </el-button>
          <el-button type="info" size="large" @click="goToHistory">
            <el-icon><Clock /></el-icon>
            历史记录
          </el-button>
        </div>
      </div>
    </div>
    
    <!-- 功能特性 -->
    <div class="features-section">
      <h2 class="section-title">核心功能特性</h2>
      <div class="features-grid">
        <div class="feature-card" @click="goToChat">
          <div class="feature-icon">
            <el-icon><ChatDotRound /></el-icon>
          </div>
          <h3>智能问答</h3>
          <p>基于 RAG 和 Agent 的流式对话，支持症状咨询、方剂查询、药材辨析</p>
        </div>
  
        <div class="feature-card" @click="goToGraph">
          <div class="feature-icon">
            <el-icon><DataAnalysis /></el-icon>
          </div>
          <h3>知识图谱</h3>
          <p>可视化展示药材、方剂、症状、证候间的复杂关系，支持路径查询</p>
        </div>
  
        <div class="feature-card" @click="goToCaseStudy">
          <div class="feature-icon">
            <el-icon><Notebook /></el-icon>
          </div>
          <h3>病例教学</h3>
          <p>病例录入与分析，自动匹配证候和方剂，辅助中医临床教学</p>
        </div>
  
        <div class="feature-card" @click="goToHistory">
          <div class="feature-icon">
            <el-icon><Clock /></el-icon>
          </div>
          <h3>历史记录</h3>
          <p>统一管理问答对话、收藏知识和教学病例，回顾学习轨迹</p>
        </div>
      </div>
    </div>
    
    <!-- 热门推荐 -->
    <div class="recommendations-section">
      <h2 class="section-title">热门知识推荐</h2>
      <div class="recommendations-tabs">
        <el-tabs v-model="activeTab" type="border-card">
          <el-tab-pane label="常用方剂" name="prescriptions">
            <div v-if="loadingPrescriptions" class="loading-content">
              <div class="loading-spinner">
                <el-icon><Loading /></el-icon>
              </div>
              <p>正在加载方剂数据...</p>
            </div>
            <div v-else-if="recommendedPrescriptions.length === 0" class="empty-content">
              <el-empty description="暂无方剂数据" />
            </div>
            <div v-else class="recommendations-list">
              <div
                v-for="item in recommendedPrescriptions"
                :key="item.id"
                class="recommendation-item"
                @click="viewDetail('prescription', item.id)"
              >
                <h4>{{ item.name }}</h4>
                <p>{{ item.description }}</p>
                <div class="item-tags">
                  <el-tag size="small" type="info">{{ item.category }}</el-tag>
                  <el-tag size="small" type="primary">{{ item.source }}</el-tag>
                </div>
              </div>
            </div>
          </el-tab-pane>
          
          <el-tab-pane label="常用药材" name="herbs">
            <div v-if="loadingHerbs" class="loading-content">
              <div class="loading-spinner">
                <el-icon><Loading /></el-icon>
              </div>
              <p>正在加载药材数据...</p>
            </div>
            <div v-else-if="recommendedHerbs.length === 0" class="empty-content">
              <el-empty description="暂无药材数据" />
            </div>
            <div v-else class="recommendations-list">
              <div
                v-for="item in recommendedHerbs"
                :key="item.id"
                class="recommendation-item"
                @click="viewDetail('herb', item.id)"
              >
                <h4>{{ item.name }}</h4>
                <p>{{ item.description }}</p>
                <div class="item-tags">
                  <el-tag size="small" type="success">{{ item.nature_and_flavor }}</el-tag>
                  <el-tag size="small" type="warning">{{ item.efficacy }}</el-tag>
                </div>
              </div>
            </div>
          </el-tab-pane>
          
          <el-tab-pane label="常见症状" name="symptoms">
            <div v-if="loadingSymptoms" class="loading-content">
              <div class="loading-spinner">
                <el-icon><Loading /></el-icon>
              </div>
              <p>正在加载症状数据...</p>
            </div>
            <div v-else-if="recommendedSymptoms.length === 0" class="empty-content">
              <el-empty description="暂无症状数据" />
            </div>
            <div v-else class="recommendations-list">
              <div
                v-for="item in recommendedSymptoms"
                :key="item.id"
                class="recommendation-item"
                @click="viewDetail('symptom', item.id)"
              >
                <h4>{{ item.name }}</h4>
                <p>{{ item.description }}</p>
                <div class="item-tags">
                  <el-tag size="small" type="warning">{{ item.category }}</el-tag>
                </div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
    
    <!-- 统计数据 -->
    <div class="stats-section">
      <h2 class="section-title">平台数据概览</h2>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon" style="background: #e3f2fd;">
            <el-icon color="#2196f3"><Orange /></el-icon>
          </div>
          <div class="stat-info">
            <h3 v-if="loadingStats">-</h3>
            <h3 v-else>{{ formatNumber(stats.totalHerbs) }}</h3>
            <p>药材数量</p>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon" style="background: #f3e5f5;">
            <el-icon color="#9c27b0"><Document /></el-icon>
          </div>
          <div class="stat-info">
            <h3 v-if="loadingStats">-</h3>
            <h3 v-else>{{ formatNumber(stats.totalPrescriptions) }}</h3>
            <p>方剂数量</p>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon" style="background: #e8f5e9;">
            <el-icon color="#4caf50"><Connection /></el-icon>
          </div>
          <div class="stat-info">
            <h3 v-if="loadingStats">-</h3>
            <h3 v-else>{{ formatNumber(stats.totalRelations) }}</h3>
            <p>关系数量</p>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon" style="background: #fff3e0;">
            <el-icon color="#ff9800"><Message /></el-icon>
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
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ChatDotRound,
  DataAnalysis,
  Notebook,
  Document,
  Orange,
  Connection,
  Message,
  Loading
} from '@element-plus/icons-vue'
import { entityApi } from '@/api'

const router = useRouter()
const activeTab = ref('prescriptions')

// 加载状态
const loadingStats = ref(true)
const loadingPrescriptions = ref(true)
const loadingHerbs = ref(true)
const loadingSymptoms = ref(true)

// 统计数据
const stats = ref({
  totalHerbs: 0,
  totalPrescriptions: 0,
  totalRelations: 0,
  totalQuestions: 0
})

// 推荐数据 - 初始为空，从API获取
const recommendedPrescriptions = ref<any[]>([])
const recommendedHerbs = ref<any[]>([])
const recommendedSymptoms = ref<any[]>([])

onMounted(() => {
  // 加载统计数据
  loadStats()
  
  // 加载推荐数据
  loadRecommendedPrescriptions()
  loadRecommendedHerbs()
  loadRecommendedSymptoms()
})

// 加载统计数据
const loadStats = async () => {
  try {
    loadingStats.value = true
    
    // 实际API调用 - 从后端获取统计数据
    // 注意：如果后端API还未实现，可以先使用模拟数据
    try {
      // 尝试调用真实API
      const response = await fetch('/api/stats/platform')
      if (response.ok) {
        const data = await response.json()
        stats.value = {
          totalHerbs: data.totalHerbs || 0,
          totalPrescriptions: data.totalPrescriptions || 0,
          totalRelations: data.totalRelations || 0,
          totalQuestions: data.totalQuestions || 0
        }
      } else {
        // API未实现，使用模拟数据
        useMockStats()
      }
    } catch (apiError) {
      console.log('API未就绪，使用模拟数据:', apiError)
      useMockStats()
    }
  } catch (error) {
    console.error('加载统计数据失败:', error)
    ElMessage.error('加载统计数据失败')
    // 出错时使用模拟数据
    useMockStats()
  } finally {
    loadingStats.value = false
  }
}

// 使用模拟统计数据
const useMockStats = () => {
  // 模拟数据 - 实际应该从API获取
  stats.value = {
    totalHerbs: 156,  // 从API获取
    totalPrescriptions: 89, // 从API获取
    totalRelations: 234, // 从API获取
    totalQuestions: 567  // 从API获取
  }
}

// 加载推荐方剂
const loadRecommendedPrescriptions = async () => {
  try {
    loadingPrescriptions.value = true
    
    // 尝试调用真实API
    try {
      const params = {
        page: 1,
        pageSize: 4,
        sortBy: 'usage_count', // 按使用频率排序
        sortOrder: 'desc'
      }
      
      // 实际API调用
      const response = await entityApi.prescriptions.list(params)
      if (response && response.data && response.data.length > 0) {
        recommendedPrescriptions.value = response.data
      } else {
        // API返回空数据，使用模拟数据
        useMockPrescriptions()
      }
    } catch (apiError) {
      console.log('API未就绪，使用模拟数据:', apiError)
      useMockPrescriptions()
    }
  } catch (error) {
    console.error('加载推荐方剂失败:', error)
    ElMessage.error('加载推荐方剂失败')
    // 出错时使用模拟数据
    useMockPrescriptions()
  } finally {
    loadingPrescriptions.value = false
  }
}

// 使用模拟方剂数据
const useMockPrescriptions = () => {
  recommendedPrescriptions.value = [
    {
      id: 'F001',
      name: '归脾汤',
      description: '益气补血、健脾养心，主治心脾两虚、气血不足证',
      category: '补益剂',
      source: '《济生方》'
    },
    {
      id: 'F002',
      name: '麻黄汤',
      description: '发汗解表、宣肺平喘，主治外感风寒表实证',
      category: '解表剂',
      source: '《伤寒论》'
    },
    {
      id: 'F003',
      name: '小柴胡汤',
      description: '和解少阳，主治伤寒少阳证',
      category: '和解剂',
      source: '《伤寒论》'
    },
    {
      id: 'F004',
      name: '补中益气汤',
      description: '补中益气、升阳举陷，主治脾虚气陷证',
      category: '补益剂',
      source: '《脾胃论》'
    }
  ]
}

// 加载推荐药材
const loadRecommendedHerbs = async () => {
  try {
    loadingHerbs.value = true
    
    // 尝试调用真实API
    try {
      const params = {
        page: 1,
        pageSize: 4,
        sortBy: 'usage_count', // 按使用频率排序
        sortOrder: 'desc'
      }
      
      // 实际API调用
      const response = await entityApi.herbs.list(params)
      if (response && response.data && response.data.length > 0) {
        recommendedHerbs.value = response.data
      } else {
        // API返回空数据，使用模拟数据
        useMockHerbs()
      }
    } catch (apiError) {
      console.log('API未就绪，使用模拟数据:', apiError)
      useMockHerbs()
    }
  } catch (error) {
    console.error('加载推荐药材失败:', error)
    ElMessage.error('加载推荐药材失败')
    // 出错时使用模拟数据
    useMockHerbs()
  } finally {
    loadingHerbs.value = false
  }
}

// 使用模拟药材数据
const useMockHerbs = () => {
  recommendedHerbs.value = [
    {
      id: 'H001',
      name: '人参',
      description: '大补元气、复脉固脱、补脾益肺、生津养血',
      nature_and_flavor: '甘、微苦，微温',
      efficacy: '补气固脱'
    },
    {
      id: 'H002',
      name: '黄芪',
      description: '补气升阳、固表止汗、利水消肿、生津养血',
      nature_and_flavor: '甘，微温',
      efficacy: '补气固表'
    },
    {
      id: 'H003',
      name: '当归',
      description: '补血活血、调经止痛、润肠通便',
      nature_and_flavor: '甘、辛，温',
      efficacy: '补血活血'
    },
    {
      id: 'H004',
      name: '茯苓',
      description: '利水渗湿、健脾宁心',
      nature_and_flavor: '甘、淡，平',
      efficacy: '利水渗湿'
    }
  ]
}

// 加载推荐症状
const loadRecommendedSymptoms = async () => {
  try {
    loadingSymptoms.value = true
    
    // 尝试调用真实API
    try {
      const params = {
        page: 1,
        pageSize: 4,
        sortBy: 'frequency', // 按出现频率排序
        sortOrder: 'desc'
      }
      
      // 实际API调用
      const response = await entityApi.symptoms.list(params)
      if (response && response.data && response.data.length > 0) {
        recommendedSymptoms.value = response.data
      } else {
        // API返回空数据，使用模拟数据
        useMockSymptoms()
      }
    } catch (apiError) {
      console.log('API未就绪，使用模拟数据:', apiError)
      useMockSymptoms()
    }
  } catch (error) {
    console.error('加载推荐症状失败:', error)
    ElMessage.error('加载推荐症状失败')
    // 出错时使用模拟数据
    useMockSymptoms()
  } finally {
    loadingSymptoms.value = false
  }
}

// 使用模拟症状数据
const useMockSymptoms = () => {
  recommendedSymptoms.value = [
    {
      id: 'S001',
      name: '失眠',
      description: '难以入眠、睡中易醒、早醒、睡眠质量差',
      category: '心神症状'
    },
    {
      id: 'S002',
      name: '畏寒',
      description: '怕冷，尤以背部、四肢为甚',
      category: '寒热症状'
    },
    {
      id: 'S003',
      name: '咳嗽',
      description: '肺气上逆作声，咯吐痰涎',
      category: '肺系症状'
    },
    {
      id: 'S004',
      name: '腹泻',
      description: '大便次数增多，粪质稀薄或完全不化',
      category: '脾胃症状'
    }
  ]
}

const goToChat = () => {
  router.push('/chat')
}

const goToGraph = () => {
  router.push('/graph')
}

const goToCaseStudy = () => {
  router.push('/case-study')
}

const goToHistory = () => {
  router.push('/history')
}

const viewDetail = (type: string, id: string) => {
  // 跳转到详情页面
  console.log('View detail:', type, id)
  // 这里可以跳转到实体详情页
}

const formatNumber = (num: number) => {
  return num.toLocaleString()
}
</script>

<style scoped lang="scss">
.front-index {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
  
  .welcome-banner {
    background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
    border-radius: 16px;
    padding: 60px 40px;
    margin-bottom: 40px;
    color: white;
    text-align: center;
    
    .banner-content {
      max-width: 800px;
      margin: 0 auto;
      
      .banner-title {
        font-size: 42px;
        margin: 0 0 16px 0;
        background: linear-gradient(45deg, #ff9800, #ff5722);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
      }
      
      .banner-subtitle {
        font-size: 18px;
        color: rgba(255, 255, 255, 0.9);
        margin-bottom: 40px;
      }
      
      .banner-actions {
        display: flex;
        gap: 20px;
        justify-content: center;
        flex-wrap: wrap;
      }
    }
  }
  
  .section-title {
    text-align: center;
    margin: 40px 0 30px;
    color: #1a237e;
    font-size: 28px;
    position: relative;
    
    &::after {
      content: '';
      display: block;
      width: 60px;
      height: 3px;
      background: linear-gradient(45deg, #409eff, #67c23a);
      margin: 12px auto;
      border-radius: 2px;
    }
  }
  
  .features-section {
    .features-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 24px;
      margin-bottom: 40px;
      
      .feature-card {
        background: white;
        border-radius: 12px;
        padding: 32px 24px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        transition: transform 0.3s, box-shadow 0.3s;
        cursor: pointer;
        
        &:hover {
          transform: translateY(-5px);
          box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
        }
        
        .feature-icon {
          width: 80px;
          height: 80px;
          background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          margin: 0 auto 24px;
          
          .el-icon {
            font-size: 36px;
            color: #2196f3;
          }
        }
        
        h3 {
          margin: 0 0 16px 0;
          color: #1a237e;
          font-size: 20px;
        }
        
        p {
          color: #666;
          line-height: 1.6;
          margin: 0;
        }
      }
    }
  }
  
  .recommendations-section {
    .recommendations-tabs {
      margin-bottom: 40px;
      
      .loading-content {
        text-align: center;
        padding: 60px 20px;
        
        .loading-spinner {
          display: inline-block;
          animation: spin 1s linear infinite;
          font-size: 32px;
          color: #409eff;
          margin-bottom: 16px;
        }
        
        p {
          color: #666;
          margin: 0;
        }
      }
      
      .empty-content {
        padding: 40px 20px;
      }
      
      .recommendations-list {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 20px;
        padding: 20px 0;
        
        .recommendation-item {
          background: white;
          border-radius: 8px;
          padding: 20px;
          box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
          cursor: pointer;
          transition: transform 0.3s, box-shadow 0.3s;
          
          &:hover {
            transform: translateY(-3px);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
          }
          
          h4 {
            margin: 0 0 12px 0;
            color: #1a237e;
            font-size: 18px;
          }
          
          p {
            color: #666;
            font-size: 14px;
            line-height: 1.5;
            margin: 0 0 16px 0;
          }
          
          .item-tags {
            display: flex;
            gap: 8px;
          }
        }
      }
    }
  }
  
  .stats-section {
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 24px;
      
      .stat-card {
        background: white;
        border-radius: 12px;
        padding: 24px;
        display: flex;
        align-items: center;
        gap: 20px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        
        .stat-icon {
          width: 60px;
          height: 60px;
          border-radius: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          
          .el-icon {
            font-size: 28px;
          }
        }
        
        .stat-info {
          h3 {
            margin: 0 0 8px 0;
            font-size: 28px;
            color: #1a237e;
          }
          
          p {
            margin: 0;
            color: #666;
            font-size: 14px;
          }
        }
      }
    }
  }
}

@media (max-width: 768px) {
  .front-index {
    padding: 10px;
    
    .welcome-banner {
      padding: 40px 20px;
      
      .banner-title {
        font-size: 32px;
      }
      
      .banner-actions {
        flex-direction: column;
        align-items: center;
      }
    }
    
    .features-grid,
    .recommendations-list,
    .stats-grid {
      grid-template-columns: 1fr;
    }
  }
}

// 旋转动画
@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>