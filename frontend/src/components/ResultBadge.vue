<template>
  <el-tag :type="tagType" :effect="effect" size="small">
    {{ label }}
  </el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  result: string
  effect?: 'dark' | 'light' | 'plain'
}>(), {
  effect: 'dark',
})

const tagType = computed(() => {
  switch (props.result) {
    case 'pass': case 'completed': return 'success'
    case 'fail': case 'failed': return 'danger'
    case 'running': return 'warning'
    case 'pending': return 'info'
    case 'skip': return 'info'
    case 'stopped': return 'info'
    case 'interrupted': return 'warning'
    default: return 'info'
  }
})

const label = computed(() => {
  switch (props.result) {
    case 'pass': case 'completed': return 'PASS'
    case 'fail': case 'failed': return 'FAIL'
    case 'running': return 'RUN'
    case 'pending': return 'WAIT'
    case 'skip': return 'SKIP'
    case 'stopped': return 'STOP'
    case 'interrupted': return '中断'
    default: return props.result.toUpperCase()
  }
})
</script>
