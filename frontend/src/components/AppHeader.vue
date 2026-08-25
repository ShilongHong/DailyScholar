<template>
  <header class="min-h-16 bg-white border-b border-gray-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 py-3 sm:px-6 sm:py-0 shadow-sm z-10">
    <h2 class="text-xl font-semibold text-gray-800 truncate">{{ title }}</h2>
    <div class="flex flex-wrap items-center gap-3 sm:gap-4">
      <button
        @click="$emit('refresh')"
        :disabled="loading"
        :aria-busy="loading ? 'true' : 'false'"
        aria-label="刷新数据"
        class="p-2 text-gray-500 hover:text-primary hover:bg-gray-50 rounded-full transition-colors"
        title="刷新数据"
      >
        <i class="ph ph-arrows-clockwise text-xl" :class="{'animate-spin': loading}"></i>
      </button>
      <div v-if="showGlobalActions" class="h-8 w-px bg-gray-200"></div>
      <div v-if="showGlobalActions" class="flex gap-2">
        <button
          @click="$emit('action', 'fetch')"
          :disabled="actionLoading"
          :aria-busy="isActionLoading('fetch') ? 'true' : 'false'"
          class="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 disabled:opacity-50 transition-colors flex items-center gap-2"
        >
          <i :class="isActionLoading('fetch') ? 'ph ph-spinner animate-spin' : 'ph ph-download-simple'"></i>
          立即获取
        </button>
        <button
          @click="$emit('action', 'process')"
          :disabled="actionLoading"
          :aria-busy="isActionLoading('process') ? 'true' : 'false'"
          class="px-4 py-2 bg-white border border-blue-300 text-blue-700 rounded-lg text-sm font-medium hover:bg-blue-50 disabled:opacity-50 transition-colors flex items-center gap-2"
        >
          <i :class="isActionLoading('process') ? 'ph ph-spinner animate-spin' : 'ph ph-cpu'"></i>
          立即解析
        </button>
        <button
          @click="$emit('action', 'push')"
          :disabled="actionLoading"
          :aria-busy="isActionLoading('push') ? 'true' : 'false'"
          class="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center gap-2 shadow-sm shadow-primary/30"
        >
          <i :class="isActionLoading('push') ? 'ph ph-spinner animate-spin' : 'ph ph-paper-plane-right'"></i>
          立即推送
        </button>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const props = defineProps({
  loading: Boolean,
  actionLoading: Boolean,
  actionLoadingType: {
    type: String,
    default: ''
  }
})

defineEmits(['refresh', 'action'])

const route = useRoute()
const title = computed(() => route.meta.title || '仪表盘')
const showGlobalActions = computed(() => route.meta.globalActions === true)
const isActionLoading = (action) => props.actionLoading && props.actionLoadingType === action
</script>
