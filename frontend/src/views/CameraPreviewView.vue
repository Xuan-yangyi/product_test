<template>
  <div class="camera-preview">
    <!-- ① 顶部：档位 + 状态 + 调节完成 -->
    <div class="toolbar">
      <div class="spacer" />
      <span class="hint">子码流 768×572 · WebRTC 实时</span>

            <el-button type="success" @click="finishDialog = true">调节帮助</el-button>
    </div>

    <!-- ② 双路实时画面 (WebRTC) -->
    <div class="boards">
      <el-card v-for="s in ['front','back']" :key="'wr-'+s" shadow="never" class="board-card">
        <template #header>
          <div class="card-head">
            <span class="title">{{ sideLabel(s) }}
              <el-tag size="small" :type="s==='front'?'success':'info'" effect="plain">{{ s==='front'?'识别中':'仅预览' }}</el-tag>
            </span>
          </div>
        </template>

<style scoped>
.preview-video { filter: brightness(0.9) contrast(1.05); }
</style>
        <div class="frame-wrap">
          <div v-if="webrtcConnecting&&s==='front'" class="frame placeholder" style="position:absolute;z-index:1;background:rgba(0,0,0,0.85);width:100%;height:100%;display:flex;align-items:center;justify-content:center;pointer-events:none">
            <div style="text-align:center"><p class="ph-main" style="color:#fff">WebRTC 连接中...</p><p class="ph-sub" style="color:#aaa">首次可能需要 5~10 秒</p></div></div>
          <video :ref="el=>setVideoRef(s,el)" autoplay playsinline muted class="frame" @click="toggleFullscreen(s)" style="cursor:pointer" title="点击全屏" />
        </div>
      </el-card>
    </div>

    <!-- ③ 底部：最近抓拍回显（只读，不入库） -->
    <el-card shadow="never" class="capture-bar">
      <div class="cap-body">
        <span class="cap-label">最近抓拍</span>

        <!-- 点击放大：el-image 自带 preview，调机时用来核对 SN 小字 -->
        <el-image
          v-if="cap.has"
          :src="latestCaptureImageUrl(capTick)"
          :preview-src-list="[latestCaptureImageUrl(capTick)]"
          :preview-teleported="true"
          fit="contain"
          class="cap-thumb"
        >
          <template #error>
            <div class="cap-thumb-empty">取图失败</div>
          </template>

<style scoped>
.preview-video { filter: brightness(0.9) contrast(1.05); }
</style>
        </el-image>
        <div v-else class="cap-thumb cap-thumb-empty">暂无</div>

        <div class="cap-text">
          <template v-if="cap.has">
            <div class="cap-sn">SN: {{ cap.sn }}</div>
            <div class="cap-sub cap-meta">
              {{ cap.ts }}<span v-if="cap.score != null"> · 分 {{ cap.score.toFixed(3) }}</span>
            </div>
            <div class="cap-sub">
              已存板子，待上传产测系统
              <el-tooltip placement="top">
                <template #content>
                  本卡片只读板子上的文件，<b>不写数据库</b>，所以产测页「SN 抓拍」<br />
                  看到的仍是 uploader 正式上传后的记录（约 5s 延迟）。
                </template>

<style scoped>
.preview-video { filter: brightness(0.9) contrast(1.05); }
</style>
                <el-icon class="cap-help"><QuestionFilled /></el-icon>
              </el-tooltip>
            </div>
          </template>

<style scoped>
.preview-video { filter: brightness(0.9) contrast(1.05); }
</style>
          <template v-else>
            <div class="cap-sub">板子上还没有已配对的抓拍图</div>
            <div class="cap-sub">镜头调好后识别到 SN 会自动出现在这里</div>
          </template>

<style scoped>
.preview-video { filter: brightness(0.9) contrast(1.05); }
</style>
        </div>

        <div class="spacer" />
      <span class="hint">子码流 768×572 · WebRTC 实时</span>
        <span class="cap-sub">点击缩略图放大 · 每 2s 自动刷新</span>
      </div>
    </el-card>

    <!-- ④ 调节帮助（V3.0：不再需要停预览/重启推流） -->
    <el-dialog v-model="finishDialog" title="调节帮助" width="620px">
      <el-alert type="success" :closable="false" show-icon style="margin-bottom: 14px">
        <template #title>识别已在后台同步运行，无需任何切换</template>

