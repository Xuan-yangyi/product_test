<template>
  <div class="results-view">
    <h2 class="page-title">测试结果</h2>

    <div class="results-layout">
      <!-- 左侧：统计 + 筛选 + 结果表 -->
      <div class="results-main">
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
          <div class="table-head">
            <span class="sel-hint">已勾选 {{ selectedIds.length }} 台（支持跨页勾选）</span>
            <el-button link size="small" @click="clearSelection">清空勾选</el-button>
          </div>
          <el-table
            ref="tableRef"
            :data="results"
            style="width: 100%"
            v-loading="loading"
            size="small"
            row-key="test_id"
            @selection-change="onSelectionChange"
          >
            <el-table-column type="selection" width="44" reserve-selection />
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
              <template #default="{ row }">{{ formatDuration(row.duration_seconds) }}</template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="170" />
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="viewDetail(row.test_id)">查看</el-button>
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

      <!-- 右侧：AI 汇总分析入口 -->
      <aside class="ai-panel">
        <el-card shadow="never" class="ai-card">
          <template #header>
            <div class="ai-head">
              <span class="ai-title">AI 汇总分析</span>
              <el-tag size="small" :type="engineTagType">{{ engineLabel }}</el-tag>
            </div>
          </template>

          <div class="ai-scope">
            <div class="scope-row">
              <span class="scope-label">分析范围</span>
              <el-radio-group v-model="aiScope" size="small">
                <el-radio-button label="selected">已勾选 {{ selectedIds.length }}</el-radio-button>
                <el-radio-button label="filtered">当前筛选</el-radio-button>
                <el-radio-button label="batch">按批次</el-radio-button>
              </el-radio-group>
            </div>

            <el-select
              v-if="aiScope === 'batch'"
              v-model="aiBatch"
              size="small"
              placeholder="选择测试批次（最近 30 天）"
              style="width: 100%"
            >
              <el-option v-for="b in batches" :key="b.cluster_id" :value="b.cluster_id" :label="batchLabel(b)" />
            </el-select>

            <div class="scope-row">
              <span class="scope-label">产品线</span>
              <el-checkbox v-model="pls.SE13">SE13</el-checkbox>
              <el-checkbox v-model="pls.Athena2">Athena2（SE9/EVB）</el-checkbox>
            </div>
          </div>

          <div class="ai-actions">
            <el-button
              type="primary"
              @click="generateReport('interface')"
              :loading="aiLoading && aiKind === 'interface'"
              :disabled="aiLoading"
            >
              快速分析接口测试报告
            </el-button>
            <el-button
              type="success"
              @click="generateReport('aging')"
              :loading="aiLoading && aiKind === 'aging'"
              :disabled="aiLoading"
            >
              快速分析老化日志报告
            </el-button>
            <el-button
              type="warning"
              @click="generateReport('all')"
              :loading="aiLoading && aiKind === 'all'"
              :disabled="aiLoading"
            >
              汇总测试报告
            </el-button>
          </div>

          <div class="ai-status">
            <template v-if="aiLoading">正在生成报告（约 30~90 秒），生成后会自动打开新页面…</template>
            <template v-else-if="lastReportId">
              已生成报告
              <el-button link type="primary" size="small" @click="openReport(lastReportId)">查看报告</el-button>
            </template>
            <template v-else>
              选择范围与产品线后点击按钮，报告将在新页面全宽展示（可打印/导出）
            </template>
          </div>
        </el-card>
      </aside>
    </div>

    <el-dialog
      v-model="reportDialog"
      :title="reportData?.title || 'AI 汇总分析报告'"
      width="92%"
      top="4vh"
      destroy-on-close
      class="ai-report-dialog"
    >
      <div v-loading="reportLoading" class="report-dialog-body">
        <AiReportContent v-if="reportData" :report="reportData" @close="reportDialog = false" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import ResultBadge from '@/components/ResultBadge.vue'
import AiReportContent from '@/components/AiReportContent.vue'
import { testApi } from '@/api/test'
import http from '@/api/http'
import { useTestStore } from '@/stores/test'

const router = useRouter()
const testStore = useTestStore()

const testTypes = ref<any[]>([])
const results = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const exporting = ref(false)
const dateRange = ref<string[]>([])

const stats = reactive({ total: 0, completed: 0, failed: 0, pass_rate: 0 })

