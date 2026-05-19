<template>
  <div class="h-full flex flex-col">
    <div class="bg-white rounded-xl shadow-sm border border-gray-100 flex flex-col h-full overflow-hidden">
      <div class="p-4 border-b border-gray-100 flex justify-between items-center bg-gray-50">
        <div class="flex items-center gap-4">
          <h3 class="font-semibold text-gray-800">系统日志</h3>
          <el-select
            v-model="selectedLogFile"
            size="small"
            class="w-48"
            @change="onFileChange"
          >
            <el-option
              v-for="file in logFiles"
              :key="file"
              :label="file"
              :value="file"
            />
          </el-select>
        </div>
        <div class="flex gap-2">
          <el-button
            text
            class="p-2 text-gray-500 hover:text-primary hover:bg-white"
            title="刷新日志"
            @click="loadLogContent(true)"
          >
            <i class="ph ph-arrows-clockwise text-lg"></i>
          </el-button>
        </div>
      </div>
      <div ref="logContainer" class="flex-1 bg-gray-900 p-4 overflow-auto font-mono text-sm text-gray-300">
        <pre class="whitespace-pre-wrap">{{ logContent }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { fetchLogFiles, fetchLogContent } from '@/api'

const logContent = ref('')
const logFiles = ref([])
const selectedLogFile = ref('')
const logContainer = ref(null)

let logInterval = null

const loadLogFiles = async () => {
  try {
    const res = await fetchLogFiles()
    if (res.data?.success) {
      logFiles.value = res.data.data
      if (!selectedLogFile.value && logFiles.value.length > 0) {
        selectedLogFile.value = logFiles.value[0]
      }
    }
  } catch (e) {
    console.error('获取日志文件列表失败:', e)
  }
}

const loadLogContent = async (forceScroll = false) => {
  try {
    // 检查是否需要滚动：强制滚动 或 当前在底部附近
    let shouldScroll = false
    if (logContainer.value) {
      const { scrollTop, scrollHeight, clientHeight } = logContainer.value
      if (forceScroll || (scrollHeight - scrollTop - clientHeight < 50)) {
        shouldScroll = true
      }
    }

    const params = { lines: 200 }
    if (selectedLogFile.value) {
      params.filename = selectedLogFile.value
    }

    const res = await fetchLogContent(params)
    if (res.data?.success) {
      logContent.value = res.data.data
      if (res.data.filename) {
        selectedLogFile.value = res.data.filename
      }

      if (shouldScroll) {
        await nextTick()
        if (logContainer.value) {
          logContainer.value.scrollTop = logContainer.value.scrollHeight
        }
      }
    }
  } catch (e) {
    console.error('获取日志内容失败:', e)
  }
}

const onFileChange = () => {
  loadLogContent(true)
}

const startAutoRefresh = () => {
  stopAutoRefresh()
  logInterval = setInterval(() => loadLogContent(false), 3000)
}

const stopAutoRefresh = () => {
  if (logInterval) {
    clearInterval(logInterval)
    logInterval = null
  }
}

defineExpose({ refresh: () => loadLogFiles().then(() => loadLogContent(true)) })

onMounted(async () => {
  await loadLogFiles()
  await loadLogContent(true)
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>
