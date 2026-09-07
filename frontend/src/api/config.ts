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
}