<style scoped>
.preview-video { filter: brightness(0.9) contrast(1.05); }
</style>
        V3.0 的预览与识别在<b>同一个进程</b>里，共享同一路相机解码 ——
        相机源仍只有一条连接。调镜头时识别照常在跑，抓到 SN 下方即出现图片。
      </el-alert>

      <div class="step">
        <div class="step-title">① 确认档位</div>
        <el-radio-group v-model="profile">
          <el-radio-button label="big">大板 big（双路，背面同步抓拍）</el-radio-button>
          <el-radio-button label="small">小板 small（单路）</el-radio-button>
        </el-radio-group>
      </div>

      <div class="step">
        <div class="step-title">② 在板子上启动（含预览）</div>
        <div class="cmd" v-for="(line, i) in commands" :key="i">
          <code>{{ line }}</code>
          <el-button size="small" text @click="copy(line)">复制</el-button>
        </div>
      </div>

      <el-alert type="warning" :closable="false" style="margin-top: 10px">
        <template #title>万一预览影响识别：一键回退</template>

<style scoped>
.preview-video { filter: brightness(0.9) contrast(1.05); }
</style>
        在板子上给识别服务加 <code>--no-preview</code> 参数重启，即退回纯识别行为。
      </el-alert>

      <el-alert type="info" :closable="false" style="margin-top: 10px">
        预览服务在 .57 页面上只是显示。实际启停都在<b>板子</b>上敲命令，
        本页面不会去连板子、不保存任何凭据。
      </el-alert>

      <template #footer>
        <el-button @click="finishDialog = false">返回继续调机</el-button>
        <el-button type="primary" @click="goSnCapture">去「SN 抓拍」看结果</el-button>
      </template>

<style scoped>
.preview-video { filter: brightness(0.9) contrast(1.05); }
</style>
    </el-dialog>
  </div>
</template>

<style scoped>
.preview-video { filter: brightness(0.9) contrast(1.05); }
</style>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import {
  cameraApi, streamUrl, latestCaptureImageUrl, RES_OPTIONS,
  type CamStatus, type CamRes, type CamSide, type LatestCapture,
} from '@/api/camera'

const router = useRouter()

// V4.0 WebRTC
const pcMap = new Map()
const videoRefs = new Map()
const webrtcConnecting = ref(true)

function setVideoRef(c, el) { if (el) videoRefs.set(c, el) }
function stopWebRTC(c) { const p=pcMap.get(c); if(p){p.close();pcMap.delete(c)} const v=videoRefs.get(c); if(v)v.srcObject=null }
async function startWebRTC(c, u, delay) {
 if(delay>0) await new Promise(r=>setTimeout(r,delay))
 stopWebRTC(c)
 const pc=new RTCPeerConnection({iceServers:[]}); pcMap.set(c,pc); pc.addTransceiver('video',{direction:'recvonly'})
 pc.oniceconnectionstatechange=()=>{ const s=pc.iceConnectionState; if(s==='failed'||s==='disconnected'){console.warn('WebRTC '+c+' retry');stopWebRTC(c);startWebRTC(c,u,3000)} }
 pc.ontrack=(ev)=>{ const v=videoRefs.get(c); if(v&&ev.streams[0]){v.srcObject=ev.streams[0];if(c==='front')webrtcConnecting.value=false} }
 try{ const o=await pc.createOffer(); await pc.setLocalDescription(o)
  await new Promise(r=>{if(pc.iceGatheringState==='complete')r();else{const ck=()=>{if(pc.iceGatheringState==='complete')r();else setTimeout(ck,200)};ck()}})
  const r=await fetch('/api/v1/camera/webrtc/whep/cam_'+c,{method:'POST',headers:{'Content-Type':'application/sdp'},body:pc.localDescription.sdp})
  if(!r.ok)throw new Error('WHEP '+r.status); await pc.setRemoteDescription({type:'answer',sdp:await r.text()})
  console.log('WebRTC '+c+' connected')
 }catch(e){console.warn('WebRTC '+c+':',e);stopWebRTC(c);startWebRTC(c,u,3000)} }
async function initWebRTC(){ try{ const cfg=await(await fetch('/api/v1/camera/webrtc/config')).json()
 for(const cn of cfg.cams) startWebRTC(cn,cfg.boardUrl, cn==='front'?1000:2000) }catch(e){console.error('WebRTC init:',e)} }


