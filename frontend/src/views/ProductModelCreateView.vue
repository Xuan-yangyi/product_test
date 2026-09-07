<template>
  <div class="create-view">
    <h2 class="page-title">新建产品型号</h2>
    <p class="page-desc">选择已有测试用例模板，快速创建新产品型号</p>

    <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
      <!-- 基本信息 -->
      <el-card shadow="never" class="section-card">
        <template #header>
          <div class="card-header"><span class="step-badge">1</span> 基本信息</div>
        </template>

        <el-form-item label="产品名称" prop="product_name">
          <el-input v-model="form.product_name" placeholder="如 SE10" :maxlength="20" />
          <div class="form-tip">仅支持字母、数字、下划线</div>
        </el-form-item>

        <el-form-item label="显示标签" prop="display_label">
          <el-input v-model="form.display_label" placeholder="如 SE10接口测试" :maxlength="50" />
        </el-form-item>
      </el-card>

      <!-- 选择测试类型 -->
      <el-card shadow="never" class="section-card">
        <template #header>
          <div class="card-header"><span class="step-badge">2</span> 选择测试类型</div>
        </template>

        <el-checkbox-group v-model="selectedSuffixes" class="suffix-list">
          <el-checkbox
            v-for="s in templates.test_type_suffixes"
            :key="s.key"
            :label="s.key"
            :value="s.key"
          >
            {{ s.label }}（{{ s.key }}）
          </el-checkbox>
        </el-checkbox-group>

        <div v-if="selectedSuffixes.length === 0" class="empty-hint">
          请至少选择一个测试类型
        </div>
      </el-card>

      <!-- 配置测试用例 -->
      <el-card
        v-for="suffix in selectedSuffixes"
        :key="suffix"
        shadow="never"
        class="section-card"
      >
        <template #header>
          <div class="card-header">
            <span class="step-badge">3</span>
            配置测试用例 —
            <el-tag size="small">{{ form.product_name || '?' }}_{{ suffix }}</el-tag>
          </div>
        </template>

        <div class="case-table">
          <div class="case-header">
            <el-checkbox
              :model-value="allChecked(suffix)"
              :indeterminate="someChecked(suffix)"
              @change="toggleAll(suffix, $event)"
            >
              全选
            </el-checkbox>
            <span class="case-count">
              {{ checkedCount(suffix) }} / {{ templates.test_case_names.length }} 个启用
            </span>
          </div>

          <div
            v-for="caseName in templates.test_case_names"
            :key="caseName"
            class="case-row"
            :class="{ 'case-enabled': isCaseEnabled(suffix, caseName) }"
          >
            <div class="case-main">
              <el-checkbox
                :model-value="isCaseEnabled(suffix, caseName)"
                @change="toggleCase(suffix, caseName, $event)"
              >
                {{ caseName }}
              </el-checkbox>
            </div>

            <!-- 脚本命令（仅启用时显示） -->
            <div v-if="isCaseEnabled(suffix, caseName)" class="case-cmd">
              <el-row :gutter="8">
                <el-col :span="8">
                  <el-input
                    v-model="getCaseCmd(suffix, caseName).exec_cmd"
                    placeholder="执行命令"
                    size="small"
                  />
                </el-col>
                <el-col :span="5">
                  <el-input
                    v-model="getCaseCmd(suffix, caseName).pass_flag"
                    placeholder="通过标志"
                    size="small"
                  />
                </el-col>
                <el-col :span="5">
                  <el-input
                    v-model="getCaseCmd(suffix, caseName).fail_flag"
                    placeholder="失败标志"
                    size="small"
                  />
                </el-col>
                <el-col :span="3">
                  <el-input-number
                    v-model="getCaseCmd(suffix, caseName).case_timeout"
                    :min="1"
                    :max="3600"
                    size="small"
                    controls-position="right"
                  />
                </el-col>
                <el-col :span="3">
                  <span class="timeout-unit">秒</span>
                </el-col>
              </el-row>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 提交 -->
      <div class="submit-section">
        <el-button type="primary" size="large" @click="handleSubmit" :loading="submitting">
          创建产品型号
        </el-button>
        <el-button size="large" @click="$router.push('/')">取消</el-button>
      </div>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { configApi } from '@/api/config'

const router = useRouter()
const formRef = ref()
const submitting = ref(false)

interface ScriptCmd {
  exec_cmd: string
  pass_flag: string
  fail_flag: string
  case_timeout: number
}

interface Templates {
  test_case_names: string[]
  test_type_suffixes: { key: string; label: string }[]
  script_cmd_templates: Record<string, ScriptCmd>
}

const templates = ref<Templates>({
  test_case_names: [],
  test_type_suffixes: [],
  script_cmd_templates: {},
})

const selectedSuffixes = ref<string[]>([])
// suffix -> case_name -> ScriptCmd
const caseCommands = reactive<Record<string, Record<string, ScriptCmd>>>({})

const form = ref({
  product_name: '',
  display_label: '',
})

const rules = {
  product_name: [
    { required: true, message: '请输入产品名称', trigger: 'blur' },
    { pattern: /^[A-Za-z0-9_]+$/, message: '仅支持字母、数字、下划线', trigger: 'blur' },
  ],
  display_label: [
    { required: true, message: '请输入显示标签', trigger: 'blur' },
  ],
}

