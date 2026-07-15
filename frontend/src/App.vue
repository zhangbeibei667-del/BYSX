<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted } from 'vue'

// 移除 index.html 中预置的 app-loading 类，避免其 flex 布局干扰页面宽度
onMounted(() => {
  const appEl = document.getElementById('app')
  if (appEl) {
    appEl.classList.remove('app-loading')
  }
})
</script>

<style scoped></style>