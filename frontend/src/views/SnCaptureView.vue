<template>
  <div class="sn-capture">
    <div class="toolbar">
    <el-input v-model="sn" placeholder="输入 SN 搜索（留空看全部）" clearable
           style="width: 320px" @keyup.enter="load" @clear="load" />
  <el-date-picker v-model="dateRange" type="daterange" range-separator="至"
           start-placeholder="抓拍起始日" end-placeholder="抓拍结束日"
           value-format="YYYY-MM-DD" clearable @change="load" />
  <el-button type="primary" @click="load">查询</el-button>
    </div>

    <el-empty v-if="!loading && pairs.length === 0" description="暂无抓拍记录" />

    <div class="grid">
      <!-- v2.1: 一张卡片 = 同一次命中的正/反两图(按 sn+captured_at 配对) -->
      <el-card v-for="p in pairs" :key="p.key" class="cap-card" shadow="hover">
        <div class="sides">
          <div class="side-col">
            <div class="side-label">正面</div>
            <el-image v-if="p.front" :src="p.front.image_url" fit="contain" class="cap-img"
              :preview-src-list="previewList(p)" preview-teleported>
              <template #error><div class="img-error">图片加载失败</div></template>
            </el-image>
            <div v-else class="img-error cap-img">（暂无正面）</div>
          </div>
          <div class="side-col">
            <div class="side-label">背面</div>
            <el-image v-if="p.back" :src="p.back.image_url" fit="contain" class="cap-img"
              :preview-src-list="previewList(p)" preview-teleported>
              <template #error><div class="img-error">图片加载失败</div></template>
            </el-image>
            <div v-else class="img-error cap-img">（暂无背面）</div>
          </div>
        </div>
        <div class="meta">
      <div class="sn">{{ p.sn }}</div>
     <div class="sub">score {{ (p.front ?? p.back)?.score?.toFixed(3) }}</div>
     <div class="sub">{{ fmtTime((p.front ?? p.back)?.captured_at ?? (p.front ?? p.back)?.uploaded_at ?? null) }}</div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue"
import { captureApi, type CaptureItem } from "@/api/captures"

const sn = ref("")
const dateRange = ref<[string, string] | null>(null)
const items = ref<CaptureItem[]>([])
const loading = ref(false)

// v2.1 正/反配对: 同一次命中 SE9 正反共用同一 captured_at, 故按 (sn, captured_at) 归组
interface CapturePair {
  key: string
  sn: string
  captured_at: string | null
  front?: CaptureItem
  back?: CaptureItem
}

const pairs = computed<CapturePair[]>(() => {
  const map = new Map<string, CapturePair>()
  for (const it of items.value) {          // items 已按 id 倒序(新→旧), 首次出现即定序
    const key = `${it.sn}|${it.captured_at ?? ""}`
    let p = map.get(key)
    if (!p) { p = { key, sn: it.sn, captured_at: it.captured_at }; map.set(key, p) }
    if ((it.side ?? "front") === "back") p.back = it   // 无 side 的旧数据当正面
    else p.front = it
  }
  return Array.from(map.values())
})

// 预览大图列表: 正、背都放进去, 点任一张可左右切换
function previewList(p: CapturePair): string[] {
  return [p.front?.image_url, p.back?.image_url].filter((u): u is string => !!u)
}

// 时间美化(抓拍时刻, 缺失时用入库时刻)：ISO "2026-09-11T14:26:01.059158" → "2026-09-11 14:26:01"
function fmtTime(t: string | null): string {
  return t ? t.replace("T", " ").slice(0, 19) : "-"
}

async function load() {
  loading.value = true
  try {
    const res = await captureApi.list({
      sn: sn.value || undefined,
      start: dateRange.value?.[0] || undefined,
      end: dateRange.value?.[1] || undefined,
      limit: 100, offset: 0,
    })
    items.value = res.items
  } finally {
  loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 16px; }
/* 正/反并排 */
.sides { display: flex; gap: 8px; }
.side-col { flex: 1; min-width: 0; }
.side-label { color: var(--text-secondary); font-size: 12px; margin-bottom: 4px; text-align: center; }
.cap-img { width: 100%; height: 180px; background: var(--bg-secondary); }
.img-error { display: flex; align-items: center; justify-content: center; height: 180px; color: var(--text-secondary); font-size: 13px; }
.meta { margin-top: 8px; }
/* SN 号用亮白大字，深色卡片上清晰可读 */
.sn { font-weight: 700; font-size: 16px; color: #ffffff; }
.sub { color: var(--text-secondary); font-size: 12px; }
</style>