onMounted(async () => {
  try {
    const res: any = await configApi.getProductTemplates()
    templates.value = res
  } catch (e) {
    ElMessage.error('加载模板数据失败')
  }
})

function isCaseEnabled(suffix: string, caseName: string): boolean {
  return !!caseCommands[suffix]?.[caseName]
}

function toggleCase(suffix: string, caseName: string, val: any) {
  if (!caseCommands[suffix]) caseCommands[suffix] = {}
  if (val) {
    const tpl = templates.value.script_cmd_templates[caseName.toLowerCase()]
    caseCommands[suffix][caseName] = tpl
      ? { ...tpl }
      : { exec_cmd: '', pass_flag: '', fail_flag: '', case_timeout: 120 }
  } else {
    delete caseCommands[suffix][caseName]
  }
}

function getCaseCmd(suffix: string, caseName: string): ScriptCmd {
  if (!caseCommands[suffix]) caseCommands[suffix] = {}
  if (!caseCommands[suffix][caseName]) {
    const tpl = templates.value.script_cmd_templates[caseName.toLowerCase()]
    caseCommands[suffix][caseName] = tpl
      ? { ...tpl }
      : { exec_cmd: '', pass_flag: '', fail_flag: '', case_timeout: 120 }
  }
  return caseCommands[suffix][caseName]
}

function checkedCount(suffix: string): number {
  return Object.keys(caseCommands[suffix] || {}).length
}

function allChecked(suffix: string): boolean {
  return checkedCount(suffix) === templates.value.test_case_names.length
}

function someChecked(suffix: string): boolean {
  const cnt = checkedCount(suffix)
  return cnt > 0 && cnt < templates.value.test_case_names.length
}

function toggleAll(suffix: string, val: any) {
  if (val) {
    if (!caseCommands[suffix]) caseCommands[suffix] = {}
    for (const name of templates.value.test_case_names) {
      const tpl = templates.value.script_cmd_templates[name.toLowerCase()]
      caseCommands[suffix][name] = tpl
        ? { ...tpl }
        : { exec_cmd: '', pass_flag: '', fail_flag: '', case_timeout: 120 }
    }
  } else {
    caseCommands[suffix] = {}
  }
}

async function handleSubmit() {
  // 校验基本信息
  try {
    await formRef.value?.validate()
  } catch {
    ElMessage.warning('请填写产品名称和显示标签')
    return
  }

  // 校验测试类型
  if (selectedSuffixes.value.length === 0) {
    ElMessage.warning('请至少选择一个测试类型')
    return
  }

  // 校验每个测试类型至少有一个启用的用例
  const testTypes: any[] = []
  for (const suffix of selectedSuffixes.value) {
    const enabledCases = Object.entries(caseCommands[suffix] || {})
    if (enabledCases.length === 0) {
      ElMessage.warning(`测试类型 ${suffix} 至少需要一个启用的测试用例`)
      return
    }

    const typeKey = `${form.value.product_name.toLowerCase()}_${suffix}`
    const suffixLabel = templates.value.test_type_suffixes.find(s => s.key === suffix)
    const label = `${form.value.product_name} ${suffixLabel?.label || suffix}`

    const testCases = enabledCases.map(([name, cmd]) => {
      if (!cmd.exec_cmd || !cmd.pass_flag || !cmd.fail_flag) {
        throw new Error(`测试用例 ${name} 的脚本命令不完整`)
      }
      return { name, enabled: true, script_cmd: cmd }
    })

    testTypes.push({
      type_key: typeKey,
      label,
      category: suffix === 'mac_check' ? 'other' : 'test',
      test_cases: testCases,
    })
  }

  submitting.value = true
  try {
    const res: any = await configApi.createProductModel({
      product_name: form.value.product_name,
      display_label: form.value.display_label,
      test_types: testTypes,
    })
    ElMessage.success(res.message || '创建成功')
    router.push('/')
  } catch (e: any) {
    // Error already shown by interceptor
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.create-view {
  max-width: 960px;
  margin: 0 auto;
  padding-bottom: 40px;
}
.page-title {
  font-size: 24px;
  margin-bottom: 8px;
  color: var(--text-primary);
}
.page-desc {
  color: var(--text-secondary);
  margin-bottom: 24px;
}
.section-card {
  margin-bottom: 20px;
  background-color: var(--bg-card);
  border-color: var(--border-color);
}
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.step-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background-color: var(--accent);
  color: #fff;
  font-size: 13px;
  font-weight: bold;
}
.suffix-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.case-table {
  max-height: 500px;
  overflow-y: auto;
}
.case-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 8px;
  position: sticky;
  top: 0;
  background-color: var(--bg-card);
  z-index: 1;
}
.case-count {
  font-size: 13px;
  color: var(--text-secondary);
}
.case-row {
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color);
}
.case-row:last-child {
  border-bottom: none;
}
.case-enabled {
  background-color: rgba(64, 158, 255, 0.05);
  border-radius: 4px;
  padding: 8px;
}
.case-main {
  margin-bottom: 4px;
}
.case-cmd {
  padding-left: 24px;
}
.timeout-unit {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 32px;
}
.empty-hint {
  text-align: center;
  color: var(--text-secondary);
  padding: 20px;
}
.form-tip {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}
.submit-section {
  text-align: center;
  padding: 20px 0;
}
</style>