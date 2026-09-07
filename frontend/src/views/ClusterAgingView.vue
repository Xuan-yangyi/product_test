<template>
  <div class="cluster-view">
    <h2 class="page-title">集群老化测试</h2>

    <!-- IP 段扫描 -->
    <el-card shadow="never" class="section-card">
      <template #header>IP 段扫描</template>
      <el-form :inline="true">
        <el-form-item label="起始 IP">
          <el-input v-model="scanForm.startIp" placeholder="10.80.40.1" style="width: 150px" />
        </el-form-item>
        <el-form-item label="结束 IP">
          <el-input v-model="scanForm.endIp" placeholder="10.80.40.254" style="width: 150px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="scanIPs" :loading="scanning">
            <el-icon><Search /></el-icon> 扫描设备
          </el-button>
        </el-form-item>
      </el-form>
      <div class="scan-hint">扫描局域网内的 SE9 设备（通过 ping 检测在线状态）</div>
    </el-card>

    <!-- 发现的设备 -->
    <el-card shadow="never" class="section-card" v-if="discoveredDevices.length">
      <template #header>
        <span>发现设备 ({{ discoveredDevices.length }} 台)</span>
        <el-button size="small" type="primary" @click="selectAll">全选</el-button>
      </template>
      <el-table
        :data="discoveredDevices"
        ref="deviceTableRef"
        @selection-change="handleSelect"
        size="small"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="ip" label="IP 地址" width="150" />
        <el-table-column prop="hostname" label="主机名" min-width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag type="success" size="small">在线</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 老化参数 -->
    <el-card shadow="never" class="section-card" v-if="selectedDevices.length">
      <template #header>老化参数 (已选 {{ selectedDevices.length }} 台设备)</template>
      <el-form :inline="true">
        <el-form-item label="循环次数">
          <el-input-number v-model="clusterParams.loop" :min="0" :max="9999" />
        </el-form-item>
        <el-form-item label="重启次数">
          <el-input-number v-model="clusterParams.reboot" :min="0" :max="999" />
        </el-form-item>
        <el-form-item label="写入OEM">
          <el-switch v-model="clusterParams.writeOem" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" @click="startCluster" :loading="starting">
            开始集群老化
          </el-button>
          <el-button size="large" @click="stopCluster" v-if="clusterStatus === 'running'" type="danger">
            停止集群
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 集群运行状态 -->
    <el-card shadow="never" class="section-card" v-if="clusterNodes.length">
      <template #header>
        <span>集群状态</span>
        <el-tag :type="statusTagType" style="margin-left: 12px">{{ clusterStatus }}</el-tag>
        <span class="summary-text">
          {{ summary.completed }}/{{ summary.total }} 完成
          <span v-if="summary.failed">, {{ summary.failed }} 失败</span>
        </span>
        <el-button size="small" @click="refreshCluster" :loading="refreshing" style="float: right">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </template>
      <div class="cluster-grid">
        <el-card
          v-for="node in clusterNodes"
          :key="node.test_id"
          class="node-card"
          :class="node.status"
          shadow="hover"
          @click="viewNodeDetail(node)"
        >
          <div class="node-header">
            <span class="node-ip">{{ node.device_ip }}</span>
            <el-tag :type="nodeTagType(node.status)" size="small">{{ nodeStatusText(node.status) }}</el-tag>
          </div>
          <div class="node-body">
            <div class="node-temp" v-if="node.currentTemp">
              🌡️ {{ node.currentTemp }}°C
            </div>
            <div class="node-step" v-if="node.current_step">
              <el-progress
                :percentage="Math.round((node.current_step / (node.total_steps || 1)) * 100)"
                :stroke-width="6"
                :color="node.status === 'failed' ? '#f56c6c' : '#409eff'"
              />
              <span class="step-text">步骤 {{ node.current_step }}/{{ node.total_steps }}</span>
            </div>
          </div>
        </el-card>
      </div>
    </el-card>

    <!-- 节点详情弹窗 -->
    <el-dialog
      v-model="detailVisible"
      :title="'节点详情: ' + selectedNode?.device_ip"
      width="85%"
      destroy-on-close
    >
      <el-tabs v-model="activeTab" v-if="selectedNode">
        <el-tab-pane label="老化日志" name="log">
          <LogViewer :logs="nodeLogs" />
        </el-tab-pane>
        <el-tab-pane label="系统日志" name="syslog">
          <LogViewer :logs="nodeSyslogs" />
        </el-tab-pane>
        <el-tab-pane label="温度曲线" name="temp">
          <TempChart :data="temperatureData" />
        </el-tab-pane>
        <el-tab-pane label="每轮时间分布" name="timing">
          <LoopTimingChart :data="loopTimingData" />
        </el-tab-pane>
        <el-tab-pane label="模块日志" name="moduleLog">
          <div class="module-toolbar">
            <el-select v-model="selectedModule" placeholder="选择模块" @change="onModuleChange" size="small" style="width: 200px">
              <el-option v-for="m in moduleNames" :key="m.value" :label="m.label" :value="m.value" />
            </el-select>
            <span class="module-hint" v-if="moduleLogCount > 0">共 {{ moduleLogCount }} 行</span>
          </div>
          <LogViewer :logs="moduleLogs" />
        </el-tab-pane>
        <el-tab-pane label="AI 分析" name="ai">
          <AiChat ref="aiChatRef" :test-id="selectedNode?.test_id" />
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh } from '@element-plus/icons-vue'
import LogViewer from '@/components/LogViewer.vue'
import TempChart from '@/components/TempChart.vue'
import LoopTimingChart from '@/components/LoopTimingChart.vue'
import AiChat from '@/components/AiChat.vue'
import http from '@/api/http'

