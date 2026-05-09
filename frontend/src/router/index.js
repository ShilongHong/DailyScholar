import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { title: '仪表盘', globalActions: true } },
  { path: '/papers', name: 'papers', component: () => import('@/views/PapersListView.vue'), meta: { title: '论文列表' } },
  { path: '/queue', name: 'queue', component: () => import('@/views/QueueView.vue'), meta: { title: '推送队列', globalActions: true } },
  { path: '/logs', name: 'logs', component: () => import('@/views/LogsView.vue'), meta: { title: '系统日志' } },
  { path: '/config', name: 'config', component: () => import('@/views/ConfigView.vue'), meta: { title: '系统配置' } },
  { path: '/reader/:doi(.*)', name: 'reader', component: () => import('@/views/PaperReaderView.vue'), meta: { title: '论文阅读', hideSidebar: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
