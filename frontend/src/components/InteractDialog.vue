<template>
  <el-dialog
    v-model="visible"
    :title="'人工检查确认'"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
    width="520px"
    top="40vh"
    class="interact-dialog"
  >
    <div class="interact-message">
      <el-icon :size="24" color="#e6a23c"><WarningFilled /></el-icon>
      <p>{{ request?.message }}</p>
    </div>

    <div v-if="request?.dialog_type === 'input'" class="interact-input">
      <el-input v-model="inputValue" placeholder="请输入" />
    </div>

    <template #footer>
      <el-button @click="respond('cancel')">取消（异常）</el-button>
      <el-button @click="respond('skip')">跳过</el-button>
      <el-button type="primary" @click="respond('confirm')">
        {{ request?.dialog_type === 'input' ? '提交' : '确认（正常）' }}
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
  padding: 12px 0 4px;
}
.interact-message p {
  font-size: 15px;
  line-height: 1.7;
  color: #303133;   /* 白底深色字 */
}
.interact-input {
  margin-bottom: 16px;
}
</style>

<style>
/* 人工确认弹窗：浅色风格（白底 + 深色字），整体位置靠下 */
.interact-dialog {
  --el-dialog-bg-color: #ffffff;
  background-color: #ffffff;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
}
.interact-dialog .el-dialog__header {
  border-bottom: 1px solid #ebeef5;
  margin-right: 0;
  padding-bottom: 12px;
}
.interact-dialog .el-dialog__title { color: #1f2d3d; font-weight: 600; }
.interact-dialog .el-dialog__body { color: #303133; padding-top: 8px; }
.interact-dialog .el-dialog__footer { padding-top: 8px; }
</style>