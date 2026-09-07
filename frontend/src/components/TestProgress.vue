<template>
  <div class="test-progress">
    <div class="progress-header">
      <span>测试进度</span>
      <span class="progress-text">{{ current }} / {{ total }}</span>
    </div>
    <el-progress
      :percentage="percentage"
      :status="progressStatus"
      :stroke-width="16"
      :text-inside="true"
    />
    <div class="step-list">
      <div
        v-for="step in steps"
        :key="step.step_index"
        class="step-item"
        :class="step.result"
      >
        <ResultBadge :result="step.result" />
        <span class="step-label">{{ step.step_label }}</span>
        <span class="step-duration" v-if="step.duration_ms > 0">
          {{ (step.duration_ms / 1000).toFixed(1) }}s
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import ResultBadge from './ResultBadge.vue'

const props = defineProps<{
  current: number
  total: number
  steps: Array<{
    step_index: number
    step_label: string
    result: string
    duration_ms: number
  }>
  status: string
}>()

const percentage = computed(() => {
  if (props.total === 0) return 0
  return Math.round((props.current / props.total) * 100)
})

const progressStatus = computed(() => {
  if (props.status === 'completed') return 'success'
  if (props.status === 'failed') return 'exception'
  return ''
})
</script>

<style scoped>
.test-progress {
  margin-bottom: 16px;
}
.progress-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 14px;
  color: var(--text-secondary);
}
.progress-text {
  font-weight: bold;
  color: var(--accent);
}
.step-list {
  margin-top: 12px;
  max-height: 300px;
  overflow-y: auto;
}
.step-item {
  display: flex;
  align-items: center;
  padding: 6px 8px;
  border-bottom: 1px solid var(--border-color);
  font-size: 13px;
}
.step-item.running {
  background-color: rgba(64, 158, 255, 0.1);
}
.step-label {
  margin-left: 8px;
  flex: 1;
  color: var(--text-primary);
}
.step-duration {
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 12px;
}
</style>
