import http from './http'

export const configApi = {
  uploadOEM: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return http.post('/config/oem/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  validateOEM: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return http.post('/config/oem/validate', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  getScriptCmd: () => http.get('/config/script-cmd'),
  getFwVersion: () => http.get('/config/fw-version'),
  getShowConfig: () => http.get('/config/show'),
  createProductModel: (data: any) => http.post('/product-models', data),
  getProductTemplates: () => http.get('/product-models/templates'),

  // Profile 管理
  listProfiles: () => http.get('/config/profiles'),
  createProfile: (name: string, file: File) => {
    const form = new FormData()
    form.append('name', name)
    form.append('oem_file', file)
    return http.post('/config/profiles', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  getProfile: (name: string) => http.get(`/config/profiles/${encodeURIComponent(name)}`),
  updateProfileOEM: (name: string, file: File) => {
    const form = new FormData()
    form.append('oem_file', file)
    return http.put(`/config/profiles/${encodeURIComponent(name)}/oem`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  deleteProfile: (name: string) => http.delete(`/config/profiles/${encodeURIComponent(name)}`),

  // Profile 测试选项
  updateProfileTestOptions: (name: string, testOptions: Record<string, boolean>) =>
    http.put(`/config/profiles/${encodeURIComponent(name)}/test-options`, { test_options: testOptions }),
}
