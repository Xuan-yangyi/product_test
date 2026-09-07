import { defineStore } from 'pinia'
import { ref } from 'vue'
import { configApi } from '@/api/config'

export const useConfigStore = defineStore('config', () => {
  const scriptCmdConfig = ref<Record<string, any>>({})
  const fwVersionConfig = ref<Record<string, any>>({})
  const showConfig = ref<Record<string, any>>({})

  async function fetchScriptCmd() {
    const res: any = await configApi.getScriptCmd()
    scriptCmdConfig.value = res.config || {}
  }

  async function fetchFwVersion() {
    const res: any = await configApi.getFwVersion()
    fwVersionConfig.value = res.config || {}
  }

  async function fetchShowConfig() {
    const res: any = await configApi.getShowConfig()
    showConfig.value = res.config || {}
  }

  return {
    scriptCmdConfig, fwVersionConfig, showConfig,
    fetchScriptCmd, fetchFwVersion, fetchShowConfig,
  }
})
