/**
 * 数学验证会话管理 —— 同一浏览器会话只需验证一次
 */
const SESSION_KEY = '_captcha_verified'

export function isCaptchaVerified(): boolean {
  return sessionStorage.getItem(SESSION_KEY) === 'true'
}

export function setCaptchaVerified(): void {
  sessionStorage.setItem(SESSION_KEY, 'true')
}

export function clearCaptchaVerified(): void {
  sessionStorage.removeItem(SESSION_KEY)
}
