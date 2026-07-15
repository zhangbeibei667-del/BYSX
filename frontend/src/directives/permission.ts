import type { Directive } from 'vue'

/**
 * 权限指令 v-permission
 *
 * 用法：v-permission="['admin']" 或 v-permission="['admin', 'user']"
 *
 * - 从 localStorage 读取 user_info 获取当前用户角色
 * - 角色不在允许列表中则移除该 DOM 元素
 * - 未登录或无法解析角色信息时默认移除元素
 */
export const permission: Directive<HTMLElement, string[]> = {
  mounted(el, binding) {
    const allowedRoles = binding.value
    if (!Array.isArray(allowedRoles) || allowedRoles.length === 0) {
      el.remove()
      return
    }

    const userInfoStr = localStorage.getItem('user_info')
    if (!userInfoStr) {
      el.remove()
      return
    }

    try {
      const userInfo = JSON.parse(userInfoStr)
      const role = userInfo.role as string
      if (!allowedRoles.includes(role)) {
        el.remove()
      }
    } catch {
      el.remove()
    }
  }
}

export default permission
