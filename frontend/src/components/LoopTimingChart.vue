<template>
  <div class="loop-timing-chart">
    <!-- 摘要信息 -->
    <div class="timing-summary" v-if="summary">
      <span class="summary-item">
        总轮次: <strong>{{ summary.total_loops || 0 }}</strong>
      </span>
      <span class="summary-item" v-if="summary.reboot_cycles">
        重启次数: <strong>{{ summary.reboot_cycles }}</strong>
      </span>
      <span class="summary-item">
        状态:
        <el-tag :type="summary.is_running ? 'warning' : 'success'" size="small">
          {{ summary.is_running ? '运行中' : '已完成' }}
        </el-tag>
      </span>
    </div>

    <div v-if="data.length === 0" class="chart-empty">暂无每轮时间数据</div>
    <v-chart v-else :option="chartOption" autoresize style="height: 350px" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{
  data: { loop: number; duration: number; status?: string }[]
  summary?: { total_loops: number; reboot_cycles: number; is_running: boolean } | null
}>()

const STATUS_COLORS: Record<string, string> = {
  pass: '#67c23a',
  running: '#e6a23c',
  fail: '#f56c6c',
}

const STATUS_LABELS: Record<string, string> = {
  pass: '通过',
  running: '运行中',
  fail: '失败',
}

const chartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    formatter: (params: any) => {
      const p = params[0]
      const d = props.data[p.dataIndex]
      const statusLabel = d.status ? STATUS_LABELS[d.status] || d.status : ''
      const duration = d.duration > 0 ? `${d.duration} 秒` : '进行中'
      return `第${d.loop}轮<br/>耗时: ${duration}${statusLabel ? `<br/>状态: ${statusLabel}` : ''}`
    },
  },
  grid: { left: 60, right: 20, top: 20, bottom: 40 },
  xAxis: {
    type: 'category',
    data: props.data.map(d => `第${d.loop}轮`),
    axisLabel: { rotate: 45, fontSize: 10 },
  },
  yAxis: {
    type: 'value',
    name: '耗时 (秒)',
    nameTextStyle: { fontSize: 11 },
  },
  series: [{
    name: '每轮耗时',
    type: 'bar',
    data: props.data.map(d => ({
      value: d.duration,
      itemStyle: {
        color: STATUS_COLORS[d.status || ''] || '#409eff',
        borderRadius: [4, 4, 0, 0],
      },
    })),
    barWidth: '60%',
  }],
}))
</script>

<style scoped>
.loop-timing-chart {
  width: 100%;
}
.timing-summary {
  display: flex;
  gap: 20px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--bg-secondary, #f5f7fa);
  border-radius: 6px;
  font-size: 13px;
}
.summary-item {
  color: var(--text-secondary);
}
.summary-item strong {
  color: var(--text-primary);
}
.chart-empty {
  text-align: center;
  color: var(--text-secondary);
  padding: 60px 0;
  font-size: 14px;
}
</style>