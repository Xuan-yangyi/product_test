<template>
  <div class="run-view">
    <el-page-header @back="$router.back()" :title="'返回'" :content="'测试执行'" />

    <div class="run-header">
      <div class="run-info">
        <h3>{{ testInfo?.test_type }} - {{ testInfo?.product_model }}</h3>
        <span class="run-id">ID: {{ testInfo?.test_id }}</span>
        <div v-if="testInfo?.params?.loop || testInfo?.params?.reboot" class="aging-params">
          <el-tag type="warning" size="small">循环: {{ testInfo.params.loop || 0 }} 次</el-tag>
          <el-tag type="danger" size="small" style="margin-left: 8px">重启: {{ testInfo.params.reboot || 0 }} 次</el-tag>
        </div>
      </div>
      <div class="run-actions">
        <el-button
          v-if="testInfo?.status === 'running'"
          type="warning"
          @click="handlePause"
        >
          暂停
        </el-button>
        <el-button
          v-if="testInfo?.status === 'paused'"
          type="success"
          @click="handleResume"
        >
          继续
        </el-button>
        <el-button
          v-if="testInfo?.status === 'running' || testInfo?.status === 'paused'"
          type="danger"
          @click="handleStop"
        >
          停止
        </el-button>
      </div>
    </div>

    <TestProgress
      :current="testInfo?.current_step || 0"
      :total="testInfo?.total_steps || 0"
      :steps="testInfo?.steps || []"
      :status="testInfo?.status || 'pending'"
    />

    <LogViewer :logs="logs" />

    <InteractDialog
      :request="interactionRequest"
      @response="handleInteraction"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, reactive, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import TestProgress from '@/components/TestProgress.vue'
import LogViewer from '@/components/LogViewer.vue'
import InteractDialog from '@/components/InteractDialog.vue'
import { useWebSocket } from '@/services/websocket'
import { testApi } from '@/api/test'

const route = useRoute()
const testId = route.params.id as string

const testInfo = ref<any>({})
const logs = reactive<Array<{
  timestamp: string
  level: string
  source: string
  message: string
}>>([])
const interactionRequest = ref<any>(null)

const { connected, messages, connect, disconnect } = useWebSocket(testId)

// Track how many messages we've already processed to avoid duplicates
let processedCount = 0

onMounted(async () => {
  connect()
  try {
    const res: any = await testApi.getTest(testId)
    testInfo.value = res
  } catch (e) {}
})

onUnmounted(() => {
  disconnect()
})

watch(messages, (msgs) => {
  // Only process new messages
  for (let i = processedCount; i < msgs.length; i++) {
    const msg = msgs[i]
    switch (msg.type) {
      case 'log':
        logs.push(msg.data as any)
        break
      case 'step_update':
        if (testInfo.value) {
          const steps = testInfo.value.steps || []
          const idx = steps.findIndex((s: any) => s.step_index === msg.data.step_index)
          if (idx >= 0) {
            steps[idx] = { ...steps[idx], ...msg.data }
          } else {
            steps.push(msg.data)
          }
          testInfo.value.steps = [...steps]
          // 更新 current_step
          if (msg.data.step_index !== undefined) {
            testInfo.value.current_step = msg.data.step_index + 1
          }
        }
        break
      case 'status_change':
        if (testInfo.value) {
          testInfo.value.status = msg.data.new
          if (msg.data.new === 'completed') {
            ElMessage.success('测试完成')
          } else if (msg.data.new === 'failed') {
            ElMessage.error('测试失败')
          }
        }
        break
      case 'interaction':
        interactionRequest.value = msg.data
        break
      case 'subscribed':
        break
    }
  }
  processedCount = msgs.length
}, { deep: true })

async function handlePause() {
  await testApi.pauseTest(testId)
  testInfo.value.status = 'paused'
}

async function handleResume() {
  await testApi.resumeTest(testId)
  testInfo.value.status = 'running'
}

async function handleStop() {
  try {
    await ElMessageBox.confirm('确定要停止测试吗？', '确认', { type: 'warning' })
    await testApi.stopTest(testId)
    testInfo.value.status = 'stopped'
  } catch (e) {}
}

async function handleInteraction(action: string, value?: string) {
  await testApi.sendInteraction(testId, { action, value })
  interactionRequest.value = null
}
</script>

<style scoped>
.run-view {
  max-width: 1200px;
  margin: 0 auto;
}
.run-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 16px 0;
  padding: 16px;
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
}
.run-info h3 {
  font-size: 18px;
  color: var(--text-primary);
}
.run-id {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}
.aging-params {
  margin-top: 8px;
  display: flex;
  align-items: center;
}
.run-actions {
  display: flex;
  gap: 8px;
}
</style>
