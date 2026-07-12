<!-- 页面大小调不好，我先放弃了 -->
<template>
  <div class="admin-layout">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <span class="sidebar-logo-icon">🌿</span>
        <span class="sidebar-logo-text">后台管理</span>
      </div>
      
      <el-menu
        :default-active="activeMenu"
        class="admin-menu"
        @select="handleMenuSelect"
      >
        <el-menu-item index="/admin/herbs">
          <el-icon><Orange /></el-icon>
          药材管理
        </el-menu-item>
        <el-menu-item index="/admin/prescriptions">
          <el-icon><Document /></el-icon>
          方剂管理
        </el-menu-item>
        <el-menu-item index="/admin/symptoms">
          <el-icon><Warning /></el-icon>
          症状管理
        </el-menu-item>
        <el-menu-item index="/admin/syndromes">
          <el-icon><Filter /></el-icon>
          证候管理
        </el-menu-item>
        <el-menu-item index="/admin/relations">
          <el-icon><Connection /></el-icon>
          图谱管理
        </el-menu-item>
        <el-menu-item index="/admin/documents">
          <el-icon><Files /></el-icon>
          文献管理
        </el-menu-item>
        <el-menu-item index="/admin/records">
          <el-icon><List /></el-icon>
          记录管理
        </el-menu-item>
      </el-menu>
    </aside>
    
    <!-- 主内容区域 -->
    <div class="main-content">
      <!-- 顶部栏 -->
      <header class="admin-header">
        <div class="breadcrumb">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>后台管理</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentPageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        
        <div class="admin-tools">
          <el-button class="back-btn" link @click="backToFront">
            <el-icon><Back /></el-icon>
            返回前台
          </el-button>
          <el-button class="logout-btn" link @click="logout">
            <el-icon><SwitchButton /></el-icon>
            退出登录
          </el-button>
        </div>
      </header>
      
      <!-- 页面内容 -->
      <div class="content-container">
        <router-view />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Orange,
  Document,
  Warning,
  Filter,
  Connection,
  Files,
  List,
  Back,
  SwitchButton
} from '@element-plus/icons-vue'
import { clearCaptchaVerified } from '@/utils/captcha'

const route = useRoute()
const router = useRouter()

const pageTitles: Record<string, string> = {
  '/admin/herbs': '药材管理',
  '/admin/prescriptions': '方剂管理',
  '/admin/symptoms': '症状管理',
  '/admin/syndromes': '证候管理',
  '/admin/relations': '图谱管理',
  '/admin/documents': '文献管理',
  '/admin/records': '记录管理'
}

const activeMenu = computed(() => route.path)
const currentPageTitle = computed(() => pageTitles[route.path] || '管理')

const handleMenuSelect = (index: string) => {
  router.push(index)
}

const backToFront = () => {
  router.push('/')
}

const logout = () => {
  localStorage.removeItem('admin_token')
  clearCaptchaVerified()
  router.push('/')
}
</script>

<style scoped lang="scss">
// ==================== 国风色彩变量 ====================
$dark-green: #2a4030;
$mid-green: #466350;
$light-green: #e8f1e5;
$soft-gold: #c8a86e;
$gold-light: rgba(200, 168, 110, 0.15);
$cream-bg: #f7f3eb;
$cream-white: #faf6ef;
$text-dark: #2c3630;
$text-light: #6b7a72;
$border-light: rgba(110, 135, 120, 0.12);
$shadow-soft: 0 2px 12px rgba(42, 64, 48, 0.06);

.admin-layout {
  display: flex;
  min-height: 100vh;
  background-color: $cream-bg;
  
  // ========== 侧边栏 - 国风深绿 ==========
  .sidebar {
    width: 240px;
    flex-shrink: 0;
    background: $dark-green;
    color: rgba(255, 255, 255, 0.85);
    display: flex;
    flex-direction: column;
    
    .sidebar-header {
      height: 64px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      padding: 0 16px;
      
      .sidebar-logo-icon {
        font-size: 22px;
      }
      
      .sidebar-logo-text {
        font-size: 18px;
        font-weight: 500;
        letter-spacing: 2px;
        color: #f7f3eb;
      }
    }
    
    .admin-menu {
      flex: 1;
      background: transparent;
      border-right: none;
      padding: 8px 0;
      
      :deep(.el-menu-item) {
        color: rgba(255, 255, 255, 0.7);
        height: 48px;
        line-height: 48px;
        margin: 2px 12px;
        border-radius: 8px;
        font-size: 14px;
        transition: all 0.25s ease;
        
        &:hover {
          background-color: rgba(255, 255, 255, 0.08);
          color: #fff;
        }
        
        &.is-active {
          background-color: rgba(200, 168, 110, 0.2);
          color: $soft-gold;
          font-weight: 500;
          
          .el-icon {
            color: $soft-gold;
          }
        }
        
        .el-icon {
          color: rgba(255, 255, 255, 0.5);
          font-size: 18px;
          margin-right: 10px;
        }
      }
    }
  }
  
  // ========== 主内容区 ==========
  .main-content {
    flex: 1;
    min-width: 0;
    max-width: calc(100vw - 240px);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: $cream-bg;
    
    // ===== 顶部栏 =====
    .admin-header {
      height: 64px;
      background: $cream-white;
      border-bottom: 1px solid $border-light;
      padding: 0 28px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
      
      .breadcrumb {
        :deep(.el-breadcrumb__inner) {
          &.is-link {
            color: $text-light;
            
            &:hover {
              color: $mid-green;
            }
          }
        }
        
        :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
          color: $text-dark;
          font-weight: 500;
        }
      }
      
      .admin-tools {
        display: flex;
        gap: 16px;
        
        .back-btn,
        .logout-btn {
          color: $text-light;
          font-size: 14px;
          
          &:hover {
            color: $mid-green;
          }
        }
        
        .logout-btn:hover {
          color: #b35c5c;
        }
      }
    }
    
    // ===== 内容容器 =====
    .content-container {
      flex: 1;
      min-width: 0;
      padding: 20px 24px 28px;
      overflow-y: auto;
      overflow-x: auto;
      background: $cream-bg;
    }
  }
}

// ========== 响应式适配 ==========
@media (max-width: 768px) {
  .admin-layout {
    .sidebar {
      width: 64px;
      
      .sidebar-header {
        .sidebar-logo-text {
          display: none;
        }
        .sidebar-logo-icon {
          font-size: 26px;
        }
      }
      
      .admin-menu {
        :deep(.el-menu-item) {
          justify-content: center;
          padding: 0 !important;
          margin: 2px 6px;
          
          .el-icon {
            margin-right: 0 !important;
          }
          
          span:not(.el-icon) {
            display: none;
          }
        }
      }
    }
    
    .main-content {
      max-width: calc(100vw - 64px);
    }
  }
}
</style>