const scanForm = reactive({ startIp: '10.80.40.1', endIp: '10.80.40.254' })
const scanning = ref(false)
const starting = ref(false)
const refreshing = ref(false)
const discoveredDevices = ref<any[]>([])
const selectedDevices = ref<any[]>([])
const deviceTableRef = ref()

const clusterParams = reactive({ loop: 1, reboot: 0, writeOem: false })
const clusterId = ref('')
const clusterStatus = ref('')
const clusterNodes = ref<any[]>([])
const summary = reactive({ total: 0, completed: 0, failed: 0 })

const detailVisible = ref(false)
const selectedNode = ref<any>(null)
const activeTab = ref('log')
const nodeLogs = ref<any[]>([])
const nodeSyslogs = ref<any[]>([])
const temperatureData = ref<any[]>([])
const loopTimingData = ref<any[]>([])

// AI 分析
const aiChatRef = ref()

// 模块日志
const moduleNames = [
  { value: 'cpu', label: 'CPU' },
  { value: 'dpu', label: 'DPU' },
  { value: 'jpu', label: 'JPU' },
  { value: 'tpu', label: 'TPU' },
  { value: 'vpss_convertto', label: 'VPSS ConvertTo' },
  { value: 'vpss_csc', label: 'VPSS CSC' },
  { value: 'vpu_dec', label: 'VPU Dec' },
  { value: 'vpu_enc', label: 'VPU Enc' },
]
const selectedModule = ref('')
const moduleLogs = ref<any[]>([])
const moduleLogCount = ref(0)

let refreshTimer: any = null
let detailRefreshTimer: any = null

onMounted(async () => {
  await loadExistingClusters()
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  if (detailRefreshTimer) clearInterval(detailRefreshTimer)
})

// 节点详情弹窗打开时自动刷新日志，关闭时停止
watch(detailVisible, (visible) => {
  if (visible) {
    detailRefreshTimer = setInterval(refreshNodeDetail, 3000)
  } else {
    if (detailRefreshTimer) clearInterval(detailRefreshTimer)
    detailRefreshTimer = null
  }
})

// 切换 tab 时刷新对应数据
watch(activeTab, (tab) => {
  if (!selectedNode.value) return
  if (tab === 'log') {
    fetchNodeLogs(selectedNode.value.test_id)
  } else if (tab === 'syslog') {
    fetchNodeSyslog(selectedNode.value.test_id)
  } else if (tab === 'temp') {
    fetchNodeTemperature(selectedNode.value.test_id)
  } else if (tab === 'timing') {
    fetchNodeLoopTiming(selectedNode.value.test_id)
  } else if (tab === 'moduleLog') {
    fetchModuleLog()
  } else if (tab === 'ai') {
    // AI 分析 tab，组件自身处理
  }
})

async function loadExistingClusters() {
  try {
    const res = await http.get('/tests/cluster')
    const clusters = (res as any).clusters || []
    if (clusters.length > 0) {
      const latest = clusters[clusters.length - 1]
      clusterId.value = latest.cluster_id
      await refreshCluster()
    }
  } catch (e) {}
}

