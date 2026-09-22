<template>
  <div class="config-view">
    <div class="page-header">
      <h2 class="page-title">配置管理</h2>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon> 新建配置
      </el-button>
    </div>

    <div class="profile-layout" v-if="profiles.length > 0">
      <!-- 左侧 Profile 列表 -->
      <el-card shadow="never" class="profile-list-card">
        <template #header>配置列表 ({{ profiles.length }})</template>
        <div
          v-for="p in profiles"
          :key="p.name"
          class="profile-item"
          :class="{ active: selectedName === p.name }"
          @click="selectProfile(p.name)"
        >
          <div class="profile-name">{{ p.name }}</div>
          <div class="profile-meta">
            <el-tag size="small" type="info" v-if="p.product_model">{{ p.product_model }}</el-tag>
            <span class="profile-date">{{ formatDate(p.updated_at || p.created_at) }}</span>
          </div>
        </div>
      </el-card>

      <!-- 右侧详情 -->
      <el-card shadow="never" class="profile-detail-card" v-if="selectedProfile">
        <template #header>
          <div class="detail-header">
            <span>{{ selectedProfile.name }}</span>
            <el-button type="danger" size="small" plain @click="handleDelete">
              <el-icon><Delete /></el-icon> 删除
            </el-button>
          </div>
        </template>

        <!-- OEM 配置 -->
        <div class="oem-section">
          <div class="section-toolbar">
            <span class="section-label">OEMconfig.ini</span>
            <el-upload
              :auto-upload="false"
              :on-change="handleOEMReplace"
              accept=".ini,.cfg,.conf"
              :show-file-list="false"
            >
              <el-button size="small" type="primary" plain>替换文件</el-button>
            </el-upload>
          </div>
          <div class="oem-content">
            <pre><code>{{ selectedProfile.oem_content || '(空)' }}</code></pre>
          </div>
        </div>

        <!-- 测试选项 -->
        <el-divider />
        <div class="test-options-section">
          <div class="section-toolbar">
            <span class="section-label">接口测试选项（已选 {{ testEnabledCount }}/{{ testCaseDefs.length }}）</span>
            <div class="test-actions">
              <el-button size="small" text @click="toggleAllTestOpts(true)" v-if="testEnabledCount < testCaseDefs.length">全选</el-button>
              <el-button size="small" text @click="toggleAllTestOpts(false)" v-if="testEnabledCount > 0">取消全选</el-button>
              <el-button size="small" type="primary" @click="saveTestOptions" :loading="savingOpts">保存测试选项</el-button>
            </div>
          </div>
          <div class="case-groups" v-if="testCaseGroups.length">
            <div v-for="group in testCaseGroups" :key="group.label" class="case-group">
              <div class="case-group-label">{{ group.label }}</div>
              <div class="case-group-items">
                <el-checkbox
                  v-for="c in group.cases"
                  :key="c.name"
                  v-model="testOpts[c.name]"
                  :label="c.label"
                />
              </div>
            </div>
          </div>
          <span v-else class="loading-hint">加载测试项目中...</span>
        </div>
      </el-card>
    </div>

    <!-- 空状态 -->
    <el-empty v-else description="暂无配置，点击「新建配置」创建" />

    <!-- 创建对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建配置" width="500px" destroy-on-close>
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="配置名称" required>
          <el-input v-model="createForm.name" placeholder="如 SE9-16-BP1-18" />
          <div class="form-tip">格式：产品型号-模块型号，如 SE9-16-BP1-18</div>
        </el-form-item>
        <el-form-item label="OEM 配置文件" required>
          <el-upload
            drag
            :auto-upload="false"
            :on-change="handleCreateFile"
            accept=".ini,.cfg,.conf"
            :limit="1"
          >
            <el-icon :size="40"><UploadFilled /></el-icon>
            <div class="upload-text">拖拽或点击上传 OEMconfig.ini</div>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="creating">
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, UploadFilled } from '@element-plus/icons-vue'
import { configApi } from '@/api/config'
import http from '@/api/http'

interface Profile {
  name: string
  product_model: string
  created_at: string
  updated_at: string
  oem_size: number
  oem_content?: string
  test_options?: Record<string, boolean>
}

// 测试项目中英文映射（与 InterfaceTestView 保持一致）
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
}

const profiles = ref<Profile[]>([])
const selectedName = ref('')
const selectedProfile = ref<Profile | null>(null)
const showCreateDialog = ref(false)
const creating = ref(false)
const savingOpts = ref(false)

const createForm = ref({ name: '' })
let createFile: File | null = null

// 测试选项
const testCaseDefs = ref<{ name: string; label: string }[]>([])
const testOpts = reactive<Record<string, boolean>>({})
const testEnabledCount = computed(() => Object.values(testOpts).filter(Boolean).length)

// 测试用例分组定义
const caseGroupDefs: { label: string; names: string[] }[] = [
  { label: '烧录', names: ['burn_emmc', 'burn_oem', 'burn_board_sn', 'burn_device_sn', 'burn_mac', 'set_interface_flag'] },
  { label: '基础检查', names: ['chip_type_check', 'ddr_size_check', 'firmware_version_check', 'emmc_check'] },
  { label: '外设检查', names: ['led_check', 'hdmi_check', 'phoenix_check', 'power_key_check', 'reset_key_check', 'rtc_cell_check', 'audio_check', 'usb_check'] },
  { label: '网络检查', names: ['eth_check', '4g_check', '5g_check', 'wifi_check', 'bluetooth_check'] },
  { label: '存储/文件', names: ['drive_check', 'upload_test_files', 'remove_test_files'] },
]