const filters = reactive({
  serial_number: '',
  test_type: '',
  status: '',
  start_date: '',
  end_date: '',
  page: 1,
  page_size: 20,
})

// ---------------- 勾选 ----------------
const selectedIds = ref<string[]>([])
const tableRef = ref()

function onSelectionChange(rows: any[]) {
  selectedIds.value = rows.map(r => r.test_id)
}
function clearSelection() {
  tableRef.value?.clearSelection()
  selectedIds.value = []
}

// ---------------- AI 汇总 ----------------
const aiLoading = ref(false)
const aiKind = ref('')
const aiScope = ref<'selected' | 'filtered' | 'batch'>('selected')
const aiBatch = ref('')
const batches = ref<any[]>([])
const pls = reactive({ SE13: true, Athena2: true })
const lastReportId = ref('')
const reportDialog = ref(false)
const reportData = ref<any>(null)
const reportLoading = ref(false)
const engine = ref<any>({ claude_available: false, provider_pref: 'auto' })

const engineLabel = computed(() => {
  if (engine.value.provider_pref === 'api') return 'API 模式'
  if (engine.value.provider_pref === 'claude') return 'Claude 模式'
  return engine.value.claude_available ? 'Claude 优先' : 'API 模式'
})
const engineTagType = computed(() => (engine.value.claude_available ? 'success' : 'info'))

onMounted(async () => {
  await testStore.fetchTypes()
  testTypes.value = testStore.testTypes
  search()
  fetchStats()
  fetchEngine()
})

watch(aiScope, async (v) => {
  if (v === 'batch' && !batches.value.length) await fetchBatches()
})

async function fetchEngine() {
  try {
    engine.value = (await http.get('/ai/summary/engine')) || engine.value
  } catch (e) {}
}

async function fetchBatches() {
  try {
    const res: any = await http.get('/result-batches', { params: { days: 30, limit: 30 } })
    batches.value = res.batches || []
  } catch (e) {
    batches.value = []
  }
}

function batchLabel(b: any) {
  const t = (b.last_at || '').slice(5, 16).replace('T', ' ')
  const type = (b.test_type || '').replace('_test', '')
  return `${b.cluster_id} · ${b.count}台 · ${b.failed || 0}失败 · ${type} · ${t}`
}

function summaryFilters() {
  const f: any = {}
  if (filters.status) f.status = filters.status
  if (filters.serial_number) f.serial_number = filters.serial_number
  if (filters.start_date) f.start_date = filters.start_date
  if (filters.end_date) f.end_date = filters.end_date
  return f
}

async function generateReport(kind: 'interface' | 'aging' | 'all') {
  if (aiLoading.value) return
  const product_lines: string[] = []
  if (pls.SE13) product_lines.push('SE13')
  if (pls.Athena2) product_lines.push('Athena2')
  if (!product_lines.length) {
    ElMessage.warning('请至少选择一个产品线')
    return
  }
  if (aiScope.value === 'selected' && !selectedIds.value.length) {
    ElMessage.warning('请先在结果表中勾选设备，或切换分析范围')
    return
  }
  if (aiScope.value === 'batch') {
    if (!aiBatch.value) {
      ElMessage.warning('请选择一个测试批次')
      return
    }
    if (!batches.value.length) await fetchBatches()
  }

  aiLoading.value = true
  aiKind.value = kind
  try {
    const params: any = {
      scope: aiScope.value,
      product_lines,
      filters: summaryFilters(),
      limit: 500,
    }
    if (aiScope.value === 'selected') params.test_ids = selectedIds.value
    if (aiScope.value === 'batch') params.cluster_id = aiBatch.value

    const res: any = await http.post(`/ai/summary/${kind}`, params, { timeout: 300000 } as any)
    if (!res.report_id) {
      ElMessage.warning(res.analysis || '未生成报告')
      return
    }
    lastReportId.value = res.report_id
    openReport(res.report_id)
  } catch (e: any) {
    ElMessage.error('AI 汇总分析失败: ' + (e?.detail || e?.message || '未知错误'))
  } finally {
    aiLoading.value = false
    aiKind.value = ''
  }
}

