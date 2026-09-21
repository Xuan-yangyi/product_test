import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      redirect: '/cluster-aging',
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
      meta: { title: '老化测试' },
    },
    {
      path: '/interface-test',
      name: 'interface-test',
      component: () => import('@/views/InterfaceTestView.vue'),
      meta: { title: '接口测试' },
    },
    {
      path: '/product-model/new',
      name: 'product-model-new',
      component: () => import('@/views/ProductModelCreateView.vue'),
      meta: { title: '新建产品型号' },
    },
    {
      path: '/result-detail/:id',
      name: 'result-detail',
      component: () => import('@/views/ResultDetailView.vue'),
      meta: { title: '测试详情' },
    },
  ],
})

export default router
