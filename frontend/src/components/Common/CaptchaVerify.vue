<template>
  <el-dialog
    v-model="visible"
    title="安全验证"
    width="420px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
    center
  >
    <div class="captcha-verify">
      <div class="captcha-icon">
        <el-icon :size="48" color="#409eff"><Lock /></el-icon>
      </div>
      <p class="captcha-tip">请回答以下数学问题以验证您不是机器人：</p>
      <div class="captcha-question">
        <span class="question-label">问题：</span>
        <span class="question-text">{{ questionText }}</span>
      </div>
      <div class="captcha-input">
        <span class="answer-label">答案：</span>
        <el-input
          v-model="userAnswer"
          placeholder="请输入计算结果"
          size="large"
          type="number"
          :class="{ 'is-error': !!errorMsg }"
          @keyup.enter="submitAnswer"
        />
      </div>
      <p v-if="errorMsg" class="error-msg">
        <el-icon><WarningFilled /></el-icon>
        {{ errorMsg }}
      </p>
    </div>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="cancelVerify">取消</el-button>
        <el-button type="primary" :disabled="!userAnswer" @click="submitAnswer">
          确认验证
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Lock, WarningFilled } from '@element-plus/icons-vue'
import { isCaptchaVerified, setCaptchaVerified } from '@/utils/captcha'

// ---- 题目生成 ----
const visible = ref(false)
const num1 = ref(0)
const num2 = ref(0)
const operator = ref<'+' | '-' | '×'>('+')
const userAnswer = ref('')
const errorMsg = ref('')

// Promise 回调
let _resolve: ((value: boolean) => void) | null = null

const operators: Array<'+' | '-' | '×'> = ['+', '-', '×']

const correctAnswer = computed(() => {
  switch (operator.value) {
    case '+': return num1.value + num2.value
    case '-': return num1.value - num2.value
    case '×': return num1.value * num2.value
    default: return 0
  }
})

const questionText = computed(() => {
  return `${num1.value} ${operator.value} ${num2.value} = ？`
})

function generateQuestion() {
  const op = operators[Math.floor(Math.random() * operators.length)]
  operator.value = op

  switch (op) {
    case '+':
      num1.value = Math.floor(Math.random() * 90) + 10   // 10~99
      num2.value = Math.floor(Math.random() * 90) + 10
      break
    case '-':
      num1.value = Math.floor(Math.random() * 80) + 20   // 20~99
      num2.value = Math.floor(Math.random() * (num1.value - 1)) + 1  // 1~(num1-1)，结果始终为正
      break
    case '×':
      num1.value = Math.floor(Math.random() * 9) + 2     // 2~10
      num2.value = Math.floor(Math.random() * 9) + 2
      break
  }

  userAnswer.value = ''
  errorMsg.value = ''
}

// ---- 对外暴露 ----
function requireVerify(): Promise<boolean> {
  // 已通过验证，直接放行
  if (isCaptchaVerified()) {
    return Promise.resolve(true)
  }

  generateQuestion()
  visible.value = true

  return new Promise((resolve) => {
    _resolve = resolve
  })
}

function submitAnswer() {
  const answer = parseInt(userAnswer.value, 10)

  if (isNaN(answer)) {
    errorMsg.value = '请输入有效的数字答案'
    return
  }

  if (answer === correctAnswer.value) {
    setCaptchaVerified()
    visible.value = false
    _resolve?.(true)
    _resolve = null
  } else {
    generateQuestion()
    errorMsg.value = `答案不正确，请重新计算（已更换新题目）`
  }
}

function cancelVerify() {
  visible.value = false
  errorMsg.value = ''
  _resolve?.(false)
  _resolve = null
}

defineExpose({ requireVerify })
</script>

<style scoped lang="scss">
.captcha-verify {
  text-align: center;
  padding: 10px 0;

  .captcha-icon {
    margin-bottom: 16px;
  }

  .captcha-tip {
    color: #606266;
    font-size: 14px;
    margin: 0 0 24px 0;
  }

  .captcha-question {
    background: linear-gradient(135deg, #f0f5ff 0%, #e8f4fd 100%);
    border: 1px dashed #409eff;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 20px;

    .question-label {
      color: #909399;
      font-size: 14px;
      margin-right: 8px;
    }

    .question-text {
      font-size: 22px;
      font-weight: bold;
      color: #1a237e;
      letter-spacing: 4px;
      user-select: none;       // 防止复制
    }
  }

  .captcha-input {
    display: flex;
    align-items: center;
    gap: 12px;

    .answer-label {
      color: #606266;
      font-size: 14px;
      white-space: nowrap;
    }

    :deep(.el-input.is-error .el-input__wrapper) {
      box-shadow: 0 0 0 1px #f56c6c inset;
    }
  }

  .error-msg {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    color: #f56c6c;
    font-size: 13px;
    margin: 12px 0 0 0;
  }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