async function scanIPs() {
  scanning.value = true
  discoveredDevices.value = []
  try {
    const startParts = scanForm.startIp.split('.').map(Number)
    const endParts = scanForm.endIp.split('.').map(Number)
    const startNum = (startParts[0] << 24) | (startParts[1] << 16) | (startParts[2] << 8) | startParts[3]
    const endNum = (endParts[0] << 24) | (endParts[1] << 16) | (endParts[2] << 8) | endParts[3]

    if (endNum < startNum || endNum - startNum > 65535) {
      ElMessage.warning('IP 范围无效或过大（最多扫描 65535 个 IP）')
      scanning.value = false
      return
    }

    // 分批扫描，每批 50 个 IP
    const batchSize = 50
    const total = endNum - startNum + 1
    const batches = Math.ceil(total / batchSize)
    ElMessage.info(`开始扫描 ${total} 个 IP...`)

    for (let b = 0; b < batches; b++) {
      const batchStart = startNum + b * batchSize
      const batchEnd = Math.min(batchStart + batchSize - 1, endNum)
      const ips = []
      for (let i = batchStart; i <= batchEnd; i++) {
        ips.push(`${(i >> 24) & 0xff}.${(i >> 16) & 0xff}.${(i >> 8) & 0xff}.${i & 0xff}`)
      }

      try {
        const res: any = await http.post('/devices/network/scan', { ips })
        const found = res.devices || []
        discoveredDevices.value.push(...found)
        ElMessage.success(`已扫描 ${Math.min(batchEnd - startNum + 1, total)}/${total}，发现 ${discoveredDevices.value.length} 台设备`)
      } catch (e: any) {
        // 如果批量扫描 API 不存在，使用单个 ping 的方式
        for (const ip of ips) {
          try {
            const checkRes: any = await http.get(`/devices/network/${ip}/info`)
            if (checkRes.device) {
              discoveredDevices.value.push({ ip, hostname: checkRes.device.hostname || '', status: 'online' })
            }
          } catch (e) {}
        }
      }
    }
  } catch (e: any) {
    ElMessage.error('扫描失败: ' + (e?.detail || '未知错误'))
  }
  scanning.value = false
}

function handleSelect(rows: any[]) {
  selectedDevices.value = rows
}

function selectAll() {
  deviceTableRef.value?.toggleAllSelection()
}

async function startCluster() {
  if (!selectedDevices.value.length) {
    ElMessage.warning('请先选择设备')
    return
  }
  starting.value = true
  try {
    const devices = selectedDevices.value.map((d: any) => ({
      ip: d.ip,
      params: { loop: clusterParams.loop, reboot: clusterParams.reboot },
    }))
    const res: any = await http.post('/tests/cluster', {
      test_type: 'se9_aging_test',
      product_model: 'SE9',
      devices,
      write_oem: clusterParams.writeOem,
    })
    clusterId.value = res.cluster_id
    clusterStatus.value = res.status

    // 启动集群
    await http.post(`/tests/cluster/${clusterId.value}/start`)
    clusterStatus.value = 'running'

    ElMessage.success(`集群老化已启动: ${clusterId.value}`)
    await refreshCluster()

    // 定时刷新
    refreshTimer = setInterval(refreshCluster, 5000)
  } catch (e: any) {
    ElMessage.error('启动集群失败: ' + (e?.detail || '未知错误'))
  }
  starting.value = false
}

async function stopCluster() {
  if (!clusterId.value) return
  try {
    await http.post(`/tests/cluster/${clusterId.value}/stop`)
    clusterStatus.value = 'stopped'
    if (refreshTimer) clearInterval(refreshTimer)
    ElMessage.warning('集群已停止')
  } catch (e: any) {
    ElMessage.error('停止失败: ' + (e?.detail || '未知错误'))
  }
}

async function refreshCluster() {
  if (!clusterId.value) return
  refreshing.value = true
  try {
    const res: any = await http.get(`/tests/cluster/${clusterId.value}`)
    clusterNodes.value = res.nodes || []
    clusterStatus.value = res.status
    Object.assign(summary, res.summary || {})
    if (res.status === 'completed' || res.status === 'failed' || res.status === 'stopped') {
      if (refreshTimer) clearInterval(refreshTimer)
    }
  } catch (e) {}
  refreshing.value = false
}

