<template>
  <el-menu
    :default-active="activeRoute"
    class="nav-menu"
    background-color="var(--bg-secondary)"
    text-color="var(--text-secondary)"
    active-text-color="var(--accent)"
    :router="true"
    :collapse="false"
  >
    <div class="logo">
      <el-dropdown trigger="click" @command="handleProductLineSwitch">
        <span class="logo-dropdown-trigger">
          {{ currentLineLabel }} <el-icon><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item
              v-for="line in productLines"
              :key="line.key"
              :command="line.key"
              :class="{ 'is-active': line.key === currentLine }"
            >
              {{ line.label }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
    <el-menu-item index="/cluster-aging">
      <el-icon><Connection /></el-icon>
      <span>老化测试</span>
    </el-menu-item>
    <el-menu-item index="/interface-test">
      <el-icon><Cpu /></el-icon>
      <span>接口测试</span>
    </el-menu-item>
    <el-menu-item index="/results">
      <el-icon><Document /></el-icon>
      <span>测试结果</span>
    </el-menu-item>
    <el-menu-item index="/sn-captures">
      <el-icon><Picture /></el-icon>
      <span>SN 抓拍</span>
    </el-menu-item>
    <el-menu-item index="/camera-preview">
      <el-icon><VideoCamera /></el-icon>
      <span>调机预览</span>
    </el-menu-item>
    <el-menu-item index="/config">
      <el-icon><Setting /></el-icon>
      <span>配置管理</span>
    </el-menu-item>
  </el-menu>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Document, Setting, Connection, Cpu, Picture, VideoCamera, ArrowDown } from '@element-plus/icons-vue'
import { useProductLine } from '@/stores/productLine'

const route = useRoute()
const activeRoute = computed(() => {
  const path = route.path
  if (path.startsWith('/test-config') || path.startsWith('/test-run')) return '/cluster-aging'
  return path
})

const { current, config, switchTo } = useProductLine()

const currentLine = computed(() => current.value)
const currentLineLabel = computed(() => config.value.label)

const productLines = [
  { key: 'Athena2' as const, label: 'Athena2 产测' },
  { key: 'X2' as const, label: 'SE13 产测' },
]

function handleProductLineSwitch(line: string) {
  switchTo(line as 'Athena2' | 'X2')
}
</script>

<style scoped>
.nav-menu {
  width: 200px;
  min-height: 100vh;
  border-right: 1px solid var(--border-color);
}
.logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid var(--border-color);
}
.logo-dropdown-trigger {
  font-size: 18px;
  font-weight: bold;
  color: var(--accent);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  user-select: none;
}
.logo-dropdown-trigger:hover {
  opacity: 0.8;
}
.is-active {
  color: var(--accent);
  font-weight: bold;
}
</style>