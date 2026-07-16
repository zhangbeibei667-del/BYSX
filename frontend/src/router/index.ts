import { createRouter, createWebHistory } from 'vue-router'
import { authApi } from '@/api'

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

// 路由守卫：受保护页面必须使用后端校验过的 token，后台仅管理员可进入。
router.beforeEach(async (to) => {
  const token = localStorage.getItem('admin_token')
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)

  if (requiresAuth) {
    if (!token) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }

    try {
      const response: any = await authApi.getCurrentUser()
      const user = response?.data || response
      if (!user?.username || !user?.role) {
        throw new Error('用户信息无效')
      }
      localStorage.setItem('user_info', JSON.stringify(user))

      if (to.path.startsWith('/admin') && user.role !== 'admin') {
        return { path: '/', query: { forbidden: 'admin' } }
      }
    } catch {
      localStorage.removeItem('admin_token')
      localStorage.removeItem('user_info')
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  } else if (to.path === '/login' && token) {
    return '/'
  }

  return true
})

export default router
