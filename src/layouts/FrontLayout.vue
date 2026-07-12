<template>
  <div class="front-layout">
    <!-- 顶部导航栏 - 国风样式 -->
    <header class="header">
      <div class="header-container">
        <div class="logo" @click="goToHome">
          <span class="logo-text">中医药智能诊疗平台</span>
        </div>
        
        <nav class="nav">
          <span class="nav-item" :class="{ active: $route.path === '/' }" @click="goToHome">首页</span>
          <span class="nav-item" :class="{ active: $route.path === '/chat' }" @click="goToChat">开始问答</span>
          <span class="nav-item" :class="{ active: $route.path === '/graph' }" @click="goToGraph">知识图谱</span>
          <span class="nav-item" :class="{ active: $route.path === '/case-study' }" @click="goToCaseStudy">病例教学</span>
          <span class="nav-item" :class="{ active: $route.path === '/history' }" @click="goToHistory">历史记录</span>
          <span class="nav-item" :class="{ active: $route.path.startsWith('/admin') }" @click="goToAdmin">后台管理</span>
          <el-button text class="login-btn" @click="login">登录 / 注册</el-button>
        </nav>
      </div>
    </header>
    
    <!-- 主要内容区域 -->
    <main class="main-content">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    
    <!-- 页脚 - 国风样式 -->
    <footer class="footer">
      <div class="footer-inner">
        <div class="footer-col">
          <div class="footer-logo">东方草木</div>
          <p>传承中医药文化，打造现代化智能本草平台</p>
        </div>
        <div class="footer-col">
          <h4>网站导航</h4>
          <div class="footer-link" @click="goToHome">首页</div>
          <div class="footer-link" @click="goToChat">智能体问答</div>
          <div class="footer-link" @click="goToGraph">图谱浏览</div>
          <div class="footer-link" @click="goToCaseStudy">病例教学</div>
          <div class="footer-link" @click="goToHistory">历史记录</div>
          <div class="footer-link" @click="goToAdmin">后台管理</div>
        </div>
        <div class="footer-col">
          <h4>帮助中心</h4>
          <div class="footer-link">使用指南</div>
          <div class="footer-link">常见问题</div>
          <div class="footer-link">联系客服</div>
        </div>
        <div class="footer-col">
          <h4>联系我们</h4>
          <div class="footer-link">邮箱：service@dongfangcaomu.com</div>
          <div class="footer-link">客服电话：400-888-2688</div>
          <div class="footer-link">工作时间：周一至周日 9:00-18:00</div>
        </div>
      </div>
      <div class="copyright">©2026 东方草木 版权所有 | 本平台仅作教学科研使用</div>
    </footer>
    
    <!-- 人机验证弹窗 -->
    <CaptchaVerify ref="captchaRef" />

    <!-- 关于系统对话框 -->
    <el-dialog v-model="aboutDialogVisible" title="关于系统" width="500px">
      <div class="about-content">
        <h3>中医药诊疗智能体系统</h3>
        <p>版本：v1.0.0</p>
        <p>基于知识图谱的中医药学习与教学辅助平台</p>
        <p>功能特性：</p>
        <ul>
          <li>知识图谱可视化浏览</li>
          <li>智能问答（RAG + Agent）</li>
          <li>病例教学分析</li>
          <li>实体管理后台</li>
          <li>关系路径查询</li>
        </ul>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="aboutDialogVisible = false">关闭</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import CaptchaVerify from '@/components/Common/CaptchaVerify.vue'

const router = useRouter()
const route = useRoute()
const aboutDialogVisible = ref(false)
const captchaRef = ref<InstanceType<typeof CaptchaVerify>>()

const goToHome = () => router.push('/')
const goToChat = () => router.push('/chat')
const goToGraph = () => router.push('/graph')
const goToCaseStudy = () => router.push('/case-study')
const goToHistory = () => router.push('/history')

