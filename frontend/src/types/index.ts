/** 测试类型 */
export type TestType = 'se9_interface' | 'se9_aging' | 'evb_interface' | 'evb_aging' | 'mac_check'

/** 测试状态 */
export type TestStatus = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'stopped'

/** 单步测试结果 */
export type StepResult = 'pass' | 'fail' | 'skip' | 'running' | 'pending'

/** 测试用例配置 */
export interface TestCaseConfig {
  name: string
  label: string
  enabled: boolean
  timeout: number
  pass_flag?: string
  fail_flag?: string
}

/** 测试任务 */
export interface TestTask {
  id: string
  type: TestType
  status: TestStatus
  product_model: string
  serial_port: string
  created_at: string
  current_step: number
  total_steps: number
}

/** 测试步骤 */
export interface TestStep {
  index: number
  name: string
  label: string
  status: StepResult
  duration_ms: number
  message: string
}

/** 交互请求 */
export interface InteractionRequest {
  step_name: string
  message: string
  dialog_type: 'info' | 'confirm' | 'input'
  timeout: number
  options?: string[]
}

/** 交互响应 */
export interface InteractionResponse {
  action: 'confirm' | 'cancel' | 'skip' | 'input'
  value?: string
}

/** 设备信息 */
export interface DeviceInfo {
  serial_port: string
  device_type: string
  vendor_id: string
  product_id: string
  in_use: boolean
}

/** 网络设备 */
export interface NetworkDevice {
  ip: string
  hostname: string
  status: 'online' | 'offline'
  device_type: string
}
