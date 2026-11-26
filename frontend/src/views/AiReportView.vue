<template>
  <div class="report-page">
    <div class="toolbar no-print">
      <el-button @click="goBack">← 返回结果页</el-button>
      <el-button @click="load" :loading="loading">刷新</el-button>
    </div>

    <el-result
      v-if="notFound"
      icon="warning"
      title="报告不存在或已过期"
      sub-title="报告在服务器本地保留 30 分钟（服务重启不丢失），过期后请返回结果页重新生成"
    >
      <template #extra>
        <el-button type="primary" @click="goBack">返回结果页</el-button>
      </template>
    </el-result>

    <div v-else-if="report" class="report-body">
      <AiReportContent :report="report" :show-close="false" />
    </div>

    <div v-else v-loading="loading" class="loading-box">加载报告中…</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '@/api/http'
import AiReportContent from '@/components/AiReportContent.vue'

const route = useRoute()
const router = useRouter()
const reportId = route.params.id as string

const report = ref<any>(null)
const loading = ref(false)
const notFound = ref(false)

onMounted(load)

async function load() {
  loading.value = true
  notFound.value = false
  try {
    report.value = await http.get(`/ai/summary/report/${reportId}`)
  } catch (e: any) {
    if (e?.response?.status === 404) notFound.value = true
    report.value = null
  } finally {
    loading.value = false
  }
}

function goBack() {
  router.push({ name: 'results' })
}
</script>

<style scoped>
.report-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 16px 8px 40px;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.report-body {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 24px 32px 40px;
}
.loading-box { padding: 60px; text-align: center; color: var(--text-secondary); }
</style>