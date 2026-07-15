<!-- 登录模拟页，缺少与后端的调试
 后端用户信息数据库完成后还需要修改部分代码
 具体修改请见登录页后期修改说明.md-->
<template>
  <div class="auth-page">
    <div class="auth-container">
      <!-- 左侧装饰区 -->
      <div class="auth-decoration">
        <div class="decoration-content">
          <div class="decoration-icon">🌿</div>
          <h1 class="decoration-title">中医药智能诊疗平台</h1>
          <p class="decoration-subtitle">传承千年智慧，探索本草奥秘</p>
          <div class="decoration-features">
            <div class="feature-item">
              <el-icon><ChatDotRound /></el-icon>
              <span>智能问答</span>
            </div>
            <div class="feature-item">
              <el-icon><DataAnalysis /></el-icon>
              <span>知识图谱</span>
            </div>
            <div class="feature-item">
              <el-icon><Notebook /></el-icon>
              <span>病例教学</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧表单区 -->
      <div class="auth-form-wrapper">
        <!-- 模式切换标签 -->
        <div class="auth-tabs">
          <span
            class="auth-tab"
            :class="{ active: activeTab === 'login' }"
            @click="switchTab('login')"
          >
            登录
          </span>
          <span class="auth-tab-divider">|</span>
          <span
            class="auth-tab"
            :class="{ active: activeTab === 'register' }"
            @click="switchTab('register')"
          >
            注册
          </span>
        </div>

        <!-- ========== 登录表单 ========== -->
        <el-form
          v-if="activeTab === 'login'"
          ref="loginFormRef"
          :model="loginForm"
          :rules="loginRules"
          class="auth-form"
          size="large"
          @keyup.enter="handleLogin"
        >
          <el-form-item prop="username">
            <el-input
              v-model="loginForm.username"
              placeholder="请输入用户名 / 邮箱"
              :prefix-icon="User"
              clearable
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              :prefix-icon="Lock"
              show-password
            />
          </el-form-item>

          <div class="form-options">
            <el-checkbox v-model="loginForm.remember" label="记住密码" />
            <span class="forgot-link" @click="handleForgotPassword">忘记密码？</span>
          </div>

          <el-button
            type="primary"
            class="submit-btn"
            :loading="loginLoading"
            @click="handleLogin"
          >
            登 录
          </el-button>
        </el-form>

        <!-- ========== 注册表单 ========== -->
        <el-form
          v-if="activeTab === 'register'"
          ref="registerFormRef"
          :model="registerForm"
          :rules="registerRules"
          class="auth-form"
          size="large"
          @keyup.enter="handleRegister"
        >
          <el-form-item prop="username">
            <el-input
              v-model="registerForm.username"
              placeholder="请输入用户名（4-20位）"
              :prefix-icon="User"
              clearable
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="registerForm.password"
              type="password"
              placeholder="请输入密码（6-20位）"
              :prefix-icon="Lock"
              show-password
            />
          </el-form-item>

          <el-form-item prop="confirmPassword">
            <el-input
              v-model="registerForm.confirmPassword"
              type="password"
              placeholder="请再次输入密码"
              :prefix-icon="Lock"
              show-password
            />
          </el-form-item>

          <el-form-item prop="role" label="角色">
            <el-select
              v-model="registerForm.role"
              placeholder="请选择角色"
              style="width: 100%"
            >
              <el-option label="普通用户" value="user" />
              <el-option label="管理员" value="admin" />
            </el-select>
          </el-form-item>

          <el-button
            type="primary"
            class="submit-btn"
            :loading="registerLoading"
            @click="handleRegister"
          >
            注 册
          </el-button>
        </el-form>

        <!-- 提示信息 -->
        <p class="auth-tip">
          {{ activeTab === 'login' ? '还没有账号？' : '已有账号？' }}
          <span class="tip-link" @click="switchTab(activeTab === 'login' ? 'register' : 'login')">
            {{ activeTab === 'login' ? '立即注册' : '立即登录' }}
          </span>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock, Message, ChatDotRound, DataAnalysis, Notebook } from '@element-plus/icons-vue'
