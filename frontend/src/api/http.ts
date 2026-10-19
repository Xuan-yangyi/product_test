import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    // silent: 后台轮询类请求（如 camera 状态探活）失败不弹全局 toast，
    // 否则板子离线时每次轮询都弹一次 = 界面刷屏。由调用方显式标记。
    if (!error.config?.silent) {
      const msg = error.response?.data?.detail || error.message || '请求失败'
      ElMessage.error(msg)
    }
    return Promise.reject(error)
  },
)

export default http
