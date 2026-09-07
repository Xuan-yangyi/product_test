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
    case 'pass': return 'success'
    case 'fail': return 'danger'
    case 'running': return 'warning'
    case 'pending': return 'info'
    case 'skip': return 'info'
    default: return 'info'
  }
})

const label = computed(() => {
  switch (props.result) {
    case 'pass': return 'PASS'
    case 'fail': return 'FAIL'
    case 'running': return 'RUN'
    case 'pending': return 'WAIT'
    case 'skip': return 'SKIP'
    default: return props.result.toUpperCase()
  }
})
</script>
