<template>
  <div class="detail-view">
    <el-page-header @back="$router.back()" :title="'返回'" :content="'测试详情'" />

    <!-- 概览卡片 -->
    <el-card shadow="never" class="overview-card" v-loading="loading">
      <template #header>测试概览</template>
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="测试 ID">{{ detail.test_id }}</el-descriptions-item>
        <el-descriptions-item label="测试类型">{{ detail.test_type }}</el-descriptions-item>
        <el-descriptions-item label="产品型号">{{ detail.product_model }}</el-descriptions-item>
        <el-descriptions-item label="序列号">{{ detail.serial_number || '-' }}</el-descriptions-item>
        <el-descriptions-item label="主板 SN">{{ detail.board_sn || '-' }}</el-descriptions-item>
        <el-descriptions-item label="设备 IP">{{ detail.device_ip || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <ResultBadge :result="detail.status" />
        </el-descriptions-item>
        <el-descriptions-item label="通过/失败/跳过">
          {{ detail.passed || 0 }} / {{ detail.failed || 0 }} / {{ detail.skipped || 0 }}
        </el-descriptions-item>
        <el-descriptions-item label="耗时">
          {{ formatDuration(detail.duration_seconds) }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ detail.created_at }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ detail.finished_at || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 步骤结果 -->
    <el-card shadow="never" class="steps-card" v-if="steps.length > 0">
      <template #header>步骤结果 ({{ steps.length }})</template>
      <el-table :data="steps" size="small" style="width: 100%">
        <el-table-column prop="step_index" label="#" width="50" />
        <el-table-column prop="step_label" label="步骤" min-width="200" />
        <el-table-column label="结果" width="100">
          <template #default="{ row }">
            <ResultBadge :result="row.result" />
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="120">
          <template #default="{ row }">
            {{ row.duration_ms ? row.duration_ms + 'ms' : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="message" label="消息" min-width="180" show-overflow-tooltip />
      </el-table>
    </el-card>

    <!-- 日志 -->
    <el-card shadow="never" class="log-card">
      <template #header>测试日志</template>
      <el-tabs v-model="activeLogTab">
        <el-tab-pane label="老化日志" name="aging">
          <div class="log-content" v-if="agingLog.length > 0">
            <div v-for="(line, i) in agingLog" :key="i" class="log-line">{{ line }}</div>
          </div>
          <el-empty v-else description="暂无老化日志" />
        </el-tab-pane>
        <el-tab-pane label="系统日志" name="syslog">
          <div class="log-content" v-if="syslogLines.length > 0">
            <div v-for="(line, i) in syslogLines" :key="i" class="log-line">{{ line }}</div>
          </div>
          <el-empty v-else description="暂无系统日志" />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import ResultBadge from '@/components/ResultBadge.vue'
import { testApi } from '@/api/test'

const route = useRoute()
const testId = route.params.id as string

const loading = ref(false)
const detail = ref<any>({})
const steps = ref<any[]>([])
const agingLog = ref<string[]>([])
const syslogLines = ref<string[]>([])
const activeLogTab = ref('aging')

onMounted(async () => {
  loading.value = true
  try {
    const [detailRes, agingRes, syslogRes] = await Promise.all([
      testApi.getResultDetail(testId),
      testApi.getLogs(testId).catch(() => ({ lines: [] })),
      testApi.getSyslog(testId).catch(() => ({ lines: [] })),
    ])
    detail.value = (detailRes as any) || {}
    steps.value = (detailRes as any)?.steps || []
    agingLog.value = (agingRes as any)?.lines || []
    syslogLines.value = (syslogRes as any)?.lines || []
  } catch (e) {
  } finally {
    loading.value = false
  }
})

function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return '-'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}h ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}
</script>

<style scoped>
.detail-view {
  max-width: 1200px;
  margin: 0 auto;
}
.overview-card, .steps-card, .log-card {
  margin-top: 16px;
  background-color: var(--bg-card);
  border-color: var(--border-color);
}
.log-content {
  max-height: 500px;
  overflow-y: auto;
  background: #1a1a2e;
  color: #a0ffa0;
  font-family: var(--font-mono);
  font-size: 12px;
  padding: 12px;
  border-radius: 4px;
}
.log-line {
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.6;
}
</style>