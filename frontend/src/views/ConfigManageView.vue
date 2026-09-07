<template>
  <div class="config-view">
    <h2 class="page-title">配置管理</h2>

    <el-card shadow="never" class="config-card">
      <template #header>OEM 配置文件</template>
      <el-upload
        drag
        :auto-upload="false"
        :on-change="handleOEMUpload"
        accept=".ini,.cfg,.conf"
        :limit="1"
      >
        <el-icon :size="40"><UploadFilled /></el-icon>
        <div class="upload-text">拖拽或点击上传 OEM 配置文件</div>
        <template #tip>
          <div class="upload-tip">支持 .ini / .cfg / .conf 格式</div>
        </template>
      </el-upload>
      <div v-if="oemResult" class="oem-result">
        <el-alert
          :title="oemResult.message"
          :type="oemResult.valid ? 'success' : 'error'"
          :closable="false"
          show-icon
        />
      </div>
    </el-card>

    <el-card shadow="never" class="config-card">
      <template #header>脚本命令配置</template>
      <el-button type="primary" size="small" @click="loadScriptConfig">
        加载配置
      </el-button>
      <el-table :data="scriptConfigList" size="small" style="margin-top: 12px" v-if="scriptConfigList.length > 0">
        <el-table-column prop="name" label="用例名称" />
        <el-table-column prop="cmd" label="命令" show-overflow-tooltip />
        <el-table-column prop="pass_flag" label="通过标志" width="100" />
        <el-table-column prop="fail_flag" label="失败标志" width="100" />
        <el-table-column prop="timeout" label="超时(s)" width="80" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { configApi } from '@/api/config'

const oemResult = ref<any>(null)
const scriptConfigList = ref<any[]>([])

async function handleOEMUpload(file: any) {
  const raw = file.raw
  if (!raw) return

  try {
    const res: any = await configApi.validateOEM(raw)
    oemResult.value = res
    if (res.valid) {
      ElMessage.success(`校验通过: ${res.product_model}`)
    } else {
      ElMessage.error(res.message)
    }
  } catch (e) {
    ElMessage.error('上传失败')
  }
}

async function loadScriptConfig() {
  try {
    const res: any = await configApi.getScriptCmd()
    const cfg = res.config || {}
    scriptConfigList.value = Object.entries(cfg).map(([name, val]: [string, any]) => ({
      name,
      cmd: val.cmd || '',
      pass_flag: val.pass_flag || 'PASS',
      fail_flag: val.fail_flag || 'FAIL',
      timeout: val.timeout || 30,
    }))
  } catch (e) {
    ElMessage.error('加载配置失败')
  }
}
</script>

<style scoped>
.config-view {
  max-width: 900px;
  margin: 0 auto;
}
.page-title {
  font-size: 24px;
  margin-bottom: 16px;
}
.config-card {
  margin-bottom: 20px;
  background-color: var(--bg-card);
  border-color: var(--border-color);
}
.upload-text {
  color: var(--text-secondary);
  font-size: 14px;
  margin-top: 8px;
}
.upload-tip {
  color: var(--text-secondary);
  font-size: 12px;
}
.oem-result {
  margin-top: 16px;
}
</style>
