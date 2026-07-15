import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import { permission } from '@/directives/permission'

const app = createApp(App)
const pinia = createPinia()

// 注册Element Plus图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 注册自定义权限指令
app.directive('permission', permission)

app.use(pinia)

// 启动时从 localStorage 恢复登录状态，保证刷新后仍保持登录
import { useUserStore } from '@/store'
useUserStore().checkAuth()

app.use(router)
app.use(ElementPlus, { locale: zhCn })

app.mount('#app')