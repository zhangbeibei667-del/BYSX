import { createRouter, createWebHistory } from 'vue-router'

// 前台布局
import FrontLayout from '@/layouts/FrontLayout.vue'

// 前台页面
import FrontIndex from '@/views/Front/Index/Index.vue'
import ChatAI from '@/views/Front/ChatAI/ChatAI.vue'
import GraphBrowse from '@/views/Front/GraphBrowse/GraphBrowse.vue'
import CaseStudy from '@/views/Front/CaseStudy/CaseStudy.vue'
import History from '@/views/Front/History/History.vue'
import Login from '@/views/Front/Login/Login.vue'

// 后台布局
import AdminLayout from '@/layouts/AdminLayout.vue'

// 后台页面
import HerbManage from '@/views/Admin/HerbManage/HerbManage.vue'
import PresManage from '@/views/Admin/PresManage/PresManage.vue'
import SymptomManage from '@/views/Admin/SymptomManage/SymptomManage.vue'
import SyndromeManage from '@/views/Admin/SyndromeManage/SyndromeManage.vue'
import RelationManage from '@/views/Admin/RelationManage/RelationManage.vue'
import DocManage from '@/views/Admin/DocManage/DocManage.vue'
import RecordManage from '@/views/Admin/RecordManage/RecordManage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: FrontLayout,
      children: [
        {
          path: '',
          name: 'home',
          component: FrontIndex
        },
        {
          path: 'chat',
          name: 'chat',
          component: ChatAI
        },
        {
          path: 'graph',
          name: 'graph',
          component: GraphBrowse
        },
        {
          path: 'case-study',
          name: 'case-study',
          component: CaseStudy,
          meta: { requiresAuth: true }
        },
        {
          path: 'history',
          name: 'history',
          component: History,
          meta: { requiresAuth: true }
        },
        {
          path: 'login',
          name: 'login',
          component: Login
        }
      ]
    },
    {
      path: '/admin',
      component: AdminLayout,
      meta: { requiresAuth: true },
      children: [
        {
          path: 'herbs',
          name: 'herbs',
          component: HerbManage
        },
        {
          path: 'prescriptions',
          name: 'prescriptions',
          component: PresManage
        },
        {
          path: 'symptoms',
          name: 'symptoms',
          component: SymptomManage
        },
        {
          path: 'syndromes',
          name: 'syndromes',
          component: SyndromeManage
        },
        {
          path: 'relations',
          name: 'relations',
          component: RelationManage
        },
        {
          path: 'documents',
          name: 'documents',
          component: DocManage
        },
        {
          path: 'records',
          name: 'records',
          component: RecordManage
        }
      ]
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/'
    }
  ]
})

// 路由守卫 - 权限检查
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('admin_token')
  const isAuthenticated = !!token

  // 检查目标路由是否需要认证
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)

  if (requiresAuth) {
    if (!isAuthenticated) {
      // 无 token，跳转登录页并携带 redirect 参数
      next('/login?redirect=' + encodeURIComponent(to.fullPath))
      return
    }

    // 访问后台页面时检查是否有有效的用户信息（admin 和 user 均可访问）
    if (to.path.startsWith('/admin')) {
      const userInfoStr = localStorage.getItem('user_info')
      if (!userInfoStr) {
        next('/')
        return
      }
      try {
        const userInfo = JSON.parse(userInfoStr)
        if (userInfo.role !== 'admin' && userInfo.role !== 'user') {
          next('/')
          return
        }
      } catch {
        next('/')
        return
      }
    }

    next()
  } else if (to.path === '/login' && isAuthenticated) {
    // 已登录用户访问登录页，自动跳转首页
    next('/')
  } else {
    next()
  }
})

export default router