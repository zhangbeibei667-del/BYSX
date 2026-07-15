<template>
  <div class="front-layout">
    <!-- 顶部导航栏 -->
    <header class="header">
      <div class="header-container">
        <div class="logo">
          <el-icon :size="28" color="#409eff"><FirstAidKit /></el-icon>
          <span class="logo-text">中医药诊疗智能体</span>
        </div>
        
        <nav class="nav">
          <router-link to="/" class="nav-item" :class="{ active: $route.name === 'home' }">
            <el-icon><HomeFilled /></el-icon>
            首页
          </router-link>
          <router-link to="/chat" class="nav-item" :class="{ active: $route.name === 'chat' }">
            <el-icon><ChatDotRound /></el-icon>
            智能问答
          </router-link>
          <router-link to="/graph" class="nav-item" :class="{ active: $route.name === 'graph' }">
            <el-icon><DataAnalysis /></el-icon>
            知识图谱
          </router-link>
          <router-link to="/case-study" class="nav-item" :class="{ active: $route.name === 'case-study' }">
            <el-icon><Notebook /></el-icon>
            病例教学
          </router-link>
          <router-link to="/history" class="nav-item" :class="{ active: $route.name === 'history' }">
            <el-icon><Clock /></el-icon>
            历史记录
          </router-link>
        </nav>
        
        <div class="header-right">
          <el-button type="primary" link @click="goToAdmin">
            <el-icon><Setting /></el-icon>
            后台管理
          </el-button>
          <el-dropdown>
            <div class="user-info">
              <el-icon><User /></el-icon>
              <span>{{ currentUser || '访客用户' }}</span>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="login">
                  <el-icon><UserFilled /></el-icon>
                  登录
                </el-dropdown-item>
                <el-dropdown-item @click="register">
                  <el-icon><EditPen /></el-icon>
                  注册
                </el-dropdown-item>
                <el-dropdown-item divided @click="aboutSystem">
                  <el-icon><InfoFilled /></el-icon>
                  关于系统
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
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
    
    <!-- 页脚 -->
    <footer class="footer">
      <div class="footer-container">
        <div class="footer-info">
          <p>© 2026 中医药诊疗智能体系统 - 基于知识图谱的中医药学习与教学辅助平台</p>
          <p class="disclaimer">本系统仅供中医药知识学习、教学辅助和研究参考使用，不构成医疗诊断或治疗建议。</p>
        </div>
        <div class="footer-links">
          <el-link type="info" :underline="false">用户协议</el-link>
          <el-link type="info" :underline="false">隐私政策</el-link>
          <el-link type="info" :underline="false">联系我们</el-link>
        </div>
      </div>
    </footer>
    
    <el-dialog v-model="authVisible" :title="authMode === 'login' ? '管理员登录' : '注册普通用户'" width="420px">
      <el-form label-width="70px">
        <el-form-item label="用户名"><el-input v-model="credentials.username" autocomplete="username" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="credentials.password" type="password" show-password autocomplete="current-password" @keyup.enter="submitAuth" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="authVisible=false">取消</el-button><el-button type="primary" :loading="authLoading" @click="submitAuth">{{ authMode === 'login' ? '登录' : '注册' }}</el-button></template>
    </el-dialog>

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
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { kgApi } from '@/api'
import {
  HomeFilled,
  ChatDotRound,
  DataAnalysis,
  Notebook,
  Clock,
  Setting,
  User,
  UserFilled,
  EditPen,
  InfoFilled,
  FirstAidKit
} from '@element-plus/icons-vue'
const router = useRouter()
const aboutDialogVisible = ref(false)
const authVisible = ref(false)
const authLoading = ref(false)
const authMode = ref<'login'|'register'>('login')
const credentials = ref({ username: 'admin', password: '' })
const currentUser = ref(localStorage.getItem('admin_username') || '')

const goToAdmin = () => {
  if (localStorage.getItem('admin_token')) router.push('/admin/herbs')
  else { authMode.value = 'login'; authVisible.value = true }
}

const login = () => {
  authMode.value = 'login'; authVisible.value = true
}

const register = () => {
  authMode.value = 'register'; authVisible.value = true
}

const submitAuth = async () => {
  if (!credentials.value.username || !credentials.value.password) return ElMessage.warning('请输入用户名和密码')
  authLoading.value = true
  try {
    if (authMode.value === 'register') { await kgApi.register(credentials.value.username, credentials.value.password); authMode.value='login'; return ElMessage.success('注册成功，请登录') }
    const result = await kgApi.login(credentials.value.username, credentials.value.password)
    localStorage.setItem('admin_token', result.token); localStorage.setItem('admin_username', result.user.username); localStorage.setItem('admin_role', result.user.role)
    currentUser.value = result.user.username; authVisible.value = false; ElMessage.success('登录成功')
    if (result.user.role === 'admin') router.push('/admin/herbs')
  } catch (error:any) { ElMessage.error(error.message || '认证失败') } finally { authLoading.value = false }
}

const aboutSystem = () => {
  aboutDialogVisible.value = true
}
</script>

<style scoped lang="scss">
.front-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  
  .header {
    background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
    color: white;
    padding: 0 20px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
    
    .header-container {
      max-width: 1400px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 64px;
      
      .logo {
        display: flex;
        align-items: center;
        gap: 10px;
        cursor: pointer;
        
        .logo-text {
          font-size: 20px;
          font-weight: bold;
          background: linear-gradient(45deg, #409eff, #67c23a);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
      }
      
      .nav {
        display: flex;
        gap: 30px;
        
        .nav-item {
          display: flex;
          align-items: center;
          gap: 6px;
          color: rgba(255, 255, 255, 0.8);
          text-decoration: none;
          padding: 8px 16px;
          border-radius: 4px;
          transition: all 0.3s;
          
          &:hover {
            color: white;
            background: rgba(255, 255, 255, 0.1);
          }
          
          &.active {
            color: white;
            background: rgba(255, 255, 255, 0.2);
            font-weight: 500;
          }
        }
      }
      
      .header-right {
        display: flex;
        align-items: center;
        gap: 20px;
        
        .user-info {
          display: flex;
          align-items: center;
          gap: 6px;
          color: white;
          cursor: pointer;
          padding: 6px 12px;
          border-radius: 4px;
          
          &:hover {
            background: rgba(255, 255, 255, 0.1);
          }
        }
      }
    }
  }
  
  .main-content {
  flex: 1;
  padding: 20px;
  max-width: 1400px;
  margin: 1000px auto 0;
  width: 100%;
  }
  
  .footer {
    background: #2c3e50;
    color: #ecf0f1;
    padding: 20px;
    
    .footer-container {
      max-width: 1400px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 20px;
      
      .footer-info {
        flex: 1;
        min-width: 300px;
        
        p {
          margin: 5px 0;
          font-size: 14px;
        }
        
        .disclaimer {
          font-size: 12px;
          color: #bdc3c7;
          font-style: italic;
        }
      }
      
      .footer-links {
        display: flex;
        gap: 20px;
        
        .el-link {
          color: #ecf0f1;
          
          &:hover {
            color: #409eff;
          }
        }
      }
    }
  }
  
  .about-content {
    h3 {
      margin-top: 0;
      color: #409eff;
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

// 页面切换动画
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
