<template>
  <el-dialog
    v-model="visible"
    :title="'人工交互'"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
    width="500px"
  >
    <div class="interact-message">
      <el-icon :size="24" color="var(--warning)"><WarningFilled /></el-icon>
      <p>{{ request?.message }}</p>
    </div>

    <div v-if="request?.dialog_type === 'input'" class="interact-input">
      <el-input v-model="inputValue" placeholder="请输入" />
    </div>

    <template #footer>
      <el-button @click="respond('cancel')">取消</el-button>
      <el-button @click="respond('skip')">跳过</el-button>
      <el-button type="primary" @click="respond('confirm')">
        {{ request?.dialog_type === 'input' ? '提交' : '确认' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { WarningFilled } from '@element-plus/icons-vue'

const props = defineProps<{
  request: {
    step_name: string
    message: string
    dialog_type: string
    timeout: number
  } | null
}>()

const emit = defineEmits<{
  response: [action: string, value?: string]
}>()

const visible = ref(false)
const inputValue = ref('')

watch(() => props.request, (val) => {
  if (val) {
    visible.value = true
    inputValue.value = ''
  }
})

function respond(action: string) {
  visible.value = false
  emit('response', action, action === 'input' ? inputValue.value : undefined)
}
</script>

<style scoped>
.interact-message {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 0;
}
.interact-message p {
  font-size: 15px;
  line-height: 1.6;
  color: var(--text-primary);
}
.interact-input {
  margin-bottom: 16px;
}
</style>