async function openReport(id: string) {
  reportDialog.value = true
  reportLoading.value = true
  reportData.value = null
  try {
    reportData.value = await http.get(`/ai/summary/report/${id}`)
  } catch (e: any) {
    ElMessage.error('报告不存在或已过期，请重新生成')
    reportDialog.value = false
  } finally {
    reportLoading.value = false
  }
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
    Object.assign(stats, (await testApi.getStatistics()) || {})
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
.stats-row { margin-bottom: 16px; }
.stat-card {
  text-align: center;
  background-color: var(--bg-card);
  border-color: var(--border-color);
}
.stat-value { font-size: 28px; font-weight: 700; color: var(--text-primary); }
.stat-label { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }
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
.table-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.sel-hint { font-size: 12px; color: var(--text-secondary); }

/* ---------------- AI 面板 ---------------- */
.ai-panel { width: 400px; flex-shrink: 0; position: sticky; top: 16px; }
.ai-card {
  background-color: var(--bg-card);
  border-color: var(--border-color);
}
.ai-head { display: flex; align-items: center; justify-content: space-between; }
.ai-title { font-weight: 600; color: var(--text-primary); }
.ai-scope { display: flex; flex-direction: column; gap: 10px; margin-bottom: 12px; }
.scope-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.scope-label { font-size: 12px; color: var(--text-secondary); min-width: 56px; }
.ai-actions { display: flex; flex-direction: column; gap: 8px; }
.ai-actions .el-button { width: 100%; margin-left: 0; }
.ai-status {
  margin-top: 12px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
}
@media (max-width: 1400px) {
  .results-layout { flex-direction: column; }
  .ai-panel { width: 100%; position: static; }
}
</style>

<style>
/* 报告弹窗：浅色风格（白底 + 深色字） */
.ai-report-dialog {
  --el-dialog-bg-color: #ffffff;
  --el-dialog-title-font-size: 18px;
  background-color: #ffffff;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
}
.ai-report-dialog .el-dialog__header {
  border-bottom: 1px solid #ebeef5;
  margin-right: 0;
  padding-bottom: 12px;
}
.ai-report-dialog .el-dialog__title { color: #1f2d3d; font-weight: 600; }
.ai-report-dialog .el-dialog__headerbtn .el-dialog__close { color: #909399; }
.ai-report-dialog .el-dialog__headerbtn:hover .el-dialog__close { color: #303133; }
.ai-report-dialog .el-dialog__body {
  max-height: 78vh;
  overflow-y: auto;
  padding-top: 12px;
  color: #303133;
}
.report-dialog-body { min-height: 240px; }

/* 内容区浅色覆盖（组件内部默认跟随暗色主题变量） */
.ai-report-dialog .ai-report-content { color: #303133; }
.ai-report-dialog .ai-report-content .report-title { color: #1f2d3d; border-bottom-color: #409eff; }
.ai-report-dialog .ai-report-content .meta { color: #606266; }
.ai-report-dialog .ai-report-content .stat b { color: #303133; }
.ai-report-dialog .ai-report-content .stat span { color: #909399; }
.ai-report-dialog .ai-report-content .stat.ok b { color: #67c23a; }
.ai-report-dialog .ai-report-content .stat.bad b { color: #f56c6c; }
.ai-report-dialog .ai-report-content .stat.muted b { color: #909399; }
.ai-report-dialog .ai-report-content .groups th,
.ai-report-dialog .ai-report-content .groups td { border-color: #dcdfe6; }
.ai-report-dialog .ai-report-content .groups th { background: #f5f7fa; color: #303133; }
.ai-report-dialog .ai-report-content .groups .ok { color: #67c23a; }
.ai-report-dialog .ai-report-content .groups .bad { color: #f56c6c; }
.ai-report-dialog .ai-report-content .md { color: #303133; }
.ai-report-dialog .ai-report-content .md h2,
.ai-report-dialog .ai-report-content .md h3,
.ai-report-dialog .ai-report-content .md h4 { color: #1f2d3d; }
.ai-report-dialog .ai-report-content .md .md-hr { border-top-color: #ebeef5; }
.ai-report-dialog .ai-report-content .md table.md-table th,
.ai-report-dialog .ai-report-content .md table.md-table td { border-color: #dcdfe6; }
.ai-report-dialog .ai-report-content .md table.md-table th { background: #f5f7fa; }
.ai-report-dialog .ai-report-content .md code.inline-code { background: rgba(0,0,0,0.06); color: #c7254e; }
.ai-report-dialog .ai-report-content .md a { color: #409eff; }
</style>