const res = ref<CamRes>('1080p')       // 默认 1080p：4K 单路 84Mbps、编码限速 5.7fps，
                                       // 观感延迟约 1.5-2s；1080p 约 1s，细节仍够核对 SN。
                                       // 要看铭牌小字可临时切 4K（上拉框内可选）。
const cameras = ref<CamStatus[]>([])
const tick = ref(0)                    // 换值即强制 <img> 重连
const fps = ref(0)
const finishDialog = ref(false)
const profile = ref<'big' | 'small'>('big')

// —— 底部回显 ——
const cap = ref<LatestCapture>({ ok: true, has: false })
const capTick = ref(0)                 // 每次发现新抓拍就换值，逼 <img> 重取
let lastCapKey = ''                    // 去重用：SN+时间戳，避免每 2s 白刷一张图

const curResHint = computed(
  () => RES_OPTIONS.find((o) => o.value === res.value)?.hint ?? '',
)

// V3.0：不再有"停预览→重启推流"的步骤，一条命令起识别（预览随之内嵌启动）
const commands = computed(() => {
  const svc = profile.value === 'big' ? 'sn-monitor-big' : 'sn-monitor'
  return [
    `sudo systemctl restart ${svc}`,
    `sudo systemctl status ${svc}`,
    'tail -f /data/soph_SN/logs/sn_monitor.service.log',
  ]
})

type ViewState = 'init' | 'running' | 'stalled' | 'stopped'

/** 由 V3.0 板子的 status 字段推导页面状态。
 *  V3.0 没有 state 字段 —— 板子那边只如实报告"这一路解码出没出帧"，
 *  "画面是不是新鲜"由前端按 age 判断（阈值给宽，调机时人不希望标签乱跳）。 */
function viewState(c: CamStatus | undefined): ViewState {
  if (!c) return 'init'
  if (c.err && !c.source_ok) return 'stopped'
  if (!c.source_ok) return 'init'
  if (c.age !== null && c.age > 5) return 'stalled'
  return 'running'
}

function sideLabel(name: CamSide) {
  return name === 'front' ? '正面' : '背面'
}

function stateLabel(s: ViewState) {
  return {
    init: '相机未就绪',
    running: '已连接',
    stalled: '画面停滞',
    stopped: '已停止',
  }[s] ?? s
}

function tagType(s: ViewState) {
  if (s === 'running') return 'success'
  if (s === 'stalled') return 'warning'
  return 'info'
}

function copy(text: string) {
  navigator.clipboard?.writeText(text).then(
    () => ElMessage.success('已复制'),
    () => ElMessage.warning('复制失败，请手工选中'),
  )
}

function goSnCapture() {
  finishDialog.value = false
  router.push('/sn-captures')
}

/** 分辨率变化：先告诉板子切档，再重连 <img>（不重连的话浏览器还挂着旧流） */
async function onResChange(v: CamRes) {
  try {
    await cameraApi.setResolution(v)
    ElMessage.success('档位已切换，画面重连中')
  } catch (e: unknown) {
    ElMessage.error(extractErr(e, '档位切换失败'))
  }
  tick.value++
}

function reloadStreams() {
  tick.value++
  ElMessage.info('正在重连画面…')
}

/** 流断掉的那几路：<img> 一旦 error 不会自己重试，由下面的 keepalive 定时重连。 */
const failed = ref<Set<CamSide>>(new Set())

function onImgError(name: CamSide) {
  failed.value = new Set(failed.value).add(name)
}

function extractErr(e: unknown, fallback: string): string {
  const d = (e as { detail?: unknown })?.detail
  return typeof d === 'string' ? d : fallback
}

/** 轮询板子状态。V3.0 板子直接给编码帧数与平均耗时，
 *  比 V2 靠 frames 差值估算更准，所以这里只取结果不再自己算帧率。 */
async function poll() {
  try {
    const r = await cameraApi.status()
    cameras.value = r.cameras
    fps.value = Math.round(r.fps_cap ?? 0)

    // 该路已经能出帧了就把重连标记摘掉，让 <img> 自己接管
    if (failed.value.size) {
      const next = new Set(failed.value)
      for (const c of r.cameras) {
        if (c.source_ok && c.age !== null && c.age < 5 && next.has(c.name)) {
          next.delete(c.name)
        }
      }
      failed.value = next
    }
  } catch (e: unknown) {
    // 板子服务没起：静默标记，页面上给出提示即可，不必每 2s 弹一次错误
    cameras.value = cameras.value.map((c) => ({ ...c, source_ok: false, err: '' }))
    fps.value = 0
  }
}

