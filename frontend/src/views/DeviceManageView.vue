<template>
  <div class="device-view">
    <h2 class="page-title">设备管理</h2>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>串口设备</span>
              <el-button type="primary" size="small" @click="scanSerials" :loading="serialLoading">
                <el-icon><Refresh /></el-icon> 刷新
              </el-button>
            </div>
          </template>
          <el-table :data="serialDevices" size="small">
            <el-table-column prop="port" label="端口" />
            <el-table-column prop="description" label="描述" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.in_use ? 'warning' : 'success'" size="small">
                  {{ row.in_use ? '使用中' : '空闲' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="serialDevices.length === 0" description="未发现串口设备" />
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>网络设备</span>
              <el-button type="primary" size="small" @click="scanNetwork" :loading="networkLoading">
                <el-icon><Refresh /></el-icon> 扫描
              </el-button>
            </div>
          </template>
          <el-table :data="networkDevices" size="small">
            <el-table-column prop="ip" label="IP 地址" />
            <el-table-column prop="hostname" label="主机名" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'online' ? 'success' : 'danger'" size="small">
                  {{ row.status === 'online' ? '在线' : '离线' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="networkDevices.length === 0" description="未发现网络设备" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="resource-card">
      <template #header>资源池状态</template>
      <el-descriptions :column="3" size="small">
        <el-descriptions-item label="管理串口数">
          {{ resourceStatus?.total_managed_ports || 0 }}
        </el-descriptions-item>
        <el-descriptions-item label="使用中">
          {{ resourceStatus?.ports_in_use || 0 }}
        </el-descriptions-item>
        <el-descriptions-item label="可用">
          {{ resourceStatus?.ports_available || 0 }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { useDeviceStore } from '@/stores/device'

const deviceStore = useDeviceStore()

const serialDevices = computed(() => deviceStore.serialDevices)
const networkDevices = computed(() => deviceStore.networkDevices)
const resourceStatus = computed(() => deviceStore.resourceStatus)

const serialLoading = ref(false)
const networkLoading = ref(false)

onMounted(() => {
  scanSerials()
  deviceStore.fetchResourceStatus()
})

async function scanSerials() {
  serialLoading.value = true
  await deviceStore.scanSerials()
  serialLoading.value = false
}

async function scanNetwork() {
  networkLoading.value = true
  await deviceStore.scanNetwork()
  networkLoading.value = false
}
</script>

<style scoped>
.device-view {
  max-width: 1200px;
  margin: 0 auto;
}
.page-title {
  font-size: 24px;
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.resource-card {
  margin-top: 20px;
  background-color: var(--bg-card);
  border-color: var(--border-color);
}
</style>