import { useUserStore } from '@/store'
import { authApi } from '@/api'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// ---- 模式切换 ----
const activeTab = ref<'login' | 'register'>('login')

const switchTab = (tab: 'login' | 'register') => {
  activeTab.value = tab
  loginFormRef.value?.resetFields()
  registerFormRef.value?.resetFields()
}

// ---- 登录 ----
const loginFormRef = ref<FormInstance>()
const loginLoading = ref(false)
const loginForm = reactive({
  username: '',
  password: '',
  remember: false
})

const loginRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名或邮箱', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不少于6位', trigger: 'blur' }
  ]
}

const handleLogin = async () => {
  if (!loginFormRef.value) return
  try {
    await loginFormRef.value.validate()
  } catch {
    return
  }

  loginLoading.value = true
  try {
    const res = await authApi.login({
      username: loginForm.username,
      password: loginForm.password
    }) as { data: { token: string; user: any } }

    const { token, user } = res.data
    userStore.login(token, user)

    ElMessage.success('登录成功，欢迎回来！')

    // 跳转到 redirect 参数指定的页面或首页
    const redirect = route.query.redirect as string
    router.push(redirect ? decodeURIComponent(redirect) : '/')
  } catch (error: any) {
    console.error('登录失败:', error)
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.msg || '登录失败，请检查用户名和密码')
  } finally {
    loginLoading.value = false
  }
}

// ---- 注册 ----
const registerFormRef = ref<FormInstance>()
const registerLoading = ref(false)
const registerForm = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  role: 'user' as 'user' | 'auditor' | 'admin'
})

const validateConfirmPassword = (_rule: any, value: string, callback: (error?: Error) => void) => {
  if (value !== registerForm.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const registerRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 4, max: 20, message: '用户名长度在 4 到 20 位之间', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_一-龥]+$/, message: '用户名只能包含中英文、数字和下划线', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 20, message: '密码长度在 6 到 20 位之间', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ],
  role: [
    { required: true, message: '请选择角色', trigger: 'change' }
  ]
}

const handleRegister = async () => {
  if (!registerFormRef.value) return
  try {
    await registerFormRef.value.validate()
  } catch {
    return
  }

  registerLoading.value = true
  try {
    await authApi.register({
      username: registerForm.username,
      password: registerForm.password
    })

    ElMessage.success('注册成功，请登录')
    // 注册成功后切换到登录 tab，不自动登录
    switchTab('login')
    // 自动填充刚注册的用户名
    loginForm.username = registerForm.username
  } catch (error: any) {
    console.error('注册失败:', error)
    ElMessage.error(error?.response?.data?.message || error?.response?.data?.msg || '注册失败，请稍后重试')
  } finally {
    registerLoading.value = false
  }
}

// ---- 忘记密码 ----
const handleForgotPassword = () => {
  ElMessage.info('请联系管理员重置密码：service@dongfangcaomu.com')
}
</script>

<style scoped lang="scss">
// ===== 国风色彩变量 =====
$dark-green: #2a4030;
$mid-green: #466350;
$soft-gold: #c8a86e;
$cream-bg: #f7f3eb;
$cream-white: #faf6ef;
$text-dark: #2c3630;
$text-light: #6b7a72;
$border-light: rgba(110, 135, 120, 0.12);
$shadow-card: 0 8px 40px rgba(42, 64, 48, 0.1);

.auth-page {
  margin: 0 auto;
  padding: 16px 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 64px - 60px);
  background-color: $cream-bg;
  margin-top: 50px;
  
  @media (max-width: 1200px) {
    margin-top: -1020px;
  }
}

.auth-container {
  display: flex;
  width: 100%;
  max-width: 960px;
  min-height: 560px;
  background: #fff;
  border-radius: 18px;
  overflow: hidden;
  box-shadow: $shadow-card;
  border: 1px solid $border-light;
}

