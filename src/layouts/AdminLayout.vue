<template>
  <div class="admin-layout">
    <!-- 顶部导航栏 -->
    <header class="header">
      <div class="header-container">
        <div class="logo" @click="backToFront">
          <span class="logo-text">中医药智能诊疗平台</span>
        </div>

        <nav class="nav">
          <span class="nav-item" :class="{ active: $route.path === '/' }" @click="goToHome">首页</span>
          <span class="nav-item" :class="{ active: $route.path === '/chat' }" @click="goToChat">开始问答</span>
          <span class="nav-item" :class="{ active: $route.path === '/graph' }" @click="goToGraph">知识图谱</span>
          <span class="nav-item" :class="{ active: $route.path === '/history' }" @click="goToHistory">历史记录</span>
          <span class="nav-item admin-nav" :class="{ active: $route.path.startsWith('/admin') }" @click="goToAdmin">后台管理</span>

          <span class="user-section">
            <el-avatar :size="32" class="user-avatar">{{ userInitial }}</el-avatar>
            <span class="user-name">{{ userInfo.username || '未登录' }}</span>
            <span v-if="roleLabel" class="role-tag" :class="`role-${userInfo.role}`">{{ roleLabel }}</span>
            <span class="logout-link" @click="logout">退出登录</span>
          </span>
        </nav>
      </div>
    </header>

    <!-- 内容区域 -->
    <div class="admin-container">
      <!-- 侧边栏 -->
      <aside class="sidebar">
        <div class="sidebar-header">
          <span class="sidebar-title">管理菜单</span>
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
import { ElMessage } from 'element-plus'
import {
  Orange,
  Document,
  Warning,
  Filter,
  Connection,
  Files,
  List
} from '@element-plus/icons-vue'
import { useUserStore } from '@/store'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const userInfo = computed(() => userStore.userInfo)
const userInitial = computed(() => (userInfo.value.username || 'U').charAt(0).toUpperCase())

const roleLabel = computed(() => {
  switch (userInfo.value.role) {
    case 'admin': return '管理员'
    case 'user': return '普通用户'
    default: return ''
  }
})

const activeMenu = computed(() => route.path)

// 导航方法
const goToHome = () => router.push('/')
const goToChat = () => router.push('/chat')
const goToGraph = () => router.push('/graph')
const goToHistory = () => router.push('/history')
const goToAdmin = () => router.push('/admin/herbs')

const backToFront = () => {
  router.push('/')
}

const handleMenuSelect = (index: string) => {
  router.push(index)
}

const logout = () => {
  userStore.logout()
  ElMessage.success('已退出登录')
  router.push('/')
}
</script>

<style scoped lang="scss">
// 国风色彩变量（与前台保持一致）
$dark-green: #2a4030;
$mid-green: #466350;
$soft-gold: #c8a86e;
$cream-bg: #f7f3eb;
$text-light: #6b7a72;

.admin-layout {
  width: 100%;
  min-height: 100vh;
  background-color: $cream-bg;
  display: flex;
  flex-direction: column;

  // ===== 顶部导航栏 =====
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
        .logo-text { font-weight: 500; }
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

          &.active { color: #fff; font-weight: 500; }
          &:hover { color: #fff; }

          &.admin-nav.active { color: #fff; font-weight: 500; }
          &.admin-nav:hover { color: #fff; }
        }

        .user-section {
          display: flex;
          align-items: center;
          gap: 10px;
          padding-left: 22px;
          border-left: 1px solid rgba(255, 255, 255, 0.15);

          .user-avatar {
            background: $soft-gold;
            color: #fff;
            font-size: 14px;
            font-weight: 600;
            flex-shrink: 0;
          }

          .user-name {
            font-size: 14px;
            color: rgba(255, 255, 255, 0.9);
            max-width: 100px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          .role-tag {
            font-size: 12px;
            padding: 2px 9px;
            border-radius: 10px;
            letter-spacing: 1px;
            border: 1px solid transparent;
            &.role-admin {
              color: $soft-gold;
              border-color: rgba(200, 168, 110, 0.5);
              background: rgba(200, 168, 110, 0.12);
            }
            &.role-user {
              color: rgba(255, 255, 255, 0.75);
              border-color: rgba(255, 255, 255, 0.25);
              background: rgba(255, 255, 255, 0.06);
            }
          }

          .logout-link {
            font-size: 14px;
            color: rgba(255, 255, 255, 0.6);
            cursor: pointer;
            transition: color 0.2s;
            &:hover { color: rgba(255, 255, 255, 0.9); }
          }
        }
      }
    }
  }

  // ===== 内容容器（与顶部导航栏保持距离） =====
  .admin-container {
    flex: 1;
    margin-top: 50px;
    display: flex;
    max-width: 1800px;
    width: 100%;
    margin-left: auto;
    margin-right: auto;
    padding: 0 32px;
    box-sizing: border-box;
    gap: 24px;

    // ===== 侧边栏 =====
    .sidebar {
      width: 240px;
      flex-shrink: 0;
      background: #faf6ef;
      color: $dark-green;
      border-radius: 14px;
      overflow: hidden;
      display: flex;
      flex-direction: column;

      .sidebar-header {
        padding: 16px 20px 12px;
        border-bottom: 1px solid rgba(110, 135, 120, 0.1);

        .sidebar-title {
          font-size: 13px;
          font-weight: 600;
          color: rgba(70, 99, 80, 0.6);
          letter-spacing: 1.5px;
          text-transform: uppercase;
        }
      }

      .admin-menu {
        flex: 1;
        background: transparent;
        border-right: none;

        :deep(.el-menu-item) {
          color: $mid-green;
          height: 52px;
          line-height: 52px;
          margin: 5px 12px;
          padding-left: 12px !important;
          border-radius: 8px;
          font-size: 15px;
          font-weight: 400;
          transition: all 0.25s ease;
          position: relative;

          &:hover {
            background-color: rgba(42, 64, 48, 0.06);
            color: $dark-green;
          }

          &.is-active {
            background-color: rgba(200, 168, 110, 0.15);
            color: $dark-green;
            font-weight: 500;

            &::before {
              content: '';
              position: absolute;
              left: -12px;
              top: 50%;
              transform: translateY(-50%);
              width: 3px;
              height: 28px;
              background: $soft-gold;
              border-radius: 0 3px 3px 0;
            }

            .el-icon { color: $soft-gold; }
          }

          .el-icon {
            color: rgba(70, 99, 80, 0.5);
            font-size: 18px;
            margin-right: 10px;
          }
        }
      }
    }

    // ===== 内容区 =====
    .content-container {
      flex: 1;
      min-width: 0;
      padding: 24px 32px;
      overflow-y: auto;
      overflow-x: auto;
      background: #fff;
      border-radius: 14px;
      box-shadow: 0 2px 16px rgba(42, 64, 48, 0.08);
    }
  }
}
</style>