const testCaseGroups = computed(() => {
  const caseMap = new Map(testCaseDefs.value.map((c: any) => [c.name, c]))
  return caseGroupDefs.map(group => ({
    label: group.label,
    cases: group.names.map(name => caseMap.get(name)).filter(Boolean),
  })).filter(g => g.cases.length > 0)
})

onMounted(async () => {
  await loadProfiles()
  await loadTestCaseDefs()
})

async function loadProfiles() {
  try {
    const res: any = await configApi.listProfiles()
    profiles.value = res.profiles || []
  } catch (e) {
    ElMessage.error('加载配置列表失败')
  }
}

async function loadTestCaseDefs() {
  try {
    const res: any = await http.get('/test-types/se9_interface_test/cases')
    const cases = res.cases || []
    testCaseDefs.value = cases.map((c: any) => ({
      name: c.name,
      label: caseLabelMap[c.name] || c.label || c.name,
    }))
  } catch (e) {}
}

async function selectProfile(name: string) {
  selectedName.value = name
  try {
    const res: any = await configApi.getProfile(name)
    selectedProfile.value = res
    // 加载测试选项
    applyTestOpts(res.test_options || {})
  } catch (e) {
    ElMessage.error('加载配置详情失败')
  }
}

function applyTestOpts(opts: Record<string, boolean>) {
  // 先清空所有
  for (const key of Object.keys(testOpts)) {
    delete testOpts[key]
  }
  // 应用 profile 中保存的选项（没有保存的默认 false）
  for (const c of testCaseDefs.value) {
    testOpts[c.name] = opts[c.name] ?? false
  }
}

function toggleAllTestOpts(enabled: boolean) {
  for (const c of testCaseDefs.value) {
    testOpts[c.name] = enabled
  }
}

async function saveTestOptions() {
  if (!selectedProfile.value) return
  savingOpts.value = true
  try {
    const opts: Record<string, boolean> = {}
    for (const c of testCaseDefs.value) {
      opts[c.name] = !!testOpts[c.name]
    }
    await configApi.updateProfileTestOptions(selectedProfile.value.name, opts)
    ElMessage.success('测试选项已保存')
    // 刷新 profile 数据
    selectedProfile.value.test_options = { ...opts }
  } catch (e: any) {
    ElMessage.error(e?.detail || '保存失败')
  } finally {
    savingOpts.value = false
  }
}

function handleCreateFile(file: any) {
  createFile = file.raw
}

async function handleCreate() {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入配置名称')
    return
  }
  if (!createFile) {
    ElMessage.warning('请上传 OEM 配置文件')
    return
  }
  creating.value = true
  try {
    await configApi.createProfile(createForm.value.name.trim(), createFile)
    ElMessage.success('创建成功')
    showCreateDialog.value = false
    createForm.value.name = ''
    createFile = null
    await loadProfiles()
    if (profiles.value.length > 0) {
      selectProfile(profiles.value[profiles.value.length - 1].name)
    }
  } catch (e: any) {
    ElMessage.error(e?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

async function handleOEMReplace(file: any) {
  const raw = file.raw
  if (!raw || !selectedProfile.value) return
  try {
    await configApi.updateProfileOEM(selectedProfile.value.name, raw)
    ElMessage.success('OEM 配置已更新')
    selectProfile(selectedProfile.value.name)
  } catch (e: any) {
    ElMessage.error(e?.detail || '更新失败')
  }
}

async function handleDelete() {
  if (!selectedProfile.value) return
  try {
    await ElMessageBox.confirm(
      `确定要删除配置「${selectedProfile.value.name}」吗？此操作不可恢复。`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await configApi.deleteProfile(selectedProfile.value.name)
    ElMessage.success('已删除')
    selectedProfile.value = null
    selectedName.value = ''
    await loadProfiles()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.detail || '删除失败')
    }
  }
}

function formatDate(iso: string): string {
  if (!iso) return ''
  return iso.slice(0, 16).replace('T', ' ')
}
</script>

<style scoped>
.config-view {
  max-width: 1100px;
  margin: 0 auto;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.page-title {
  font-size: 22px;
  margin: 0;
  color: var(--text-primary);
}
.profile-layout {
  display: flex;
  gap: 20px;
}
.profile-list-card {
  width: 300px;
  flex-shrink: 0;
  background-color: var(--bg-card);
  border-color: var(--border-color);
}
.profile-detail-card {
  flex: 1;
  min-width: 0;
  background-color: var(--bg-card);
  border-color: var(--border-color);
}
.profile-item {
  padding: 12px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
  border: 1px solid transparent;
}
.profile-item:hover {
  background-color: var(--bg-secondary);
}
.profile-item.active {
  background-color: rgba(64, 158, 255, 0.12);
  border-color: var(--accent);
}
.profile-name {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 6px;
  color: var(--text-primary);
}
.profile-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}
.profile-date {
  font-size: 12px;
  color: var(--text-secondary);
}
.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  color: var(--text-primary);
}
.oem-section {
  margin-bottom: 4px;
}
.section-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.section-label {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}
.oem-content {
  background: #1a2744;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 16px;
  max-height: 360px;
  overflow: auto;
}
.oem-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 13px;
  line-height: 1.6;
  font-family: 'Menlo', 'Consolas', monospace;
  color: #e0e0e0;
}
.oem-content pre code {
  color: #e0e0e0;
  font-family: inherit;
  font-size: inherit;
}
.test-options-section {
  margin-top: 4px;
}
.test-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.case-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-top: 4px;
}
.case-groups {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 10px 16px;
  margin-top: 4px;
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
.loading-hint {
  font-size: 13px;
  color: var(--text-secondary);
}
.form-tip {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}
.upload-text {
  color: var(--text-secondary);
  font-size: 14px;
  margin-top: 8px;
}
</style>