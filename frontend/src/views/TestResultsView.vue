<template>
  <div class="results-view">
    <h2 class="page-title">测试结果</h2>

    <div class="results-layout">
      <!-- 左侧：统计 + 筛选 + 结果表 -->
      <div class="results-main">
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
            <el-table-column label="操作" width="100">
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

      <!-- 右侧：AI 汇总分析 -->
      <aside class="ai-panel">
        <el-card shadow="never" class="ai-card">
          <template #header>
            <div class="ai-head">
              <span class="ai-title">AI 汇总分析</span>
              <el-tag size="small" :type="engineTagType">{{ engineLabel }}</el-tag>
            </div>
          </template>

          <div class="ai-actions">
            <el-button
              type="primary"
              @click="analyzeSummary('interface')"
              :loading="aiLoading && aiKind === 'interface'"
              :disabled="aiLoading"
            >
              快速分析接口测试报告
            </el-button>
            <el-button
              type="success"
              @click="analyzeSummary('aging')"
              :loading="aiLoading && aiKind === 'aging'"
              :disabled="aiLoading"
            >
              快速分析老化日志报告
            </el-button>
            <el-button
              type="warning"
              @click="analyzeSummary('all')"
              :loading="aiLoading && aiKind === 'all'"
              :disabled="aiLoading"
            >
              汇总测试报告
            </el-button>
          </div>

          <div class="ai-stats" v-if="aiStats.total !== undefined">
            范围 <b>{{ aiStats.total }}</b> 台 ·
            通过 <b class="ok">{{ aiStats.passed }}</b> ·
            失败 <b class="bad">{{ aiStats.failed }}</b> ·
            通过率 <b>{{ aiStats.pass_rate }}%</b>
          </div>

          <div class="ai-result" v-loading="aiLoading">
            <div v-if="aiResult" class="md" v-html="renderMarkdown(aiResult)"></div>
            <el-empty
              v-else
              description="点击上方按钮，对当前筛选范围的测试结果做 AI 汇总分析"
              :image-size="60"
            />
          </div>

          <div class="ai-foot" v-if="aiResult">
            <span class="ai-engine">引擎：{{ providerLabel }}</span>
            <el-button link size="small" @click="clearAi">清空</el-button>
          </div>
        </el-card>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import ResultBadge from '@/components/ResultBadge.vue'
import { testApi } from '@/api/test'
import http from '@/api/http'
import { renderMarkdown } from '@/utils/markdown'
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

// ---------------- AI 汇总分析 ----------------
const aiLoading = ref(false)
const aiKind = ref('')
const aiResult = ref('')
const aiProvider = ref('')
const aiStats = ref<any>({})
const engine = ref<any>({ claude_available: false, provider_pref: 'auto' })

const engineLabel = computed(() => {
  if (engine.value.provider_pref === 'api') return 'API 模式'
  if (engine.value.provider_pref === 'claude') return 'Claude 模式'
  return engine.value.claude_available ? 'Claude 优先' : 'API 模式'
})

const engineTagType = computed(() => (engine.value.claude_available ? 'success' : 'info'))

const providerLabel = computed(() => {
  if (aiProvider.value === 'claude') return 'Claude CLI'
  if (aiProvider.value === 'api') return 'API Key'
  if (aiProvider.value === 'none') return '不可用'
  return '-'
})

onMounted(async () => {
  await testStore.fetchTypes()
  testTypes.value = testStore.testTypes
  search()
  fetchStats()
  fetchEngine()
})

async function fetchEngine() {
  try {
    const res: any = await http.get('/ai/summary/engine')
    engine.value = res || engine.value
  } catch (e) {}
}

function summaryFilters() {
  const f: any = {}
  if (filters.status) f.status = filters.status
  if (filters.serial_number) f.serial_number = filters.serial_number
  if (filters.start_date) f.start_date = filters.start_date
  if (filters.end_date) f.end_date = filters.end_date
  return f
}

async function analyzeSummary(kind: 'interface' | 'aging' | 'all') {
  if (aiLoading.value) return
  aiLoading.value = true
  aiKind.value = kind
  aiResult.value = ''
  aiStats.value = {}
  aiProvider.value = ''
  try {
    const res: any = await http.post(
      `/ai/summary/${kind}`,
      { filters: summaryFilters() },
      { timeout: 300000 } as any,
    )
    aiResult.value = res.analysis || '（无分析结果）'
    aiProvider.value = res.provider || 'none'
    aiStats.value = res.stats || {}
  } catch (e: any) {
    ElMessage.error('AI 汇总分析失败: ' + (e?.detail || e?.message || '未知错误'))
  } finally {
    aiLoading.value = false
    aiKind.value = ''
  }
}

function clearAi() {
  aiResult.value = ''
  aiStats.value = {}
  aiProvider.value = ''
}

// ---------------- 结果列表 ----------------
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
  max-width: 1680px;
  margin: 0 auto;
}
.page-title {
  font-size: 24px;
  margin-bottom: 16px;
  color: var(--text-primary);
}
.results-layout {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}
.results-main {
  flex: 1;
  min-width: 0;
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

/* ---------------- AI 面板 ---------------- */
.ai-panel {
  width: 420px;
  flex-shrink: 0;
  position: sticky;
  top: 16px;
}
.ai-card {
  background-color: var(--bg-card);
  border-color: var(--border-color);
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 32px);
}
.ai-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
}
.ai-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.ai-title {
  font-weight: 600;
  color: var(--text-primary);
}
.ai-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ai-actions .el-button {
  width: 100%;
  margin-left: 0;
}
.ai-stats {
  font-size: 12px;
  color: var(--text-secondary);
}
.ai-stats .ok { color: #67c23a; }
.ai-stats .bad { color: #f56c6c; }
.ai-result {
  flex: 1;
  min-height: 240px;
  max-height: calc(100vh - 340px);
  overflow: auto;
  background: rgba(0, 0, 0, 0.18);
  border-radius: 6px;
  padding: 10px 12px;
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.7;
}
.ai-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary);
}

/* Markdown 内容样式（v-html） */
.md :deep(p) { margin: 4px 0; }
.md :deep(h2), .md :deep(h3), .md :deep(h4) {
  margin: 10px 0 6px;
  font-weight: 600;
  color: var(--text-primary);
}
.md :deep(h2) { font-size: 16px; }
.md :deep(h3) { font-size: 15px; }
.md :deep(h4) { font-size: 14px; }
.md :deep(ul), .md :deep(ol) { margin: 4px 0 4px 18px; }
.md :deep(li) { margin: 2px 0; }
.md :deep(pre.code-block) {
  background: #282c34;
  color: #abb2bf;
  padding: 10px;
  border-radius: 6px;
  overflow-x: auto;
}
.md :deep(code.inline-code) {
  background: rgba(255, 255, 255, 0.1);
  padding: 1px 5px;
  border-radius: 3px;
}
.md :deep(.md-hr) {
  border: none;
  border-top: 1px solid rgba(255, 255, 255, 0.15);
  margin: 10px 0;
}
.md :deep(table.md-table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 12px;
}
.md :deep(table.md-table th),
.md :deep(table.md-table td) {
  border: 1px solid rgba(255, 255, 255, 0.15);
  padding: 4px 6px;
  text-align: left;
  vertical-align: top;
}
.md :deep(table.md-table th) {
  background: rgba(255, 255, 255, 0.08);
  font-weight: 600;
}
.md :deep(a) { color: #79bbff; }

@media (max-width: 1400px) {
  .results-layout { flex-direction: column; }
  .ai-panel { width: 100%; position: static; }
  .ai-result { max-height: 420px; }
}
</style>