const goToAdmin = async () => {
  const passed = await captchaRef.value?.requireVerify()
  if (passed) {
    router.push('/admin/herbs')
  }
}

const login = () => {
  router.push('/login')
}
</script>

<style scoped lang="scss">
// 国风色彩变量
$dark-green: #2a4030;
$mid-green: #466350;
$soft-gold: #c8a86e;
$cream-bg: #f7f3eb;
$text-light: #6b7a72;

.front-layout {
  width: 100%;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: $cream-bg;

  // ===== 顶部导航栏 - 国风样式 =====
  .header {
    width: 100%;
    background: $dark-green;
    padding: 14px 0;
    flex-shrink: 0;
    position: sticky;
    top: 0;
    z-index: 100;

    .header-container {
      max-width: 1800px;
      margin: 0 auto;
      padding: 0 32px;
      display: flex;
      justify-content: space-between;
      align-items: center;

      .logo {
        color: #f7f3eb;
        font-size: 18px;
        letter-spacing: 1px;
        cursor: pointer;
        user-select: none;

        .logo-text {
          font-weight: 500;
        }
      }

      .nav {
        display: flex;
        gap: 32px;
        align-items: center;

        .nav-item {
          color: rgba(255, 255, 255, 0.75);
          cursor: pointer;
          transition: color 0.2s;
          font-size: 15px;

          &.active {
            color: #fff;
            font-weight: 500;
          }

          &:hover {
            color: #fff;
          }
        }

        .login-btn {
          color: $soft-gold;
          font-size: 15px;

          &:hover {
            color: lighten($soft-gold, 15%);
          }
        }
      }
    }
  }

  // ===== 主要内容区域 =====
  .main-content {
    flex: 1;
    padding: 24px 32px;
    width: 100%;
  }

  // ===== 页脚 - 国风样式 =====
  .footer {
    background: #1f3026;
    padding: 50px 24px 26px;
    color: rgba(255, 255, 255, 0.7);
    flex-shrink: 0;

    .footer-inner {
      max-width: 1800px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 36px;
      margin-bottom: 36px;

      .footer-col {
        .footer-logo {
          color: #fff;
          font-size: 20px;
          margin-bottom: 14px;
          letter-spacing: 1px;
        }

        h4 {
          color: #fff;
          font-size: 16px;
          margin-bottom: 16px;
          font-weight: 500;
        }

        .footer-link {
          margin-bottom: 9px;
          cursor: pointer;
          transition: color 0.2s;

          &:hover {
            color: $soft-gold;
          }
        }

        p {
          margin: 0;
          font-size: 14px;
          line-height: 1.6;
          color: rgba(255, 255, 255, 0.7);
        }
      }
    }

    .copyright {
      max-width: 1800px;
      margin: 0 auto;
      text-align: center;
      font-size: 13px;
      padding-top: 18px;
      border-top: 1px solid rgba(255, 255, 255, 0.1);
      color: rgba(255, 255, 255, 0.5);
    }
  }

  // ===== 关于系统对话框 =====
  .about-content {
    h3 {
      margin-top: 0;
      color: $dark-green;
    }

    ul {
      padding-left: 20px;

      li {
        margin: 8px 0;
        color: #666;
      }
    }
  }
}

// ===== 页面切换动画 =====
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

// ===== 移动端适配 =====
@media (max-width: 992px) {
  .front-layout {
    .header .header-container {
      flex-direction: column;
      gap: 14px;
      text-align: center;
    }

    .footer .footer-inner {
      grid-template-columns: repeat(2, 1fr);
    }
  }
}

@media (max-width: 768px) {
  .front-layout {
    .header .nav {
      flex-wrap: wrap;
      justify-content: center;
      gap: 14px;
    }

    .footer .footer-inner {
      grid-template-columns: 1fr;
      text-align: center;
    }

    .main-content {
      padding-top: 16px;
      padding-bottom: 16px;
    }
  }
}
</style>