function mapLogLines(rawLines: any[], source: string): any[] {
  return rawLines.map((l: any) => {
    if (typeof l === 'string') {
      return { timestamp: new Date().toISOString(), level: 'INFO', source, message: l }
    }
    return {
      timestamp: l.timestamp || new Date().toISOString(),
      level: l.level || 'INFO',
      source: l.source || source,
      message: l.message || String(l),
    }
  })
}

async function fetchNodeLogs(testId: string) {
  try {
    const res: any = await http.get(`/results/${testId}/logs`)
    const rawLines = res.lines || res.logs || []
    nodeLogs.value = mapLogLines(rawLines, 'aging')
  } catch (e) {}
}

async function fetchNodeSyslog(testId: string) {
  try {
    const res: any = await http.get(`/results/${testId}/syslog`)
    const rawLines = res.lines || []
    nodeSyslogs.value = mapLogLines(rawLines, 'syslog')
  } catch (e) {}
}

async function fetchNodeTemperature(testId: string) {
  try {
    const res: any = await http.get(`/tests/${testId}/temperature`)
    temperatureData.value = res.data || []
  } catch (e) {}
}

async function fetchNodeLoopTiming(testId: string) {
  try {
    const res: any = await http.get(`/tests/${testId}/loop-timing`)
    loopTimingData.value = res.data || []
  } catch (e) {}
}

async function fetchModuleLog() {
  if (!selectedNode.value || !selectedModule.value) return
  const testId = selectedNode.value.test_id
  try {
    const res: any = await http.get(`/tests/${testId}/module-log/${selectedModule.value}`)
    const rawLines = res.lines || []
    moduleLogs.value = mapLogLines(rawLines, `aging-${selectedModule.value}`)
    moduleLogCount.value = res.count || 0
  } catch (e) {}
}

function onModuleChange() {
  fetchModuleLog()
}

async function viewNodeDetail(node: any) {
  selectedNode.value = node
  detailVisible.value = true
  activeTab.value = 'log'
  await fetchNodeLogs(node.test_id)
}

function refreshNodeDetail() {
  if (!selectedNode.value || !detailVisible.value) return
  const testId = selectedNode.value.test_id
  // 只刷新当前激活的 tab 数据
  if (activeTab.value === 'log') {
    fetchNodeLogs(testId)
  } else if (activeTab.value === 'syslog') {
    fetchNodeSyslog(testId)
  } else if (activeTab.value === 'temp') {
    fetchNodeTemperature(testId)
  } else if (activeTab.value === 'timing') {
    fetchNodeLoopTiming(testId)
  } else if (activeTab.value === 'moduleLog') {
    fetchModuleLog()
  } else if (activeTab.value === 'ai') {
    // AI 分析 tab，组件自身处理
  }
}

function nodeTagType(status: string) {
  const map: Record<string, string> = { running: 'warning', completed: 'success', failed: 'danger', pending: 'info' }
  return map[status] || 'info'
}

function nodeStatusText(status: string) {
  const map: Record<string, string> = { running: '运行中', completed: '完成', failed: '失败', pending: '等待', stopped: '已停止' }
  return map[status] || status
}

const statusTagType = computed(() => {
  const map: Record<string, string> = { running: 'warning', completed: 'success', failed: 'danger', pending: 'info' }
  return map[clusterStatus.value] || 'info'
})
</script>

<style scoped>
.cluster-view {
  max-width: 1400px;
  margin: 0 auto;
}
.page-title {
  font-size: 24px;
  margin-bottom: 16px;
}
.section-card {
  margin-bottom: 16px;
  background-color: var(--bg-card);
  border-color: var(--border-color);
}
.scan-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 8px;
}
.cluster-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.node-card {
  cursor: pointer;
  border: 2px solid var(--border-color);
  transition: border-color 0.3s;
}
.node-card:hover {
  border-color: var(--accent);
}
.node-card.running {
  border-color: #e6a23c;
}
.node-card.completed {
  border-color: #67c23a;
}
.node-card.failed {
  border-color: #f56c6c;
}
.node-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.node-ip {
  font-weight: bold;
  font-family: var(--font-mono);
  font-size: 14px;
}
.node-body {
  font-size: 12px;
}
.node-temp {
  color: #f56c6c;
  margin-bottom: 4px;
}
.node-step {
  margin-top: 4px;
}
.step-text {
  font-size: 11px;
  color: var(--text-secondary);
}
.summary-text {
  margin-left: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}
.module-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.module-hint {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>