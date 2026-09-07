<template>
  <div class="status-bar">
    <div class="status-left">
      <span class="status-dot" :class="resourceStatus"></span>
      <span>系统正常</span>
      <span class="divider">|</span>
      <span>串口: {{ serialCount }} 可用</span>
      <span class="divider">|</span>
      <span>运行中: {{ runningCount }}</span>
    </div>
    <div class="status-right">
      <span>{{ currentTime }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const currentTime = ref('')
const serialCount = ref(0)
const runningCount = ref(0)
const resourceStatus = ref('online')

let timer: number | null = null

onMounted(() => {
  timer = window.setInterval(() => {
    currentTime.value = new Date().toLocaleString('zh-CN')
  }, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.status-bar {
  height: 36px;
  line-height: 36px;
  padding: 0 16px;
  background-color: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--text-secondary);
}
.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  background-color: var(--success);
}
.status-dot.offline {
  background-color: var(--danger);
}
.divider {
  margin: 0 8px;
  color: var(--border-color);
}
</style>
