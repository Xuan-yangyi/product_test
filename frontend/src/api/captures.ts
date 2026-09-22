import http from './http'

export interface CaptureItem {
  id: number
  sn: string
  score: number
  captured_at: string | null
  uploaded_at: string | null
  image_path: string
  image_url: string
  side?: 'front' | 'back'          // v2.1 正/反面; 旧后端不返回时为 undefined, 视作 front
}

export const captureApi = {
  list: (params: { sn?: string; start?: string; end?: string; limit?: number; offset?: number }) =>
    http.get('/captures', { params }) as Promise<{ total: number; items: CaptureItem[] }>,
}
