<template>
  <AppLayout>
    <router-view v-slot="{ Component }">
      <keep-alive :include="['ClusterAgingView', 'InterfaceTestView']">
        <component :is="Component" />
      </keep-alive>
    </router-view>
  </AppLayout>
</template>

<script setup lang="ts">
import AppLayout from '@/components/AppLayout.vue'
</script>
