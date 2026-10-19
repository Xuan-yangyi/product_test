import http from './http'

/** 调机预览：双路摄像头实时画面（经 .57 中继到板子 :8090） */
export type CamSide = 'front' | 'back'
export type CamRes = '4k' | '1080p' | '720p' | '360p'

/** 单路预览状态。
 *  V3.0 由板子的 sn_preview_embed.PreviewEncoder.status() 提供 ——
 *  注意这里**没有 rtsp 字段**（V1 独立预览服务才有），地址是前端写死的。 */
export interface CamStatus {
  name: CamSide
  resolution: CamRes
  size: [number, number]       // [w,h]，[0,0] 表示原始尺寸(4K)
  source_ok: boolean           // 这一路解码是否出过帧（false=相机没起来/断流）
  frames: number               // 累计编码成功的帧数
  seq: number                  // 最新帧序号
  age: number | null           // 最新帧编码距今秒数
  fps_cap: number              // 编码节流上限（不是保证帧率）
  avg_ms: number | null        // 平均单帧编码耗时，实测用
  skipped: number              // 因节流/无帧跳过的轮次
  err: string
}

/** MJPEG 流地址。直接给 <img src> 用。
 *  t 参数是防缓存的一次性令牌：改分辨率/重连时必须变，否则浏览器会复用旧连接。 */
export function streamUrl(cam: CamSide, res: CamRes, t: number): string {
  return `/api/v1/camera/stream?cam=${cam}&res=${res}&_t=${t}`
}

/** 单张抓拍地址（MJPEG 兜底用），同样带防缓存令牌 */
export function snapshotUrl(cam: CamSide, res: CamRes, t: number): string {
  return `/api/v1/camera/snapshot?cam=${cam}&res=${res}&_t=${t}`
}

/** 板子最近一次抓拍的信息（调机页底部回显用） */
export interface LatestCapture {
  ok: boolean
  has: boolean
  reason?: string
  sn?: string
  ts?: string            // 形如 20260916_120100（板子本地时间）
  score?: number | null
  side?: string
  mtime?: number
  image?: string
}

/** 回显图地址。
 *  ★ 带 _t 令牌不是为了防缓存，而是为了让浏览器在抓到新 SN 后重新取图 ——
 *    URL 不变的话 <img> 会一直显示旧图。 */
export function latestCaptureImageUrl(t: number): string {
  return `/api/v1/camera/latest-capture/image?_t=${t}`
}

export const cameraApi = {
  status: () => http.get('/camera/status', { silent: true } as never) as unknown as Promise<{
    ok: boolean
    port: number
    fps_cap: number
    cameras: CamStatus[]
  }>,

  setResolution: (res: CamRes) =>
    http.get('/camera/resolution', { params: { res } }) as unknown as Promise<{
      ok: boolean
      res: CamRes
      cameras: CamSide[]
    }>,

  /** 板子上的最新抓拍（只读，不入库）。板子没抓拍图时返回 has=false，不是错误。 */
  latestCapture: () =>
    http.get('/camera/latest-capture', { silent: true } as never) as unknown as Promise<LatestCapture>,
}

/** 分辨率档位的中文说明。
 *  hint 只讲"看什么"和相对开销，**不写具体帧率** —— 帧率取决于板子实时负载，
 *  页面顶部已按板子回报的编码上限单独显示，写死数字迟早对不上。 */
export const RES_OPTIONS: { value: CamRes; label: string; hint: string }[] = [
  { value: '4k', label: '4K 全幅', hint: '3840×2160，看清整图和铭牌细节；编码开销最大、延迟最高' },
  { value: '1080p', label: '1080p（调机默认）', hint: '1920×1080，细节与流畅度的平衡点' },
  { value: '720p', label: '720p', hint: '1280×720，动作跟手，调位置时更顺' },
  { value: '360p', label: '360p', hint: '640×360，只看大体位置，开销最小' },
]
