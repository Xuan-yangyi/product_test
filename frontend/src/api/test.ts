import http from './http'
import type { TestType, TestTask, TestCaseConfig } from '@/types'

export interface CreateTestParams {
  test_type: TestType
  product_model: string
  serial_port?: string
  device_ip?: string
  device_count?: number
  params?: Record<string, any>
}

export const testApi = {
  getTypes: () => http.get('/test-types'),
  getCases: (type: string) => http.get(`/test-types/${type}/cases`),
  getProductModels: () => http.get('/product-models'),
  getShowConfig: (type: string) => http.get(`/test-types/${type}/show-config`),
  updateCase: (testType: string, caseName: string, enabled: boolean) =>
    http.put(`/test-types/${testType}/cases/${caseName}`, { enabled }),

  createTest: (params: CreateTestParams) => http.post('/tests', params),
  startTest: (id: string) => http.post(`/tests/${id}/start`),
  stopTest: (id: string) => http.post(`/tests/${id}/stop`),
  pauseTest: (id: string) => http.post(`/tests/${id}/pause`),
  resumeTest: (id: string) => http.post(`/tests/${id}/resume`),

  getTest: (id: string) => http.get(`/tests/${id}`),
  listTests: () => http.get('/tests'),

  sendInteraction: (id: string, data: { action: string; value?: string }) =>
    http.post(`/tests/${id}/interact`, data),

  getResults: (params: Record<string, any>) => http.get('/results', { params }),
  getResultDetail: (id: string) => http.get(`/results/${id}`),
  getStatistics: (params?: Record<string, any>) => http.get('/results/statistics', { params }),
  getLogs: (id: string) => http.get(`/results/${id}/logs`),
  getSyslog: (id: string) => http.get(`/results/${id}/syslog`),
  exportCsv: (params?: Record<string, any>) => http.get('/results/export/csv', {
    params,
    responseType: 'blob',
  }),
}
