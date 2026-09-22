<template>
  <div class="results-view">
    <h2 class="page-title">测试结果</h2>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row" v-if="stats.total > 0">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">总测试数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-pass">
          <div class="stat-value">{{ stats.completed }}</div>
          <div class="stat-label">通过</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-fail">
          <div class="stat-value">{{ stats.failed }}</div>
          <div class="stat-label">失败</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-rate">
          <div class="stat-value">{{ stats.pass_rate }}%</div>
          <div class="stat-label">通过率</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filters" size="small">
        <el-form-item label="序列号">
          <el-input v-model="filters.serial_number" placeholder="SN" clearable />
        </el-form-item>
        <el-form-item label="测试类型">
          <el-select v-model="filters.test_type" placeholder="全部" clearable>
            <el-option v-for="t in testTypes" :key="t.type" :label="t.label" :value="t.type" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable>
            <el-option label="通过" value="completed" />
            <el-option label="失败" value="failed" />
            <el-option label="运行中" value="running" />
            <el-option label="已中断" value="interrupted" />
            <el-option label="已停止" value="stopped" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            value-format="YYYY-MM-DD"
            size="small"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search">查询</el-button>
          <el-button @click="handleExport" :loading="exporting">导出 CSV</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <el-table :data="results" style="width: 100%" v-loading="loading" size="small">
        <el-table-column prop="test_id" label="测试ID" width="120" />
        <el-table-column prop="test_type" label="测试类型" width="140" />
        <el-table-column prop="product_model" label="产品型号" width="100" />
        <el-table-column prop="serial_number" label="序列号" width="160" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <ResultBadge :result="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="通过/失败" width="100">
          <template #default="{ row }">
            <span style="color: #67c23a">{{ row.passed || 0 }}</span>
            /
            <span style="color: #f56c6c">{{ row.failed || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="100">
          <template #default="{ row }">
            {{ formatDuration(row.duration_seconds) }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewDetail(row.test_id)">
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > 0"
        v-model:current-page="filters.page"
        :page-size="filters.page_size"
        :total="total"
        layout="prev, pager, next"
        @current-change="search"
        style="margin-top: 16px; justify-content: center;"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ResultBadge from '@/components/ResultBadge.vue'
import { testApi } from '@/api/test'
import { useTestStore } from '@/stores/test'

const router = useRouter()
const testStore = useTestStore()

const testTypes = ref<any[]>([])
const results = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const exporting = ref(false)
const dateRange = ref<string[]>([])

const stats = reactive({
  total: 0,
  completed: 0,
  failed: 0,
  pass_rate: 0,
})

const filters = reactive({
  serial_number: '',
  test_type: '',
  status: '',
  start_date: '',
  end_date: '',
  page: 1,
  page_size: 20,
})

onMounted(async () => {
  await testStore.fetchTypes()
  testTypes.value = testStore.testTypes
  search()
  fetchStats()
})

async function search() {
  loading.value = true
  try {
    if (dateRange.value && dateRange.value.length === 2) {
      filters.start_date = dateRange.value[0]
      filters.end_date = dateRange.value[1]
    } else {
      filters.start_date = ''
      filters.end_date = ''
    }
    const res: any = await testApi.getResults(filters)
    results.value = res.items || []
    total.value = res.total || 0
  } catch (e) {
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  try {
    const res: any = await testApi.getStatistics()
    Object.assign(stats, res)
  } catch (e) {}
}

function viewDetail(testId: string) {
  router.push({ name: 'result-detail', params: { id: testId } })
}

async function handleExport() {
  exporting.value = true
  try {
    const params: any = {}
    if (filters.test_type) params.test_type = filters.test_type
    if (filters.status) params.status = filters.status
    if (filters.start_date) params.start_date = filters.start_date
    if (filters.end_date) params.end_date = filters.end_date

    const blob: any = await testApi.exportCsv(params)
    const url = window.URL.createObjectURL(new Blob([blob]))
    const link = document.createElement('a')
    link.href = url
    link.download = 'test_results.csv'
    link.click()
    window.URL.revokeObjectURL(url)
  } catch (e) {
  } finally {
    exporting.value = false
  }
}

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
.results-view {
  max-width: 1200px;
  margin: 0 auto;
}
.page-title {
  font-size: 24px;
  margin-bottom: 16px;
  color: var(--text-primary);
}
.stats-row {
  margin-bottom: 16px;
}
.stat-card {
  text-align: center;
  background-color: var(--bg-card);
  border-color: var(--border-color);
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}
.stat-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
}
.stat-pass .stat-value { color: #67c23a; }
.stat-fail .stat-value { color: #f56c6c; }
.stat-rate .stat-value { color: var(--accent); }
.filter-card {
  margin-bottom: 16px;
  background-color: var(--bg-card);
  border-color: var(--border-color);
}
.table-card {
  background-color: var(--bg-card);
  border-color: var(--border-color);
}
</style>