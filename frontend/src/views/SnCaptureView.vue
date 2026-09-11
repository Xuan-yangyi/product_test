<template>
  <div class="sn-capture">
    <div class="toolbar">
      <el-input v-model="sn" placeholder="输入 SN 搜索（留空看全部）" clearable
                style="width: 320px" @keyup.enter="load" />
      <el-button type="primary" @click="load">查询</el-button>
    </div>

    <el-empty v-if="!loading && items.length === 0" description="暂无抓拍记录" />

    <div class="grid">
      <el-card v-for="it in items" :key="it.id" class="cap-card" shadow="hover">
        <el-image :src="it.image_url" fit="contain" class="cap-img"
                  :preview-src-list="[it.image_url]" preview-teleported />
        <div class="meta">
          <div class="sn">{{ it.sn }}</div>
          <div class="sub">score {{ it.score?.toFixed(3) }} · {{ it.captured_at || '-' }}</div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { captureApi, type CaptureItem } from '@/api/captures'

const sn = ref('')
const items = ref<CaptureItem[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await captureApi.list({ sn: sn.value || undefined, limit: 100, offset: 0 })
    items.value = res.items
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.cap-img { width: 100%; height: 180px; background: var(--bg-secondary); }
.meta { margin-top: 8px; }
.sn { font-weight: bold; }
.sub { color: var(--text-secondary); font-size: 12px; }
</style>
