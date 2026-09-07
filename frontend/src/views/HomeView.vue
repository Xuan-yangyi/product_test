<template>
  <div class="home-view">
    <h2 class="page-title">测试类型选择</h2>
    <p class="page-desc">选择要执行的产测类型</p>

    <el-row :gutter="20">
      <el-col :span="8" v-for="t in testTypes" :key="t.type">
        <el-card class="type-card" shadow="hover" @click="selectType(t)">
          <div class="type-icon">
            <el-icon :size="32"><Cpu /></el-icon>
          </div>
          <div class="type-info">
            <h3>{{ t.label }}</h3>
            <p>{{ t.description }}</p>
          </div>
          <div class="type-meta">
            <el-tag v-if="t.requires_serial" size="small" type="info">串口</el-tag>
            <el-tag v-if="t.requires_network" size="small" type="warning">网络</el-tag>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Cpu } from '@element-plus/icons-vue'
import { useTestStore } from '@/stores/test'

const router = useRouter()
const store = useTestStore()

const testTypes = computed(() => store.testTypes)

onMounted(() => {
  store.fetchTypes()
  store.fetchProductModels()
})

function selectType(type: any) {
  router.push({ name: 'test-config', params: { type: type.type } })
}
</script>

<style scoped>
.home-view {
  max-width: 1200px;
  margin: 0 auto;
}
.page-title {
  font-size: 24px;
  margin-bottom: 8px;
  color: var(--text-primary);
}
.page-desc {
  color: var(--text-secondary);
  margin-bottom: 24px;
}
.type-card {
  cursor: pointer;
  border: 1px solid var(--border-color);
  background-color: var(--bg-card);
  transition: border-color 0.3s;
  margin-bottom: 20px;
}
.type-card:hover {
  border-color: var(--accent);
}
.type-icon {
  color: var(--accent);
  margin-bottom: 12px;
}
.type-info h3 {
  font-size: 16px;
  margin-bottom: 4px;
  color: var(--text-primary);
}
.type-info p {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}
.type-meta {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}
</style>
