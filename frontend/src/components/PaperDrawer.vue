<template>
  <el-drawer
    :model-value="open"
    @update:model-value="$emit('update:open', $event)"
    direction="rtl"
    :size="'480px'"
    :with-header="false"
    :show-close="false"
    class="paper-drawer"
  >
    <div class="relative w-full h-full flex flex-col">
      <!-- 抽屉头部 -->
      <div class="p-6 border-b border-gray-100 flex items-start justify-between bg-gray-50/50">
        <div class="flex-1 pr-8">
          <div class="flex items-center gap-2 mb-3">
            <span class="px-2.5 py-1 bg-primary/10 text-primary text-xs font-medium rounded-full">
              {{ paper.PublicationYear }}
            </span>
            <span :class="['px-2.5 py-1 text-xs font-bold rounded-full', paper.Stars >= 80 ? 'bg-green-100 text-green-700' : paper.Stars >= 60 ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-600']">{{ paper.Stars ?? 0 }}分/100</span>
            <span v-if="paper.Source" class="px-2.5 py-1 bg-purple-50 text-purple-600 text-xs font-medium rounded-full border border-purple-100">
              {{ paper.Source }}
            </span>
          </div>
          <h2 class="text-xl font-bold text-gray-900 leading-snug mb-2">
            {{ paper.TitleCN || paper.Title }}
          </h2>
          <h3 class="text-sm text-gray-500 font-medium leading-relaxed">
            {{ paper.Title }}
          </h3>
        </div>
        <button @click="$emit('update:open', false)" class="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full transition-colors">
          <i class="ph ph-x text-xl"></i>
        </button>
      </div>

      <!-- 抽屉主体 -->
      <div class="flex-1 overflow-y-auto p-6 space-y-8">

        <!-- 推荐理由 -->
        <div class="bg-blue-50/50 p-4 rounded-xl border border-blue-100">
          <h4 class="text-sm font-semibold text-blue-800 mb-2 flex items-center gap-2">
            <i class="ph ph-thumbs-up"></i> 推荐理由
          </h4>
          <p class="text-sm text-blue-900/80 leading-relaxed">
            {{ paper.RelevanceReason }}
          </p>
        </div>

        <!-- 潜在帮助 -->
        <div v-if="paper.PotentialHelp" class="bg-green-50/50 p-4 rounded-xl border border-green-100">
          <h4 class="text-sm font-semibold text-green-800 mb-2 flex items-center gap-2">
            <i class="ph ph-lightbulb"></i> 潜在帮助
          </h4>
          <p class="text-sm text-green-900/80 leading-relaxed">
            {{ paper.PotentialHelp }}
          </p>
        </div>

        <!-- 中文摘要 -->
        <div>
          <h4 class="text-sm font-bold text-gray-900 uppercase tracking-wider mb-3">中文摘要</h4>
          <p class="text-gray-700 leading-relaxed text-justify">
            {{ paper.AbstractCN || '暂无翻译' }}
          </p>
        </div>

        <!-- 英文摘要 -->
        <div>
          <h4 class="text-sm font-bold text-gray-900 uppercase tracking-wider mb-3">英文摘要</h4>
          <p class="text-gray-600 leading-relaxed text-justify text-sm font-light">
            {{ paper.Abstract }}
          </p>
        </div>

        <!-- 元数据 -->
        <div class="grid grid-cols-2 gap-4 pt-4 border-t border-gray-100">
          <div>
            <span class="text-xs text-gray-500 block mb-1">作者</span>
            <span class="text-sm text-gray-800">{{ paper.Author }}</span>
          </div>
          <div>
            <span class="text-xs text-gray-500 block mb-1">机构</span>
            <span class="text-sm text-gray-800">{{ paper.Affiliation || '-' }}</span>
          </div>
          <div>
            <span class="text-xs text-gray-500 block mb-1">DOI</span>
            <span class="text-sm text-gray-800 font-mono">{{ paper.DOI }}</span>
          </div>
          <div>
            <span class="text-xs text-gray-500 block mb-1">来源</span>
            <span class="text-sm text-gray-800">{{ paper.Source || '-' }}</span>
          </div>
        </div>

        <!-- 评论区 -->
        <div class="bg-gray-50 p-4 rounded-xl border border-gray-200">
          <h4 class="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <i class="ph ph-chat-circle-text"></i> 我的评论
          </h4>
          <textarea
            :value="paper.comment"
            @input="localComment = $event.target.value"
            @blur="onCommentBlur"
            placeholder="在这里记录你的想法、笔记或评论..."
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm resize-none"
            rows="4"
          ></textarea>
          <p class="text-xs text-gray-500 mt-2">失焦时自动保存</p>
        </div>
      </div>

      <!-- 抽屉底部 -->
      <div class="p-4 border-t border-gray-100 bg-gray-50 flex flex-wrap gap-2 text-sm">
        <a :href="paper.PDFLink || paper.Link" target="_blank" class="flex-1 min-w-0 bg-primary text-white text-center py-2 rounded-lg font-medium hover:bg-primary/90 transition-colors flex items-center justify-center gap-1.5">
          <i class="ph ph-file-pdf"></i> 阅读原文
        </a>
        <button @click="$router.push(`/reader/${encodeURIComponent(paper.DOI)}`)"
          class="flex-1 min-w-0 py-2 rounded-lg font-medium border border-primary/30 bg-primary/5 text-primary hover:bg-primary/10 transition-colors flex items-center justify-center gap-1.5">
          <i class="ph ph-book-open"></i> 在线阅读
        </button>
        <button @click="$emit('toggle-mark', paper)" :class="['py-2 px-3 rounded-lg font-medium border transition-colors flex items-center justify-center gap-1.5', paper.is_marked ? 'bg-red-50 border-red-200 text-red-600' : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50']">
          <i :class="paper.is_marked ? 'ph-fill ph-heart' : 'ph ph-heart'"></i>
          {{ paper.is_marked ? '取消标记' : '标记' }}
        </button>
        <button @click="$emit('retranslate', paper)" class="py-2 px-3 rounded-lg font-medium border border-blue-200 bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors flex items-center justify-center gap-1.5">
          <i class="ph ph-translate"></i> 翻译
        </button>
        <button @click="$emit('delete', paper)" class="py-2 px-3 rounded-lg font-medium border border-red-200 bg-red-50 text-red-600 hover:bg-red-100 transition-colors flex items-center justify-center gap-1.5">
          <i class="ph ph-trash"></i> 删除
        </button>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  paper: {
    type: Object,
    default: () => ({})
  },
  open: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:open', 'toggle-mark', 'retranslate', 'delete', 'update-comment'])

const localComment = ref('')

// 同步 paper.comment 到 localComment
watch(() => props.paper?.comment, (val) => {
  if (val !== undefined) {
    localComment.value = val
  }
}, { immediate: true })

// 失焦时触发保存
const onCommentBlur = () => {
  emit('update-comment', props.paper, localComment.value)
}
</script>

<style scoped>
.paper-drawer :deep(.el-drawer__body) {
  padding: 0;
  overflow: hidden;
}
</style>
