<template>
  <div class="loop-timing-chart">
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
  data: { loop: number; duration: number }[]
}>()

const chartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    formatter: (params: any) => {
      const p = params[0]
      return `第${p.axisValue}轮<br/>耗时: ${p.value} 秒`
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
    data: props.data.map(d => d.duration),
    itemStyle: {
      color: '#409eff',
      borderRadius: [4, 4, 0, 0],
    },
    barWidth: '60%',
  }],
}))
</script>

<style scoped>
.loop-timing-chart {
  width: 100%;
}
.chart-empty {
  text-align: center;
  color: var(--text-secondary);
  padding: 60px 0;
  font-size: 14px;
}
</style>