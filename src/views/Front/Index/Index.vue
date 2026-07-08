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
            浏览图谱
          </el-button>
          <el-button type="warning" size="large" @click="goToCaseStudy">
            <el-icon><Notebook /></el-icon>
            病例教学
          </el-button>
          <el-button type="info" size="large" @click="goToGraph">
            <el-icon><DataAnalysis /></el-icon>
            文献溯源
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
  
        <div class="feature-card" @click="goToGraph">
          <div class="feature-icon">
            <el-icon><Document /></el-icon>
          </div>
          <h3>文献溯源</h3>
            <p>答案自动关联经典文献和药典依据，提供可信的知识来源</p>
        </div>
      </div>
    </div>
    
    <!-- 热门推荐 -->
    <div class="recommendations-section">
      <h2 class="section-title">热门知识推荐</h2>
      <div class="recommendations-tabs">
        <el-tabs v-model="activeTab" type="border-card">
          <el-tab-pane label="常用方剂" name="prescriptions">
            <div class="recommendations-list">
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
            <div class="recommendations-list">
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
            <div class="recommendations-list">
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
            <h3>{{ formatNumber(stats.totalHerbs) }}</h3>
            <p>药材数量</p>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon" style="background: #f3e5f5;">
            <el-icon color="#9c27b0"><Document /></el-icon>
          </div>
          <div class="stat-info">
            <h3>{{ formatNumber(stats.totalPrescriptions) }}</h3>
            <p>方剂数量</p>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon" style="background: #e8f5e9;">
            <el-icon color="#4caf50"><Connection /></el-icon>
          </div>
          <div class="stat-info">
            <h3>{{ formatNumber(stats.totalRelations) }}</h3>
            <p>关系数量</p>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon" style="background: #fff3e0;">
            <el-icon color="#ff9800"><Message /></el-icon>
          </div>
          <div class="stat-info">
            <h3>{{ formatNumber(stats.totalQuestions) }}</h3>
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
import {
  ChatDotRound,
  DataAnalysis,
  Notebook,
  Document,
  Orange,
  Connection,
  Message
} from '@element-plus/icons-vue'

const router = useRouter()
const activeTab = ref('prescriptions')

// 统计数据
const stats = ref({
  totalHerbs: 156,
  totalPrescriptions: 89,
  totalRelations: 234,
  totalQuestions: 567
})

// 推荐数据
const recommendedPrescriptions = ref([
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
    source: '《伤���论》'
  },
  {
    id: 'F004',
    name: '补中益气汤',
    description: '补中益气、升阳举陷，主治脾虚气陷证',
    category: '补益剂',
    source: '《脾胃论》'
  }
])

const recommendedHerbs = ref([
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
])

const recommendedSymptoms = ref([
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
])

onMounted(() => {
  // 这里可以加载实际的统计数据
})

const goToChat = () => {
  router.push('/chat')
}

const goToGraph = () => {
  router.push('/graph')
}

const goToCaseStudy = () => {
  router.push('/case-study')
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
</style>