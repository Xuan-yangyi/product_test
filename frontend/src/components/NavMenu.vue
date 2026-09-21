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
    <div class="logo">Athena2 产测</div>
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
    <el-menu-item index="/config">
      <el-icon><Setting /></el-icon>
      <span>配置管理</span>
    </el-menu-item>
  </el-menu>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Document, Setting, Connection, Cpu } from '@element-plus/icons-vue'

const route = useRoute()
const activeRoute = computed(() => {
  const path = route.path
  if (path.startsWith('/test-config') || path.startsWith('/test-run')) return '/cluster-aging'
  return path
})
</script>

<style scoped>
.nav-menu {
  width: 200px;
  min-height: 100vh;
  border-right: 1px solid var(--border-color);
}
.logo {
  height: 56px;
  line-height: 56px;
  text-align: center;
  font-size: 18px;
  font-weight: bold;
  color: var(--accent);
  border-bottom: 1px solid var(--border-color);
}
</style>
