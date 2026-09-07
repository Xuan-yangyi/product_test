import http from './http'

export const deviceApi = {
  scanSerials: () => http.get('/devices/serials'),
  scanNetwork: () => http.get('/devices/network'),
  getDeviceInfo: (ip: string) => http.get(`/devices/network/${ip}/info`),
  getResourceStatus: () => http.get('/resource-pool/status'),
}
