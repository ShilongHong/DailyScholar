<template>
  <div class="markdown-viewer h-full overflow-auto">
    <!-- 顶部工具栏 -->
    <div v-if="!loading && !error" class="sticky top-0 z-10 bg-gray-50/95 backdrop-blur border-b border-gray-200 px-8 py-2 flex items-center justify-between">
      <span class="text-xs text-gray-400">Markdown 预览</span>
      <el-button size="small" @click="$emit('convert')" :loading="converting">
        <i class="ph ph-arrows-clockwise mr-1"></i>
        {{ converting ? '转换中...' : '重新转换' }}
      </el-button>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="flex items-center justify-center h-full">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <span class="ml-3 text-gray-500">加载 Markdown 内容...</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="error" class="text-center py-12 text-gray-500">
      <i class="ph ph-warning-circle text-3xl mb-2"></i>
      <p class="mb-4">{{ error }}</p>
      <el-button type="primary" @click="$emit('convert')" :loading="converting">
        {{ converting ? '转换中...' : '重新转换' }}
      </el-button>
    </div>

    <!-- 无内容 -->
    <div v-else-if="!markdown" class="text-center py-20">
      <i class="ph ph-file-doc text-4xl text-gray-300 mb-4 block"></i>
      <p class="text-gray-500 mb-4">尚未转换为 Markdown</p>
      <el-button type="primary" @click="$emit('convert')" :loading="converting">
        {{ converting ? '转换中...' : '转换为 Markdown' }}
      </el-button>
    </div>

    <!-- Markdown 内容 -->
    <div v-else class="prose prose-sm max-w-4xl mx-auto p-8" v-html="renderedMarkdown"></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import katex from 'katex'

const props = defineProps({
  markdown: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  converting: { type: Boolean, default: false },
  error: { type: String, default: '' }
})

defineEmits(['convert'])

/**
 * 将 LaTeX 数学公式渲染为 HTML
 * 先保护 HTML 标签内容，只对纯文本部分做 KaTeX 渲染
 */
function renderMath(text) {
  if (!text) return ''

  // 兼容 LLM 常见输出：\(...\)、\[...\] 以及部分缺失反斜杠的闭合符
  const normalizedText = text
    .replace(/\\\(([^\n]*?)\)/g, '\\($1\\)')
    .replace(/\\\[([\s\S]*?)\]/g, '\\[$1\\]')

  // 保护 HTML 标签：用占位符替换，避免 KaTeX 误处理标签内的 $ 符号
  const htmlChunks = []
  const protected_ = normalizedText.replace(/<[^>]+>/g, (match) => {
    htmlChunks.push(match)
    return `\x00HTML${htmlChunks.length - 1}\x00`
  })

  // 处理块级公式 \[...\]
  let result = protected_.replace(/\\\[([\s\S]*?)\\\]/g, (_, math) => {
    try {
      return katex.renderToString(math.trim(), { displayMode: true, throwOnError: false })
    } catch {
      return `<span class="text-red-400">[公式渲染失败: ${math.substring(0, 30)}...]</span>`
    }
  })

  // 处理行内公式 \(...\)
  result = result.replace(/\\\(([^\n]*?)\\\)/g, (_, math) => {
    try {
      return katex.renderToString(math.trim(), { displayMode: false, throwOnError: false })
    } catch {
      return `<span class="text-red-400">[公式: ${math}]</span>`
    }
  })

  // 处理块级公式 $$...$$
  result = result.replace(/\$\$([\s\S]*?)\$\$/g, (_, math) => {
    try {
      return katex.renderToString(math.trim(), { displayMode: true, throwOnError: false })
    } catch {
      return `<span class="text-red-400">[公式渲染失败: ${math.substring(0, 30)}...]</span>`
    }
  })

  // 处理行内公式 $...$（不匹配 $$，且内容不含换行）
  result = result.replace(/(?<!\$)\$(?!\$)([^\$\n]+?)(?<!\$)\$(?!\$)/g, (_, math) => {
    try {
      return katex.renderToString(math.trim(), { displayMode: false, throwOnError: false })
    } catch {
      return `<span class="text-red-400">[公式: ${math}]</span>`
    }
  })

  // 恢复 HTML 标签
  result = result.replace(/\x00HTML(\d+)\x00/g, (_, i) => htmlChunks[i])

  return result
}

const renderedMarkdown = computed(() => {
  if (!props.markdown) return ''
  const withMath = renderMath(props.markdown)
  const rawHtml = marked(withMath)
  return DOMPurify.sanitize(rawHtml, {
    ADD_TAGS: ['math', 'semantics', 'mrow', 'mi', 'mo', 'mn', 'msup', 'msub', 'mfrac', 'msqrt', 'mroot', 'mover', 'munder', 'mtable', 'mtr', 'mtd', 'mtext', 'mstyle', 'mpadded', 'mspace', 'annotation'],
    ADD_ATTR: ['mathvariant', 'mathsize', 'mathcolor', 'displaystyle', 'scriptlevel', 'stretchy', 'lspace', 'rspace', 'minsize', 'maxsize', 'movablelimits', 'accent', 'separator', 'linethickness', 'columnalign', 'encoding']
  })
})
</script>

<style scoped>
.markdown-viewer :deep(h1) { font-size: 1.5rem; font-weight: 700; margin: 1.5rem 0 1rem; }
.markdown-viewer :deep(h2) { font-size: 1.25rem; font-weight: 600; margin: 1.25rem 0 0.75rem; }
.markdown-viewer :deep(h3) { font-size: 1.1rem; font-weight: 600; margin: 1rem 0 0.5rem; }
.markdown-viewer :deep(p) { margin: 0.75rem 0; line-height: 1.7; }
.markdown-viewer :deep(pre) { background: #1e293b; color: #e2e8f0; padding: 1rem; border-radius: 0.5rem; overflow-x: auto; }
.markdown-viewer :deep(code) { font-size: 0.875rem; }
.markdown-viewer :deep(table) { border-collapse: collapse; width: 100%; margin: 1rem 0; }
.markdown-viewer :deep(th), .markdown-viewer :deep(td) { border: 1px solid #e5e7eb; padding: 0.5rem 0.75rem; text-align: left; }
.markdown-viewer :deep(th) { background: #f9fafb; font-weight: 600; }
.markdown-viewer :deep(img) { max-width: 100%; border-radius: 0.5rem; margin: 1rem 0; }
.markdown-viewer :deep(blockquote) { border-left: 3px solid #6366f1; padding-left: 1rem; color: #6b7280; margin: 1rem 0; }
.markdown-viewer :deep(.katex-display) { margin: 1rem 0; overflow-x: auto; }
.markdown-viewer :deep(.katex) { font-size: 1.05em; }
</style>
