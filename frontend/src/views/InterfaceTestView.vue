<template>
  <div class="cluster-view">
    <h2 class="page-title">接口测试</h2>

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
      <div class="scan-hint">扫描局域网内的设备（通过 ping 检测在线状态）</div>
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
        <el-table-column label="设备类型" min-width="200">
          <template #default="{ row }">
            <template v-if="row.chip_model">
              <el-tag type="warning" size="small">{{ row.device_type || '其他' }}</el-tag>
              <span class="chip-info">{{ row.chip_model }}</span>
              <span v-if="row.module_type" class="module-info">{{ row.module_type }}</span>
              <span v-if="row.ddr_capacity" class="ddr-info">{{ row.ddr_capacity }}</span>
            </template>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="SDK 版本" width="100">
          <template #default="{ row }">
            <span v-if="row.sdk_version" class="sdk-info">{{ row.sdk_version }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default>
            <el-tag type="success" size="small">在线</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 测试参数 -->
    <el-card shadow="never" class="section-card" v-if="selectedDevices.length">
      <template #header>接口测试 (已选 {{ selectedDevices.length }} 台设备)</template>

      <!-- Profile 选择 -->
      <div class="profile-select-row" v-if="profiles.length">
        <span class="profile-select-label">配置模板：</span>
        <el-select
          v-model="selectedProfileName"
          placeholder="选择配置模板以应用默认测试选项"
          clearable
          @change="onProfileSelect"
          style="width: 280px"
        >
          <el-option
            v-for="p in profiles"
            :key="p.name"
            :label="p.name"
            :value="p.name"
          />
        </el-select>
      </div>

      <!-- 测试项目列表 -->
      <div class="case-header">
        <span class="case-title">测试项目（已选 {{ enabledCount }}/{{ testCases.length }}）</span>
        <el-button size="small" text @click="toggleAllCases(true)" v-if="enabledCount < testCases.length">全选</el-button>
        <el-button size="small" text @click="toggleAllCases(false)" v-if="enabledCount > 0">取消全选</el-button>
      </div>

      <div class="case-groups" v-if="testCases.length">
        <div v-for="group in caseGroups" :key="group.label" class="case-group">
          <div class="case-group-label">{{ group.label }}</div>
          <div class="case-group-items">
            <el-checkbox
              v-for="c in group.cases"
              :key="c.name"
              :model-value="c.enabled"
              :label="c.label"
              @change="(val: boolean) => onCaseToggle(c, val)"
            />
          </div>
        </div>
      </div>
      <span v-if="!testCases.length" class="loading-cases">加载测试项目中...</span>

      <el-form :inline="true" style="margin-top: 16px">
        <el-form-item label="写入OEM">
          <el-switch v-model="clusterParams.writeOem" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" @click="startCluster" :loading="starting">
            开始接口测试
          </el-button>
          <el-button size="large" @click="stopCluster" v-if="activeClusters.some(c => c.status === 'running')" type="danger">
            停止测试
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 运行状态 -->
    <el-card
      shadow="never"
      class="section-card"
      v-for="cluster in activeClusters"
      :key="cluster.clusterId"
    >
      <template #header>
        <div class="cluster-card-header">
          <span class="cluster-card-title">测试状态</span>
          <el-tag size="small" type="info" style="margin-left: 8px">{{ cluster.clusterId }}</el-tag>
          <el-tag :type="statusTagType(cluster.status)" style="margin-left: 8px">{{ statusText(cluster.status) }}</el-tag>
          <span class="summary-text">
            {{ cluster.summary.completed }}/{{ cluster.summary.total }} 完成
            <span v-if="cluster.summary.failed">, {{ cluster.summary.failed }} 失败</span>
          </span>
          <el-button
            v-if="cluster.status === 'interrupted'"
            size="small"
            type="success"
            @click="resumeCluster(cluster.clusterId)"
            :loading="cluster._resuming"
            style="float: right; margin-right: 8px"
          >
            <el-icon><Refresh /></el-icon> 恢复监控
          </el-button>
          <el-button
            v-if="cluster.status === 'completed' || cluster.status === 'failed'"
            size="small"
            type="danger"
            plain
            @click="dismissCluster(cluster.clusterId)"
            style="float: right; margin-right: 8px"
          >
            <el-icon><Delete /></el-icon> 清除
          </el-button>
          <el-button size="small" @click="refreshSingleCluster(cluster)" style="float: right">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </template>
      <div class="cluster-grid">
        <el-card
          v-for="node in cluster.nodes"
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
            <div class="node-error" v-if="node.error_message">
              <el-tooltip :content="node.error_message" placement="top">
                <el-tag type="danger" size="small" effect="dark">启动失败</el-tag>
              </el-tooltip>
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
        <el-tab-pane label="系统日志" name="syslog">
          <LogViewer :logs="nodeSyslogs" />
        </el-tab-pane>
        <el-tab-pane label="测试步骤" name="steps">
          <el-table :data="nodeSteps" size="small" style="margin-top: 8px">
            <el-table-column prop="step_index" label="序号" width="60" />
            <el-table-column label="步骤" min-width="150">
              <template #default="{ row }">
                {{ row.step_label || row.step_name }}
              </template>
            </el-table-column>
            <el-table-column prop="result" label="结果" width="80">
              <template #default="{ row }">
                <el-tag :type="row.result === 'pass' ? 'success' : row.result === 'pending' ? 'info' : 'danger'" size="small">
                  {{ row.result === 'pass' ? '通过' : row.result === 'pending' ? '等待' : '失败' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="耗时" width="100">
              <template #default="{ row }">
                {{ row.duration_ms ? (row.duration_ms / 1000).toFixed(1) + 's' : '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="message" label="消息" min-width="200" show-overflow-tooltip />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'InterfaceTestView' })
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh, Delete } from '@element-plus/icons-vue'
import LogViewer from '@/components/LogViewer.vue'
import http from '@/api/http'
import { configApi } from '@/api/config'

const scanForm = reactive({ startIp: '10.80.40.1', endIp: '10.80.40.254' })
const scanning = ref(false)
const starting = ref(false)
const refreshing = ref(false)
const resuming = ref(false)
const discoveredDevices = ref<any[]>([])
const selectedDevices = ref<any[]>([])
const deviceTableRef = ref()

const clusterParams = reactive({ writeOem: false })

// 多集群支持
interface ActiveCluster {
  clusterId: string
  testType: string
  status: string
  nodes: any[]
  summary: { total: number; completed: number; failed: number; running: number }
  _resuming?: boolean
}
const activeClusters = ref<ActiveCluster[]>([])

// Profile 选择
const profiles = ref<any[]>([])
const selectedProfileName = ref('')

// 测试项目
const testCases = ref<any[]>([])
const enabledCount = computed(() => testCases.value.filter((c: any) => c.enabled).length)

// 测试用例分组定义
const caseGroupDefs: { label: string; names: string[] }[] = [
  { label: '烧录', names: ['burn_emmc', 'burn_oem', 'burn_board_sn', 'burn_device_sn', 'burn_mac', 'set_interface_flag'] },
  { label: '基础检查', names: ['chip_type_check', 'ddr_size_check', 'firmware_version_check', 'emmc_check'] },
  { label: '外设自动检查', names: ['phoenix_check', 'audio_check', 'usb_check'] },
  { label: '外设人工检查', names: ['led_check', 'hdmi_check', 'power_key_check', 'reset_key_check', 'rtc_cell_check'] },
  { label: '网络检查', names: ['eth_check', '4g_check', '5g_check', 'wifi_check', 'bluetooth_check'] },
  { label: '存储/文件', names: ['drive_check', 'upload_test_files', 'remove_test_files'] },
  { label: '串口/IO', names: ['rs232_check', 'rs485_check', 'io_check'] },
]

const caseGroups = computed(() => {
  const caseMap = new Map(testCases.value.map((c: any) => [c.name, c]))
  return caseGroupDefs.map(group => ({
    label: group.label,
    cases: group.names.map(name => caseMap.get(name)).filter(Boolean),
  })).filter(g => g.cases.length > 0)
})

const detailVisible = ref(false)
const selectedNode = ref<any>(null)
const activeTab = ref('syslog')
const nodeSyslogs = ref<any[]>([])
const nodeSteps = ref<any[]>([])

let refreshTimer: any = null
let detailRefreshTimer: any = null

onMounted(async () => {
  await loadExistingClusters()
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  if (detailRefreshTimer) clearInterval(detailRefreshTimer)
})

watch(detailVisible, (visible) => {
  if (visible) {
    detailRefreshTimer = setInterval(refreshNodeDetail, 3000)
  } else {
    if (detailRefreshTimer) clearInterval(detailRefreshTimer)
    detailRefreshTimer = null
  }
})

watch(activeTab, (tab) => {
  if (!selectedNode.value) return
  if (tab === 'syslog') {
    fetchNodeSyslog(selectedNode.value.test_id)
  }
})

// 选中设备后加载测试项目
watch(selectedDevices, (devices) => {
  if (devices.length > 0 && !testCases.value.length) {
    fetchTestCases()
  }
})

// 测试项目中英文映射
const caseLabelMap: Record<string, string> = {
  burn_emmc: '烧录eMMC',
  chip_type_check: '芯片型号检查',
  ddr_size_check: 'DDR容量检查',
  firmware_version_check: '固件版本检查',
  upload_test_files: '上传测试文件',
  burn_oem: '烧录OEM',
  led_check: 'LED检查',
  hdmi_check: 'HDMI检查',
  phoenix_check: 'Phoenix检查',
  power_key_check: '电源键检查',
  reset_key_check: '复位键检查',
  rtc_cell_check: 'RTC电池检查',
  audio_check: '音频检查',
  usb_check: 'USB检查',
  drive_check: '硬盘检查',
  eth_check: '以太网检查',
  '4g_check': '4G检查',
  '5g_check': '5G检查',
  wifi_check: 'WiFi检查',
  bluetooth_check: '蓝牙检查',
  emmc_check: 'eMMC检查',
  burn_board_sn: '烧录主板SN',
  burn_device_sn: '烧录设备SN',
  burn_mac: '烧录MAC',
  set_interface_flag: '设置接口标志',
  remove_test_files: '清理测试文件',
  rs232_check: 'RS232检查',
  rs485_check: 'RS485检查',
  io_check: 'IO检查',
}

async function fetchTestCases() {
  try {
    const res: any = await http.get('/test-types/se9_interface_test/cases')
    const cases = res.cases || []
    testCases.value = cases.map((c: any) => ({
      ...c,
      label: caseLabelMap[c.name] || c.label || c.name,
    }))
  } catch (e) {}
  // 同时加载 profile 列表
  loadProfiles()
}

async function loadProfiles() {
  try {
    const res: any = await configApi.listProfiles()
    profiles.value = res.profiles || []
  } catch (e) {}
}

async function onProfileSelect(name: string) {
  if (!name) return
  try {
    const res: any = await configApi.getProfile(name)
    const opts = res.test_options || {}
    if (Object.keys(opts).length === 0) {
      ElMessage.info('该配置暂无测试选项')
      return
    }
    // 将 profile 的测试选项应用到 UI checkbox，并持久化到后端
    for (const c of testCases.value) {
      const enabled = opts.hasOwnProperty(c.name) ? !!opts[c.name] : false
      if (c.enabled !== enabled) {
        c.enabled = enabled
        await http.put(`/test-types/se9_interface_test/cases/${c.name}`, { enabled })
      }
    }
    ElMessage.success(`已应用「${name}」的测试选项`)
  } catch (e) {
    ElMessage.error('加载配置测试选项失败')
  }
}

async function onCaseToggle(c: any, enabled: boolean) {
  try {
    await http.put(`/test-types/se9_interface_test/cases/${c.name}`, { enabled })
    c.enabled = enabled
  } catch (e) {
    // API 失败则不更新 UI
  }
}

async function toggleAllCases(enabled: boolean) {
  for (const c of testCases.value) {
    if (c.enabled !== enabled) {
      await onCaseToggle(c, enabled)
    }
  }
}

async function loadExistingClusters() {
  try {
    const res = await http.get('/tests/cluster')
    const clusters = (res as any).clusters || []
    const ifaceClusters = clusters.filter((c: any) =>
      c.test_type === 'se9_interface_test' && (c.status === 'running' || c.status === 'interrupted' || c.status === 'completed' || c.status === 'failed')
    )
    for (const c of ifaceClusters) {
      const detail: any = await http.get(`/tests/cluster/${c.cluster_id}`)
      activeClusters.value.push({
        clusterId: c.cluster_id,
        testType: c.test_type,
        status: detail.status,
        nodes: detail.nodes || [],
        summary: detail.summary || { total: 0, completed: 0, failed: 0, running: 0 },
      })
    }
    // 只对运行中或中断的集群开启轮询
    if (activeClusters.value.some(c => c.status === 'running' || c.status === 'interrupted')) {
      refreshTimer = setInterval(refreshAllClusters, 5000)
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
      } catch (e: any) {
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
    ElMessage.success(`扫描完成，发现 ${discoveredDevices.value.length} 台设备`)
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
      params: {},
    }))
    const res: any = await http.post('/tests/cluster', {
      test_type: 'se9_interface_test',
      product_model: 'SE9',
      devices,
      write_oem: clusterParams.writeOem,
      oem_profile: selectedProfileName.value || null,
    })

    await http.post(`/tests/cluster/${res.cluster_id}/start`)

    const detail: any = await http.get(`/tests/cluster/${res.cluster_id}`)
    activeClusters.value.push({
      clusterId: res.cluster_id,
      testType: 'se9_interface_test',
      status: 'running',
      nodes: detail.nodes || [],
      summary: detail.summary || { total: 0, completed: 0, failed: 0, running: 0 },
    })

    ElMessage.success(`接口测试已启动: ${res.cluster_id}`)

    if (!refreshTimer) {
      refreshTimer = setInterval(refreshAllClusters, 5000)
    }
  } catch (e: any) {
    ElMessage.error('启动失败: ' + (e?.detail || '未知错误'))
  }
  starting.value = false
}

async function stopCluster() {
  // 停止所有运行中的集群
  for (const cluster of activeClusters.value) {
    if (cluster.status === 'running') {
      try {
        await http.post(`/tests/cluster/${cluster.clusterId}/stop`)
      } catch (e) {}
    }
  }
  if (refreshTimer) clearInterval(refreshTimer)
  refreshTimer = null
  ElMessage.warning('测试已停止')
}

async function refreshAllClusters() {
  const stillActive: ActiveCluster[] = []
  for (const cluster of activeClusters.value) {
    try {
      const res: any = await http.get(`/tests/cluster/${cluster.clusterId}`)
      const status = res.status
      if (status === 'completed' || status === 'failed' || status === 'stopped') {
        continue
      }
      stillActive.push({
        ...cluster,
        status,
        nodes: res.nodes || [],
        summary: res.summary || cluster.summary,
      })
    } catch (e) {
      // API 调用失败时保留现有集群状态，避免因网络抖动导致监控卡片消失
      stillActive.push(cluster)
    }
  }
  activeClusters.value = stillActive
  if (stillActive.length === 0 && refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

async function dismissCluster(clusterId: string) {
  try {
    await http.delete(`/tests/cluster/${clusterId}`)
    activeClusters.value = activeClusters.value.filter(c => c.clusterId !== clusterId)
    ElMessage.success('已清除')
    if (activeClusters.value.length === 0 && refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  } catch (e: any) {
    ElMessage.error('清除失败: ' + (e?.detail || '未知错误'))
  }
}

async function refreshSingleCluster(cluster: ActiveCluster) {
  try {
    const res: any = await http.get(`/tests/cluster/${cluster.clusterId}`)
    cluster.status = res.status
    cluster.nodes = res.nodes || []
    cluster.summary = res.summary || cluster.summary
  } catch (e) {}
}

async function resumeCluster(clusterId: string) {
  const cluster = activeClusters.value.find(c => c.clusterId === clusterId)
  if (!cluster) return
  cluster._resuming = true
  try {
    await http.post(`/tests/cluster/${clusterId}/resume`)
    ElMessage.success('监控已恢复')
    await refreshSingleCluster(cluster)
    if (!refreshTimer) {
      refreshTimer = setInterval(refreshAllClusters, 5000)
    }
  } catch (e: any) {
    ElMessage.error('恢复失败: ' + (e?.detail || '未知错误'))
  }
  cluster._resuming = false
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

async function fetchNodeSyslog(testId: string) {
  try {
    const res: any = await http.get(`/results/${testId}/syslog`)
    const rawLines = res.lines || []
    nodeSyslogs.value = mapLogLines(rawLines, 'syslog')
  } catch (e) {}
}

async function fetchNodeSteps(testId: string) {
  try {
    const res: any = await http.get(`/results/${testId}`)
    nodeSteps.value = res.steps || []
  } catch (e) {}
}

async function viewNodeDetail(node: any) {
  selectedNode.value = node
  detailVisible.value = true
  activeTab.value = 'syslog'
  await fetchNodeSyslog(node.test_id)
  await fetchNodeSteps(node.test_id)
}

function refreshNodeDetail() {
  if (!selectedNode.value || !detailVisible.value) return
  const testId = selectedNode.value.test_id
  if (activeTab.value === 'syslog') {
    fetchNodeSyslog(testId)
  }
}

function nodeTagType(status: string) {
  const map: Record<string, string> = { running: 'warning', completed: 'success', failed: 'danger', pending: 'info', interrupted: 'warning', unknown: 'info' }
  return map[status] || 'info'
}

function nodeStatusText(status: string) {
  const map: Record<string, string> = { running: '运行中', completed: '完成', failed: '失败', pending: '等待', stopped: '已停止', interrupted: '已中断', unknown: '未知' }
  return map[status] || status
}

function statusTagType(status: string) {
  const map: Record<string, string> = { running: 'warning', completed: 'success', failed: 'danger', pending: 'info', interrupted: 'warning', unknown: 'info' }
  return map[status] || 'info'
}

function statusText(status: string) {
  const map: Record<string, string> = { running: '运行中', completed: '完成', failed: '失败', pending: '等待', stopped: '已停止', interrupted: '已中断', unknown: '未知' }
  return map[status] || status
}
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
.cluster-card-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}
.cluster-card-title {
  font-weight: 600;
  font-size: 14px;
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
.node-error {
  margin-bottom: 4px;
  cursor: help;
}
.node-step {
  margin-top: 4px;
}
.step-text {
  font-size: 11px;
  color: var(--text-secondary);
}
.summary-text {
  margin-left: 16px;
  font-size: 13px;
  color: var(--text-secondary);
}
.case-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.case-title {
  font-size: 13px;
  color: var(--text-secondary);
}
.case-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  margin-bottom: 4px;
}
.case-groups {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px 20px;
  margin-bottom: 8px;
}
.case-group {
  min-width: 0;
}
.case-group-label {
  font-size: 12px;
  color: var(--accent);
  font-weight: 600;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--border-color);
}
.case-group-items {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.loading-cases {
  font-size: 13px;
  color: var(--text-secondary);
}
.profile-select-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}
.profile-select-label {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}
.chip-info {
  display: inline-block;
  background: #e6f7ff;
  color: #1890ff;
  padding: 0 6px;
  border-radius: 3px;
  font-size: 12px;
  margin-left: 6px;
}
.module-info {
  display: inline-block;
  background: #fff7e6;
  color: #fa8c16;
  padding: 0 6px;
  border-radius: 3px;
  font-size: 12px;
  margin-left: 4px;
}
.ddr-info {
  display: inline-block;
  background: #f6ffed;
  color: #52c41a;
  padding: 0 6px;
  border-radius: 3px;
  font-size: 12px;
  margin-left: 4px;
}
.sdk-info {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--accent);
}
.text-muted { color: #999; }
</style>