let pollTimer: number | undefined
let capTimer: number | undefined
let keepAliveTimer: number | undefined

/** <img> 一旦 error 就彻底不干活了。定时换 tick 让它重连，直到板子那边恢复。 */
function keepAlive() {
  if (failed.value.size) tick.value++
}

/** 轮询板子上的最新抓拍（只读）。
 *  没抓到图时不报错、不弹消息 —— 调机阶段"还没有抓拍"是常态，不是故障。 */
async function pollCapture() {
  try {
    const r = await cameraApi.latestCapture()
    cap.value = r
    if (r.has) {
      const key = `${r.sn}_${r.ts}`     // 只在真的换了新抓拍时才重取图
      if (key !== lastCapKey) {
        lastCapKey = key
        capTick.value++
      }
    }
  } catch {
    // 板子服务没起/没抓拍图：保持安静，卡片自己显示空态
    cap.value = { ok: false, has: false }
  }
}

onMounted(async () => {
  initWebRTC()
  // 首次立刻建流：tick 变化会让 <img> 开始拉
  tick.value++
  await poll()
  await pollCapture()
  pollTimer = window.setInterval(poll, 2000)
  capTimer = window.setInterval(pollCapture, 2000)
  keepAliveTimer = window.setInterval(keepAlive, 5000)
})

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
  if (capTimer) window.clearInterval(capTimer)
  if (keepAliveTimer) window.clearInterval(keepAliveTimer)
})
</script>

<style scoped>
.camera-preview {
  padding: 16px;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.toolbar .label {
  color: var(--text-secondary);
  font-size: 14px;
}
.toolbar .hint {
  color: var(--text-secondary);
  font-size: 12px;
}
.spacer {
  flex: 1;
}
.boards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
@media (max-width: 1100px) {
  .boards {
    grid-template-columns: 1fr;
  }
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.card-head .title {
  font-size: 14px;
  font-weight: 600;
}
.frame-wrap {
  background: #000;
  border-radius: 4px;
  overflow: hidden;
  aspect-ratio: 16 / 9;
  display: flex;
  align-items: center;
  justify-content: center;
}
.frame {
  width: 100%;
  height: 100%;
  /* contain：调机要看全图，宁可留黑边也不裁切 */
  object-fit: contain;
  display: block;
}
.placeholder {
  color: #999;
  text-align: center;
  padding: 20px;
}
.ph-main {
  font-size: 16px;
  margin: 0 0 6px;
}
.ph-sub {
  font-size: 12px;
  margin: 0;
  word-break: break-all;
  max-width: 420px;
}
.meta {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

/* 底部抓拍回显横条：横着排，高度压到 ~120px，不抢上面双路画面的高度 */
.capture-bar {
  margin-top: 14px;
}
.capture-bar :deep(.el-card__body) {
  padding: 10px 14px;
}
.cap-body {
  display: flex;
  align-items: center;
  gap: 14px;
}
.cap-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  flex-shrink: 0;
}
.cap-thumb {
  width: 142px;
  height: 80px;           /* 16:9，正好一排，不撑高整个横条 */
  border-radius: 4px;
  background: #000;
  flex-shrink: 0;
  cursor: zoom-in;
}
.cap-thumb-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  font-size: 12px;
  background: var(--bg-secondary, #f5f7fa);
  cursor: default;
}
.cap-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 260px;
}
.cap-sn {
  font-size: 15px;
  font-weight: 600;
  /* 暗底卡片上 SN 是这一条的主角，用纯白高亮；继承主题色会偏灰看不清 */
  color: #fff;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: 0.3px;
}
.cap-sub {
  font-size: 12px;
  color: var(--text-secondary);
}
/* SN 下方的时间/分数紧跟主角，比说明文字亮一档，形成层次 */
.cap-sub.cap-meta {
  color: #c8c8c8;
}
.cap-help {
  vertical-align: -2px;
  cursor: help;
  color: var(--text-secondary);
}
.step {
  margin-bottom: 14px;
}
.step-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}
.cmd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  background: var(--bg-secondary, #f5f7fa);
  border-radius: 4px;
  padding: 6px 10px;
  margin-bottom: 6px;
}
.cmd code {
  font-size: 13px;
  user-select: all;
}
</style>