// ===== 左侧装饰区 =====
.auth-decoration {
  flex: 1;
  background: linear-gradient(160deg, $dark-green 0%, #3a5a42 40%, $mid-green 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 36px;
  position: relative;
  overflow: hidden;

  // 装饰纹理
  &::before {
    content: '';
    position: absolute;
    top: -60px;
    right: -60px;
    width: 260px;
    height: 260px;
    border: 2px solid rgba(200, 168, 110, 0.15);
    border-radius: 50%;
  }

  &::after {
    content: '';
    position: absolute;
    bottom: -40px;
    left: -40px;
    width: 180px;
    height: 180px;
    border: 1px solid rgba(200, 168, 110, 0.12);
    border-radius: 50%;
  }

  .decoration-content {
    position: relative;
    z-index: 1;
    text-align: center;
    color: #fff;
  }

  .decoration-icon {
    font-size: 56px;
    margin-bottom: 20px;
  }

  .decoration-title {
    font-size: 22px;
    font-weight: 500;
    margin: 0 0 12px 0;
    letter-spacing: 2px;
    color: #f7f3eb;
  }

  .decoration-subtitle {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.7);
    margin: 0 0 36px 0;
    letter-spacing: 1px;
  }

  .decoration-features {
    display: flex;
    flex-direction: column;
    gap: 16px;
    align-items: flex-start;
    padding: 0 20px;

    .feature-item {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 14px;
      color: rgba(255, 255, 255, 0.8);

      .el-icon {
        font-size: 20px;
        color: $soft-gold;
      }
    }
  }
}

// ===== 右侧表单区 =====
.auth-form-wrapper {
  flex: 1;
  padding: 48px 44px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.auth-tabs {
  text-align: center;
  margin-bottom: 32px;

  .auth-tab {
    font-size: 20px;
    color: $text-light;
    cursor: pointer;
    transition: color 0.3s, font-weight 0.3s;
    padding: 0 8px;

    &.active {
      color: $dark-green;
      font-weight: 600;
    }

    &:hover {
      color: $dark-green;
    }
  }

  .auth-tab-divider {
    color: $border-light;
    margin: 0 12px;
    font-size: 18px;
    user-select: none;
  }
}

.auth-form {
  :deep(.el-input__wrapper) {
    border-radius: 8px;
    box-shadow: 0 0 0 1px $border-light inset;
    transition: box-shadow 0.3s;

    &:hover {
      box-shadow: 0 0 0 1px $mid-green inset;
    }
  }

  :deep(.el-input__wrapper.is-focus) {
    box-shadow: 0 0 0 1px $mid-green inset;
  }

  .form-options {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;

    :deep(.el-checkbox__label) {
      color: $text-light;
      font-size: 13px;
    }

    .forgot-link {
      color: $text-light;
      font-size: 13px;
      cursor: pointer;
      transition: color 0.2s;

      &:hover {
        color: $soft-gold;
      }
    }
  }

  .submit-btn {
    width: 100%;
    height: 46px;
    font-size: 16px;
    letter-spacing: 4px;
    border-radius: 8px;
    background: $dark-green;
    border-color: $dark-green;
    transition: all 0.3s;

    &:hover {
      background: $mid-green;
      border-color: $mid-green;
    }
  }
}

.auth-tip {
  text-align: center;
  color: $text-light;
  font-size: 13px;
  margin: 20px 0 0 0;

  .tip-link {
    color: $dark-green;
    cursor: pointer;
    font-weight: 500;
    transition: color 0.2s;

    &:hover {
      color: $soft-gold;
      text-decoration: underline;
    }
  }
}

// ===== 响应式 =====
@media (max-width: 768px) {
  .auth-container {
    flex-direction: column;
    max-width: 420px;
  }

  .auth-decoration {
    padding: 32px 24px;

    .decoration-icon {
      font-size: 40px;
    }

    .decoration-title {
      font-size: 18px;
    }

    .decoration-features {
      display: none;
    }
  }

  .auth-form-wrapper {
    padding: 32px 24px;
  }
}

@media (max-width: 1200px) {
  .auth-page {
    margin-top: -1020px;
  }
}
</style>
