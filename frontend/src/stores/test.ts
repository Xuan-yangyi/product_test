import { defineStore } from 'pinia'
import { ref } from 'vue'
import { testApi } from '@/api/test'
import type { TestType } from '@/types'

export const useTestStore = defineStore('test', () => {
  const testTypes = ref<any[]>([])
  const productModels = ref<any[]>([])
  const currentTest = ref<any>(null)
  const tests = ref<any[]>([])

  async function fetchTypes() {
    const res: any = await testApi.getTypes()
    testTypes.value = res.types || []
  }

  async function fetchProductModels() {
    const res: any = await testApi.getProductModels()
    productModels.value = res.models || []
  }

  async function createTest(params: any) {
    const res: any = await testApi.createTest(params)
    return res
  }

  async function startTest(id: string) {
    await testApi.startTest(id)
  }

  async function stopTest(id: string) {
    await testApi.stopTest(id)
  }

  async function fetchTest(id: string) {
    const res: any = await testApi.getTest(id)
    currentTest.value = res
    return res
  }

  return {
    testTypes, productModels, currentTest, tests,
    fetchTypes, fetchProductModels, createTest, startTest, stopTest, fetchTest,
  }
})
