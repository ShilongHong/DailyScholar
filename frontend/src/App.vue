<template>
  <div class="bg-gray-50 text-gray-800 h-screen w-full flex overflow-hidden">
    <template v-if="!hideSidebar">
      <AppSidebar :queue-size="queueSize" />
      <main class="flex-1 flex flex-col h-full overflow-hidden relative">
        <AppHeader
          :loading="loading"
          :action-loading="actionLoading"
          @refresh="refreshAll"
          @action="triggerAction"
        />
        <div class="flex-1 overflow-y-auto p-6 bg-gray-50">
          <router-view ref="currentViewRef" @open-wizard="openWizard" />
        </div>
      </main>
    </template>
    <template v-else>
      <main class="flex-1 flex flex-col h-full overflow-hidden">
        <router-view ref="currentViewRef" />
      </main>
    </template>
    <ToastMessages :messages="messages" />
    <ConfigWizard v-if="wizardOpen" @close="wizardOpen = false" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'
import AppHeader from '@/components/AppHeader.vue'
import ToastMessages from '@/components/ToastMessages.vue'
import ConfigWizard from '@/components/ConfigWizard.vue'
import { useToast } from '@/composables/useToast'
import { fetchQueueStatus, triggerFetch, triggerProcess, triggerPush, fetchSetupStatus } from '@/api'

const route = useRoute()
const { messages, showToast } = useToast()

// 阅读器模式：隐藏侧边栏和头部
const hideSidebar = computed(() => !!route.meta.hideSidebar)

// 全局共享状态
const loading = ref(false)
const actionLoading = ref(false)
const queueSize = ref(0)
const currentViewRef = ref(null)
const wizardOpen = ref(false)

// 定时器引用
let queueIntervalId = null

// 获取队列状态
const fetchQueue = async () => {
  try {
    const res = await fetchQueueStatus()
    if (res.data?.success) {
      const data = res.data.data || {}
      queueSize.value = data.size || 0
    }
  } catch (e) {
    // 静默失败，队列状态轮询不报错
  }
}

// 刷新所有数据
const refreshAll = async () => {
  loading.value = true
  try {
    // 始终刷新队列
    await fetchQueue()

    // 刷新当前活跃视图（如果暴露了 refresh 方法）
    if (currentViewRef.value?.refresh) {
      await currentViewRef.value.refresh()
    }
  } catch (e) {
    console.error('刷新数据失败:', e)
  } finally {
    loading.value = false
  }
}

// 触发全局操作（获取/解析/推送）
const triggerAction = async (action) => {
  if (actionLoading.value) return
  actionLoading.value = true

  const actionMap = {
    fetch: { fn: triggerFetch, text: '获取任务' },
    process: { fn: triggerProcess, text: '解析任务' },
    push: { fn: triggerPush, text: '推送任务' }
  }

  const config = actionMap[action]
  if (!config) {
    showToast('未知操作', 'error')
    actionLoading.value = false
    return
  }

  try {
    const res = await config.fn()
    if (res.data?.success) {
      showToast(`${config.text}已触发`)
      setTimeout(refreshAll, 2000)
    } else {
      showToast(res.data?.message || '操作失败', 'error')
    }
  } catch (e) {
    showToast('网络请求失败', 'error')
  } finally {
    actionLoading.value = false
  }
}

// 打开配置向导
const openWizard = () => {
  wizardOpen.value = true
}

// 检查是否需要显示配置向导
const checkSetupStatus = async () => {
  try {
    const res = await fetchSetupStatus()
    if (res.data?.data?.needs_setup) {
      wizardOpen.value = true
    }
  } catch (e) {
    // 静默处理
  }
}

// 生命周期
onMounted(() => {
  refreshAll()
  // 每30秒自动刷新队列状态
  queueIntervalId = setInterval(fetchQueue, 30000)
  // 检查配置向导
  checkSetupStatus()
})

onUnmounted(() => {
  if (queueIntervalId) {
    clearInterval(queueIntervalId)
    queueIntervalId = null
  }
})
</script>
