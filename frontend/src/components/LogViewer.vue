<template>
  <div class="log-viewer" ref="containerRef">
    <div class="log-header">
      <span>实时日志</span>
      <el-button size="small" @click="clearLogs" :icon="Delete" text />
    </div>
    <div class="log-content" ref="contentRef">
      <div
        v-for="(log, i) in logs"
        :key="i"
        class="log-line"
        :class="log.level.toLowerCase()"
      >
        <span class="log-time">{{ formatTime(log.timestamp) }}</span>
        <span class="log-level">{{ log.level }}</span>
        <span class="log-source">{{ log.source }}</span>
        <span class="log-msg">{{ log.message }}</span>
      </div>
      <div v-if="logs.length === 0" class="log-empty">等待日志输出...</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { Delete } from '@element-plus/icons-vue'

const props = defineProps<{
  logs: Array<{
    timestamp: string
    level: string
    source: string
    message: string
  }>
}>()

const containerRef = ref<HTMLElement>()
const contentRef = ref<HTMLElement>()

watch(() => props.logs.length, async () => {
  await nextTick()
  if (contentRef.value) {
    contentRef.value.scrollTop = contentRef.value.scrollHeight
  }
})

function formatTime(ts: string) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN')
}

function clearLogs() {
  props.logs.splice(0, props.logs.length)
}
</script>

<style scoped>
.log-viewer {
  background-color: #0d1117;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  overflow: hidden;
}
.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background-color: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  font-size: 13px;
  color: var(--text-secondary);
}
.log-content {
  height: 400px;
  overflow-y: auto;
  padding: 8px 0;
  font-family: var(--font-mono);
  font-size: 12px;
}
.log-line {
  padding: 1px 12px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-all;
}
.log-line:hover {
  background-color: rgba(64, 158, 255, 0.05);
}
.log-time { color: #6e7681; margin-right: 8px; }
.log-level { margin-right: 8px; font-weight: bold; }
.log-source { color: #58a6ff; margin-right: 8px; }
.log-msg { color: var(--text-primary); }
.log-line.error .log-level { color: var(--danger); }
.log-line.warn .log-level { color: var(--warning); }
.log-line.info .log-level { color: var(--success); }
.log-line.debug .log-level { color: var(--info); }
.log-empty {
  padding: 20px;
  text-align: center;
  color: var(--text-secondary);
}
</style>
