<template>
  <div
    @click="$emit('click', paper)"
    class="bg-white p-5 rounded-xl shadow-sm border border-gray-100 hover:shadow-md hover:border-primary/30 transition-all cursor-pointer group relative"
  >
    <div class="flex justify-between items-start gap-4">
      <div class="flex-1">
        <div class="flex items-center gap-2 mb-2">
          <span v-if="paper.PublicationYear" class="px-2 py-0.5 bg-blue-50 text-blue-600 text-xs font-medium rounded border border-blue-100">{{ paper.PublicationYear }}</span>
          <span :class="['px-2 py-0.5 text-xs font-bold rounded', paper.Stars >= 80 ? 'bg-green-100 text-green-700' : paper.Stars >= 60 ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-600']">{{ paper.Stars }}分</span>
          <span v-if="paper.is_marked" class="text-red-500 text-xs flex items-center gap-1">
            <i class="ph-fill ph-heart"></i> 已标记
          </span>
          <span v-if="paper.is_pushed" class="text-green-600 text-xs flex items-center gap-1">
            <i class="ph-fill ph-paper-plane-tilt"></i> 已推送
          </span>
          <span v-if="paper.comment" class="text-blue-500 text-xs flex items-center gap-1">
            <i class="ph-fill ph-chat-circle-text"></i> 有评论
          </span>
        </div>
        <h3 class="font-semibold text-gray-900 text-lg mb-1 group-hover:text-primary transition-colors line-clamp-2">{{ paper.TitleCN || paper.Title }}</h3>
        <p class="text-sm text-gray-500 mb-3 line-clamp-1">{{ paper.Author }}</p>
        <p class="text-sm text-gray-600 line-clamp-2">{{ paper.RelevanceReason }}</p>
        <!-- 显示评论 -->
        <div v-if="paper.comment" class="mt-3 p-3 bg-blue-50 rounded-lg border border-blue-100">
          <div class="flex items-start gap-2">
            <i class="ph ph-chat-circle-text text-blue-600 text-sm mt-0.5"></i>
            <p class="text-sm text-blue-900 flex-1">{{ paper.comment }}</p>
          </div>
        </div>
      </div>
      <div class="flex flex-col gap-2">
        <button @click.stop="$router.push(`/reader/${encodeURIComponent(paper.DOI)}`)"
          class="p-2 rounded-full hover:bg-gray-100 text-gray-400 hover:text-primary transition-colors" title="在线阅读">
          <i class="ph ph-book-open"></i>
        </button>
        <button @click.stop="$emit('toggle-mark', paper)" class="p-2 rounded-full hover:bg-gray-100 text-gray-400 hover:text-red-500 transition-colors" title="标记/取消标记">
          <i :class="paper.is_marked ? 'ph-fill ph-heart text-red-500' : 'ph ph-heart'"></i>
        </button>
        <button @click.stop="$emit('retranslate', paper)" class="p-2 rounded-full hover:bg-gray-100 text-gray-400 hover:text-blue-500 transition-colors" title="重新翻译">
          <i class="ph ph-translate"></i>
        </button>
        <button @click.stop="$emit('delete', paper)" class="p-2 rounded-full hover:bg-gray-100 text-gray-400 hover:text-red-600 transition-colors" title="删除">
          <i class="ph ph-trash"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  paper: {
    type: Object,
    required: true
  }
})

defineEmits(['click', 'toggle-mark', 'retranslate', 'delete'])
</script>
