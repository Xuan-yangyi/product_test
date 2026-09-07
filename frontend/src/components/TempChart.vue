<template>
  <div class="temp-chart">
    <div v-if="data.length === 0" class="chart-empty">暂无温度数据</div>
    <v-chart v-else :option="chartOption" autoresize style="height: 350px" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{
  data: { time: string; temp: number }[]
}>()

const chartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    formatter: (params: any) => {
      const p = params[0]
      return `${p.axisValue}<br/>芯片温度: ${p.value} °C`
    },
  },
  grid: { left: 60, right: 20, top: 20, bottom: 40 },
  xAxis: {
    type: 'category',
    data: props.data.map(d => {
      if (!d.time) return ''
      return d.time.length > 8 ? d.time.slice(-8) : d.time
    }),
    axisLabel: { rotate: 45, fontSize: 10 },
  },
  yAxis: {
    type: 'value',
    name: '温度 (°C)',
    nameTextStyle: { fontSize: 11 },
    axisLabel: { formatter: (v: number) => v.toFixed(1) },
  },
  series: [{
    name: '芯片温度',
    type: 'line',
    data: props.data.map(d => d.temp),
    smooth: true,
    areaStyle: { opacity: 0.3 },
    lineStyle: { color: '#f56c6c', width: 2 },
    itemStyle: { color: '#f56c6c' },
    symbol: 'none',
  }],
}))
</script>

<style scoped>
.temp-chart {
  width: 100%;
}
.chart-empty {
  text-align: center;
  color: var(--text-secondary);
  padding: 60px 0;
  font-size: 14px;
}
</style>