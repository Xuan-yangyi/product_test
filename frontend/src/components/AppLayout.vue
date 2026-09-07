<template>
  <div class="app-layout">
    <NavMenu />
    <div class="main-area">
      <StatusBar />
      <div class="content">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import NavMenu from './NavMenu.vue'
import StatusBar from './StatusBar.vue'
</script>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background-color: var(--bg-primary);
}
</style>
