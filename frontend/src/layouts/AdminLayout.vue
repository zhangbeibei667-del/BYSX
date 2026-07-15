<!-- 页面大小调不好，我先放弃了 -->
<template>
  <div class="admin-layout">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <el-icon :size="28" color="#409eff"><Setting /></el-icon>
        <span>后台管理</span>
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
          <el-button type="primary" link @click="backToFront">
            <el-icon><Back /></el-icon>
            返回前台
          </el-button>
          <el-button type="warning" link @click="logout">
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
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Setting,
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

const route = useRoute()
const router = useRouter()

// 页面标题映射
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
  localStorage.removeItem('admin_username')
  localStorage.removeItem('admin_role')
  router.push('/')
}
</script>

<style scoped lang="scss">
.admin-layout {
  display: flex;
  min-height: 100vh;
  background-color: #f5f7fa;
  
  .sidebar {
    width: 240px;
    background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
    color: white;
    display: flex;
    flex-direction: column;
    
    .sidebar-header {
      height: 64px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      font-size: 18px;
      font-weight: bold;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .admin-menu {
      flex: 1;
      background: transparent;
      border-right: none;
      
      :deep(.el-menu-item) {
        color: rgba(255, 255, 255, 0.8);
        height: 56px;
        line-height: 56px;
        
        &:hover {
          background-color: rgba(255, 255, 255, 0.1);
          color: white;
        }
        
        &.is-active {
          background-color: rgba(255, 255, 255, 0.2);
          color: white;
          font-weight: 500;
        }
      }
      
      :deep(.el-icon) {
        color: inherit;
        font-size: 18px;
      }
    }
  }
  
  .main-content {
    flex: 1;
    min-width: 0;
    max-width: calc(100vw - 240px);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    
    .admin-header {
      height: 64px;
      background: white;
      border-bottom: 1px solid #e4e7ed;
      padding: 0 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      
      .breadcrumb {
        :deep(.el-breadcrumb__inner) {
          &.is-link {
            color: #606266;
            
            &:hover {
              color: #409eff;
            }
          }
        }
      }
      
      .admin-tools {
        display: flex;
        gap: 16px;
      }
    }
    
    .content-container {
      flex: 1;
      min-width: 0;
      padding: 20px 24px;
      overflow-y: auto;
      overflow-x: atuo;
    }
  }
}
</style>
