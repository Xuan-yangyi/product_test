import { defineStore } from 'pinia'
import { ref } from 'vue'
import { deviceApi } from '@/api/device'

export const useDeviceStore = defineStore('device', () => {
  const serialDevices = ref<any[]>([])
  const networkDevices = ref<any[]>([])
  const resourceStatus = ref<any>({})

  async function scanSerials() {
    const res: any = await deviceApi.scanSerials()
    serialDevices.value = res.devices || []
  }

  async function scanNetwork() {
    const res: any = await deviceApi.scanNetwork()
    networkDevices.value = res.devices || []
  }

  async function fetchResourceStatus() {
    const res: any = await deviceApi.getResourceStatus()
    resourceStatus.value = res
  }

  return {
    serialDevices, networkDevices, resourceStatus,
    scanSerials, scanNetwork, fetchResourceStatus,
  }
})
