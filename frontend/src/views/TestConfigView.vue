<template>
  <div class="config-view">
    <el-page-header @back="$router.back()" :title="'返回'" :content="pageTitle" />

    <el-card class="config-card" shadow="never">
      <template #header>测试参数配置</template>

      <el-form :model="form" label-width="120px" label-position="right">
        <el-form-item label="测试类型">
          <el-input :model-value="testTypeLabel" disabled />
        </el-form-item>

        <el-form-item label="产品型号" required>
          <el-select v-model="form.product_model" placeholder="选择产品型号" style="width: 100%">
            <el-option v-for="m in productModels" :key="m.model" :label="m.label" :value="m.model" />
          </el-select>
        </el-form-item>

        <el-form-item label="串口设备" v-if="needsSerial">
          <el-select v-model="form.serial_port" placeholder="选择串口" style="width: 100%">
            <el-option v-for="d in serialDevices" :key="d.port" :label="d.port" :value="d.port" />
          </el-select>
          <el-button type="primary" link @click="refreshSerials" style="margin-left: 8px">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </el-form-item>

        <el-form-item label="设备 IP" v-if="needsNetwork">
          <el-input v-model="form.device_ip" placeholder="输入设备 IP 地址" />
        </el-form-item>

        <el-form-item label="设备数量" v-if="isAgingTest">
          <el-input-number v-model="form.device_count" :min="1" :max="100" />
        </el-form-item>

        <template v-if="isAgingTest">
          <el-divider content-position="left">老化测试参数</el-divider>
          <el-form-item label="循环次数 (loop)">
            <el-input-number v-model="form.params.loop" :min="0" :max="9999"
              placeholder="0 表示不循环" style="width: 200px" />
            <span class="param-hint">每轮运行全部子测试（cpu/dpu/jpu/tpu/vpss/vpu）</span>
          </el-form-item>
          <el-form-item label="重启次数 (reboot)">
            <el-input-number v-model="form.params.reboot" :min="0" :max="999"
              placeholder="0 表示不重启" style="width: 200px" />
            <span class="param-hint">每次重启后自动运行 1 轮老化测试</span>
          </el-form-item>
          <el-form-item label="写入OEM信息">
            <el-switch v-model="form.params.write_oem" />
            <span class="param-hint">将 OEM 配置写入设备（产品型号相关）</span>
          </el-form-item>
        </template>

        <el-form-item>
          <el-button type="primary" size="large" @click="startTest" :loading="starting">
            开始测试
          </el-button>
          <el-button size="large" @click="$router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="config-card" shadow="never" v-if="testCases.length > 0">
      <template #header>测试用例列表</template>
      <el-table :data="testCases" style="width: 100%" size="small">
        <el-table-column prop="name" label="用例名称" />
        <el-table-column prop="label" label="描述" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-switch
              :model-value="row.enabled"
              @change="(val: boolean) => toggleCase(row.name, val)"
              size="small"
            />
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useTestStore } from '@/stores/test'
import { useDeviceStore } from '@/stores/device'
import { testApi } from '@/api/test'

const route = useRoute()
const router = useRouter()
const testStore = useTestStore()
const deviceStore = useDeviceStore()

const testType = computed(() => route.params.type as string)
const testTypeLabel = computed(() => {
  const t = testStore.testTypes.find((t: any) => t.type === testType.value)
  return t?.label || testType.value
})
const needsSerial = computed(() => {
  const t = testStore.testTypes.find((t: any) => t.type === testType.value)
  return t?.requires_serial !== false
})
const needsNetwork = computed(() => {
  const t = testStore.testTypes.find((t: any) => t.type === testType.value)
  return t?.requires_network === true
})
const isAgingTest = computed(() => testType.value === 'se9_aging_test')
const productModels = computed(() => testStore.productModels)
const serialDevices = computed(() => deviceStore.serialDevices)

const pageTitle = computed(() => `${testTypeLabel.value} - 配置`)

const form = reactive({
  test_type: testType.value,
  product_model: '',
  serial_port: '',
  device_ip: '',
  device_count: 1,
  params: { loop: 0, reboot: 0 } as Record<string, any>,
})

const testCases = ref<any[]>([])
const starting = ref(false)

onMounted(async () => {
  await deviceStore.scanSerials()
  try {
    const res: any = await testApi.getCases(testType.value)
    testCases.value = res.cases || []
  } catch (e) {}
})

async function refreshSerials() {
  await deviceStore.scanSerials()
}

async function toggleCase(caseName: string, enabled: boolean) {
  try {
    await testApi.updateCase(testType.value, caseName, enabled)
    const idx = testCases.value.findIndex((c: any) => c.name === caseName)
    if (idx >= 0) {
      testCases.value[idx].enabled = enabled
    }
    ElMessage.success(`${caseName} 已${enabled ? '启用' : '禁用'}`)
  } catch (e: any) {
    ElMessage.error(e?.detail || '更新失败')
  }
}

async function startTest() {
  if (!form.product_model) {
    ElMessage.warning('请选择产品型号')
    return
  }
  starting.value = true
  try {
    const res: any = await testApi.createTest({
      test_type: form.test_type,
      product_model: form.product_model,
      serial_port: form.serial_port || undefined,
      device_ip: form.device_ip || undefined,
      device_count: form.device_count,
      params: form.params,
    })
    await testApi.startTest(res.test_id)
    router.push({ name: 'test-run', params: { id: res.test_id } })
  } catch (e: any) {
    ElMessage.error(e?.detail || '启动测试失败')
  } finally {
    starting.value = false
  }
}
</script>

<style scoped>
.config-view {
  max-width: 900px;
  margin: 0 auto;
}
.config-card {
  margin-top: 16px;
  background-color: var(--bg-card);
  border-color: var(--border-color);
}
.param-hint {
  margin-left: 12px;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
