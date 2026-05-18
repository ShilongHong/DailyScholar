<template>
  <div class="space-y-6 h-full">
    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <div v-for="card in statCards" :key="card.label" class="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
        <div class="flex justify-between items-start">
          <div>
            <p class="text-sm text-gray-500 mb-1">{{ card.label }}</p>
            <h3 class="text-3xl font-bold text-gray-900">{{ card.value }}</h3>
          </div>
          <div :class="['p-2 rounded-lg', card.bgClass]">
            <i :class="[card.icon, 'text-xl', card.textClass]"></i>
          </div>
        </div>
      </div>
    </div>

    <!-- 图表区域 -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="lg:col-span-2 bg-white p-6 rounded-xl shadow-sm border border-gray-100">
        <h3 class="font-semibold text-gray-800 mb-4">分数分布</h3>
        <div class="h-64 flex items-center justify-center">
          <canvas ref="chartRef"></canvas>
        </div>
      </div>
      <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
        <h3 class="font-semibold text-gray-800 mb-4">系统状态</h3>
        <div class="space-y-4">
          <div v-for="row in systemRows" :key="row.label" class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span class="text-sm text-gray-600">{{ row.label }}</span>
            <span :class="['px-2 py-1 text-xs font-medium rounded', row.className]">{{ row.value }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import Chart from 'chart.js/auto'
import { fetchAllConfig, fetchHealth, fetchPaperStats, fetchSchedulerStatus } from '@/api'

const stats = ref({})
const health = ref(null)
const schedulerStatus = ref(null)
const appConfig = ref(null)
const emit = defineEmits(['update:stats'])

const statCards = computed(() => [
  { label: '今日获取', value: stats.value.today_raw || 0, icon: 'ph ph-download-simple', bgClass: 'bg-blue-50', textClass: 'text-blue-600' },
  { label: '今日筛选相关', value: stats.value.today_relevant || 0, icon: 'ph ph-check-circle', bgClass: 'bg-green-50', textClass: 'text-green-600' },
  { label: '待推送队列', value: stats.value.queue_size || 0, icon: 'ph ph-queue', bgClass: 'bg-purple-50', textClass: 'text-purple-600' },
  { label: '总收录论文', value: stats.value.total_relevant || 0, icon: 'ph ph-database', bgClass: 'bg-orange-50', textClass: 'text-orange-600' }
])

const statusClass = (status) => {
  if (status === 'ok') return 'bg-green-100 text-green-700'
  if (status === 'warn') return 'bg-yellow-100 text-yellow-700'
  if (status === 'loading') return 'bg-gray-100 text-gray-600'
  return 'bg-red-100 text-red-700'
}

const systemRows = computed(() => {
  const dbKnown = health.value !== null
  const dbOk = health.value?.db === true
  const schedulerKnown = schedulerStatus.value !== null
  const schedulerOk = schedulerStatus.value?.running === true
  const llm = appConfig.value?.llm_filter || {}
  const llmKey = typeof llm.api_key === 'string' ? llm.api_key.trim() : ''
  const llmModel = typeof llm.model === 'string' ? llm.model.trim() : ''
  const llmOk = llm.enable !== false && !!llmModel && !!llmKey

  return [
    {
      label: '调度器',
      value: schedulerKnown ? (schedulerOk ? '运行中' : '未运行') : '检测中',
      className: statusClass(schedulerKnown ? (schedulerOk ? 'ok' : 'warn') : 'loading')
    },
    {
      label: '数据库',
      value: dbKnown ? (dbOk ? '已连接' : '未连接') : '检测中',
      className: statusClass(dbKnown ? (dbOk ? 'ok' : 'error') : 'loading')
    },
    {
      label: 'LLM服务',
      value: llmOk ? '已配置' : '未配置',
      className: statusClass(llmOk ? 'ok' : 'warn')
    }
  ]
})

let chartInstance = null
const chartRef = ref(null)

const updateChart = () => {
  const ctx = chartRef.value
  if (!ctx || !stats.value.by_score_range) return

  if (chartInstance) chartInstance.destroy()

  const labels = ['90-100分', '80-89分', '70-79分', '60-69分', '0-59分']
  const data = [
    stats.value.by_score_range['90-100'] || 0,
    stats.value.by_score_range['80-89'] || 0,
    stats.value.by_score_range['70-79'] || 0,
    stats.value.by_score_range['60-69'] || 0,
    stats.value.by_score_range['0-59'] || 0
  ]

  chartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: '论文数量',
        data,
        backgroundColor: [
          '#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444'
        ],
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (context) => '论文数量: ' + context.parsed.y + ' 篇'
          }
        }
      },
      scales: {
        y: { beginAtZero: true, grid: { display: false }, ticks: { stepSize: 1 } },
        x: { grid: { display: false } }
      }
    }
  })
}

const loadStats = async () => {
  try {
    const [statsRes, healthRes, schedulerRes, configRes] = await Promise.allSettled([
      fetchPaperStats(),
      fetchHealth(),
      fetchSchedulerStatus(),
      fetchAllConfig()
    ])

    if (statsRes.status === 'fulfilled' && statsRes.value.data?.success) {
      stats.value = statsRes.value.data.data || {}
      emit('update:stats', stats.value)
      await nextTick()
      updateChart()
    }

    if (healthRes.status === 'fulfilled') {
      health.value = healthRes.value.data || null
    } else {
      health.value = { db: false }
    }

    if (schedulerRes.status === 'fulfilled' && schedulerRes.value.data?.success) {
      schedulerStatus.value = schedulerRes.value.data.data || null
    } else {
      schedulerStatus.value = { running: false }
    }

    if (configRes.status === 'fulfilled' && configRes.value.data?.success) {
      appConfig.value = configRes.value.data.data || null
    } else {
      appConfig.value = null
    }
  } catch (e) {
    console.error('获取统计失败:', e)
  }
}

// 暴露给父组件调用
defineExpose({ refresh: loadStats })

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.destroy()
    chartInstance = null
  }
})

onMounted(() => {
  loadStats()
})
</script>
