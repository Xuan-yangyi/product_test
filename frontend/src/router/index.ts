import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
      meta: { title: '产测首页' },
    },
    {
      path: '/test-config/:type',
      name: 'test-config',
      component: () => import('@/views/TestConfigView.vue'),
      meta: { title: '测试配置' },
    },
    {
      path: '/test-run/:id',
      name: 'test-run',
      component: () => import('@/views/TestRunView.vue'),
      meta: { title: '测试执行' },
    },
    {
      path: '/results',
      name: 'results',
      component: () => import('@/views/TestResultsView.vue'),
      meta: { title: '测试结果' },
    },
    {
      path: '/devices',
      name: 'devices',
      component: () => import('@/views/DeviceManageView.vue'),
      meta: { title: '设备管理' },
    },
    {
      path: '/config',
      name: 'config',
      component: () => import('@/views/ConfigManageView.vue'),
      meta: { title: '配置管理' },
    },
    {
      path: '/cluster-aging',
      name: 'cluster-aging',
      component: () => import('@/views/ClusterAgingView.vue'),
      meta: { title: '集群老化' },
    },
    {
      path: '/product-model/new',
      name: 'product-model-new',
      component: () => import('@/views/ProductModelCreateView.vue'),
      meta: { title: '新建产品型号' },
    },
  ],
})

export default router
