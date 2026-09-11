import http from './http'

export interface CaptureItem {
  id: number
  sn: string
  score: number
  captured_at: string | null
  image_path: string
  image_url: string
}

export const captureApi = {
  list: (params: { sn?: string; limit?: number; offset?: number }) =>
    http.get('/captures', { params }) as Promise<{ total: number; items: CaptureItem[] }>,
}
