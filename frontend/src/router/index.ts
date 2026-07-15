import { createRouter, createWebHistory } from 'vue-router'

// 前台布局
import FrontLayout from '@/layouts/FrontLayout.vue'

// 前台页面
import FrontIndex from '@/views/Front/Index/Index.vue'
import ChatAI from '@/views/Front/ChatAI/ChatAI.vue'
import GraphBrowse from '@/views/Front/GraphBrowse/GraphBrowse.vue'
import CaseStudy from '@/views/Front/CaseStudy/CaseStudy.vue'
import History from '@/views/Front/History/History.vue'

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
import { kgApi } from '@/api'

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
          component: CaseStudy
        },
        {
          path: 'history',
          name: 'history',
          component: History
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
router.beforeEach(async (to) => {
  if (!to.matched.some(record => record.meta.requiresAuth)) return true
  if (!localStorage.getItem('admin_token')) return '/'
  try {
    const user = await kgApi.me()
    if (user.role !== 'admin') throw new Error('admin required')
    return true
  } catch {
    for (const key of ['admin_token','admin_username','admin_role']) localStorage.removeItem(key)
    return '/'
  }
})

export default router
