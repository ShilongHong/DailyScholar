<template>
  <div class="h-full">
    <div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
      <div class="p-6 border-b border-gray-100 flex justify-between items-center">
        <h3 class="font-semibold text-gray-800">待推送列表</h3>
        <span class="text-sm text-gray-500">{{ queueStatus.size }} 篇等待中</span>
      </div>
      <div class="divide-y divide-gray-100">
        <div
          v-for="(paper, index) in queueStatus.preview"
          :key="index"
          class="p-4 hover:bg-gray-50 flex items-center gap-4"
        >
          <div class="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center text-gray-500 font-medium text-sm">
            {{ index + 1 }}
          </div>
          <div class="flex-1 min-w-0">
            <h4 class="font-medium text-gray-900 truncate">{{ paper.TitleCN || paper.Title }}</h4>
            <div class="flex items-center gap-3 mt-1 text-xs text-gray-500">
              <span
                :class="[
                  'px-1.5 py-0.5 rounded font-bold',
                  paper.Stars >= 80 ? 'bg-green-100 text-green-700' :
                  paper.Stars >= 60 ? 'bg-yellow-100 text-yellow-700' :
                  'bg-gray-100 text-gray-600'
                ]"
              >{{ paper.Stars ?? 0 }}分</span>
              <span class="truncate" :title="paper.RelevanceReason">{{ paper.RelevanceReason || '待评分' }}</span>
            </div>
            <p class="text-xs text-gray-400 mt-1 truncate">{{ paper.Author }}</p>
          </div>
        </div>
      </div>
      <div v-if="queueStatus.size === 0" class="p-8 text-center text-gray-500">
        队列为空
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { fetchQueueStatus } from '@/api'

const queueStatus = ref({ size: 0, preview: [] })

const loadQueue = async () => {
  try {
    const res = await fetchQueueStatus()
    if (res.data?.success) {
      queueStatus.value = res.data.data
    }
  } catch (e) {
    console.error('获取队列状态失败:', e)
  }
}

defineExpose({ refresh: loadQueue })

onMounted(() => {
  loadQueue()
})
</script>
