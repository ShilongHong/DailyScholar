<template>
  <div class="h-full flex flex-col bg-gray-50">
    <!-- Top bar -->
    <div class="min-h-14 bg-white border-b border-gray-200 flex flex-wrap items-center px-3 md:px-4 py-2 gap-2 md:gap-4 shrink-0">
      <!-- Back button -->
      <button
        @click="$router.back()"
        class="text-gray-500 hover:text-gray-700 flex items-center gap-1 text-sm shrink-0 transition-colors"
      >
        <i class="ph ph-arrow-left text-lg"></i>
        <span>返回</span>
      </button>

      <!-- Divider -->
      <div class="hidden sm:block w-px h-6 bg-gray-200 shrink-0"></div>

      <!-- Paper title -->
      <h2 class="font-semibold text-gray-800 truncate flex-1 min-w-[140px] text-sm">
        {{ paper?.TitleCN || paper?.Title || '加载中...' }}
      </h2>

      <!-- View mode toggle -->
      <div class="flex items-center bg-gray-100 rounded-lg p-0.5 shrink-0 overflow-x-auto">
        <button
          @click="viewMode = 'pdf'"
          :aria-pressed="viewMode === 'pdf'"
          :class="[
            'px-3 py-1.5 rounded-md text-xs font-medium transition-all',
            viewMode === 'pdf'
              ? 'bg-white text-primary shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          ]"
        >
          <i class="ph ph-file-pdf mr-1"></i>PDF
        </button>
        <button
          @click="viewMode = 'markdown'"
          :aria-pressed="viewMode === 'markdown'"
          :class="[
            'px-3 py-1.5 rounded-md text-xs font-medium transition-all',
            viewMode === 'markdown'
              ? 'bg-white text-primary shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          ]"
        >
          <i class="ph ph-article mr-1"></i>Markdown
        </button>
        <button
          v-if="hasHtmlVersion"
          @click="viewMode = 'html'"
          :aria-pressed="viewMode === 'html'"
          :class="[
            'px-3 py-1.5 rounded-md text-xs font-medium transition-all',
            viewMode === 'html'
              ? 'bg-white text-primary shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          ]"
        >
          <i class="ph ph-code mr-1"></i>HTML
        </button>
      </div>

      <!-- Sidebar toggle -->
      <button
        @click="sidebarVisible = !sidebarVisible"
        aria-label="切换侧栏"
        :aria-expanded="sidebarVisible ? 'true' : 'false'"
        :class="[
          'p-2 rounded-lg transition-colors shrink-0',
          sidebarVisible ? 'bg-primary/10 text-primary' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
        ]"
        title="切换侧栏"
      >
        <i class="ph ph-sidebar text-lg"></i>
      </button>
    </div>

    <!-- Main area -->
    <div class="flex-1 flex flex-col lg:flex-row overflow-hidden">
      <!-- Left panel: content viewer -->
      <div class="flex-1 flex flex-col overflow-hidden">
        <!-- Loading state -->
        <div v-if="loading" class="flex-1 flex items-center justify-center">
          <div class="text-center">
            <i class="ph ph-spinner-gap text-4xl text-primary animate-spin mb-3 block"></i>
            <p class="text-gray-500 text-sm">正在加载论文...</p>
          </div>
        </div>

        <!-- Error state -->
        <div v-else-if="error" class="flex-1 flex items-center justify-center">
          <div class="text-center max-w-md">
            <i class="ph ph-warning-circle text-4xl text-red-400 mb-3 block"></i>
            <p class="text-gray-600 text-sm">{{ error }}</p>
            <button @click="fetchPaper" class="mt-3 px-4 py-2 bg-primary text-white rounded-lg text-sm hover:bg-primary/90 transition-colors">
              重试
            </button>
          </div>
        </div>

        <!-- PDF mode -->
        <div v-else-if="viewMode === 'pdf'" class="flex-1 overflow-hidden relative">
          <div v-if="pdfLoading" class="absolute inset-0 flex items-center justify-center bg-gray-50 z-10">
            <div class="text-center">
              <i class="ph ph-spinner-gap text-3xl text-primary animate-spin mb-2 block"></i>
              <p class="text-gray-400 text-sm">正在加载 PDF...</p>
            </div>
          </div>
          <PdfViewer
            :pdf-src="pdfUrl"
            @loaded="pdfLoading = false"
          />
        </div>

        <!-- Markdown mode -->
        <div v-else-if="viewMode === 'markdown'" class="flex-1 overflow-hidden">
          <MarkdownViewer
            :markdown="displayMarkdownContent"
            :loading="markdownLoading"
            :converting="markdownConverting"
            :error="markdownError"
            @convert="handleConvertToMarkdown"
          />
        </div>

        <!-- HTML mode -->
        <div v-else-if="viewMode === 'html'" class="flex-1 overflow-hidden relative">
          <div v-if="htmlLoading" class="absolute inset-0 flex items-center justify-center bg-gray-50 z-10">
            <div class="text-center">
              <i class="ph ph-spinner-gap text-3xl text-primary animate-spin mb-2 block"></i>
              <p class="text-gray-400 text-sm">正在加载 HTML...</p>
            </div>
          </div>
          <div v-if="htmlError" class="absolute inset-0 flex items-center justify-center bg-gray-50 z-10">
            <div class="text-center max-w-md">
              <i class="ph ph-warning-circle text-4xl text-red-400 mb-3 block"></i>
              <p class="text-gray-600 text-sm">{{ htmlError }}</p>
              <a
                v-if="htmlDirectUrl"
                :href="htmlDirectUrl"
                target="_blank"
                rel="noopener noreferrer"
                class="mt-3 inline-block px-4 py-2 bg-primary text-white rounded-lg text-sm hover:bg-primary/90 transition-colors"
              >
                <i class="ph ph-arrow-square-out mr-1"></i>在新标签页打开
              </a>
            </div>
          </div>
          <iframe
            v-show="!htmlError"
            :src="htmlProxyUrl"
            title="论文 HTML 阅读视图"
            class="w-full h-full border-0"
            @load="htmlLoading = false"
            @error="htmlError = 'HTML 页面加载失败，请尝试在新标签页打开'"
          ></iframe>
        </div>
      </div>

      <!-- Right sidebar -->
      <transition name="sidebar-slide">
        <div
          v-show="sidebarVisible"
          class="w-full lg:w-[380px] max-h-[45vh] lg:max-h-none border-t lg:border-t-0 lg:border-l border-gray-200 bg-white overflow-hidden shrink-0"
        >
          <div v-if="!paper" class="flex items-center justify-center h-full">
            <i class="ph ph-spinner-gap text-2xl text-gray-300 animate-spin"></i>
          </div>

          <div v-else class="p-4 h-full overflow-hidden flex flex-col">
            <el-collapse v-model="activeCollapse" class="reader-sidebar-collapse flex-1 min-h-0">
              <!-- Paper info section -->
              <el-collapse-item name="info">
                <template #title>
                  <div class="flex items-center gap-2 text-sm font-semibold text-gray-700">
                    <i class="ph ph-info text-base"></i>
                    论文信息
                  </div>
                </template>

                <div class="space-y-4 pt-1">
                  <!-- Score badge -->
                  <div class="flex items-center gap-2">
                    <span
                      :class="[
                        'px-2.5 py-1 text-xs font-bold rounded-full',
                        paper.Stars >= 80
                          ? 'bg-green-100 text-green-700'
                          : paper.Stars >= 60
                            ? 'bg-yellow-100 text-yellow-700'
                            : 'bg-gray-100 text-gray-600'
                      ]"
                    >
                      {{ paper.Stars }}分 / 100
                    </span>
                    <span v-if="paper.Source" class="px-2.5 py-1 bg-purple-50 text-purple-600 text-xs font-medium rounded-full border border-purple-100">
                      {{ paper.Source }}
                    </span>
                  </div>

                  <!-- Relevance reason -->
                  <div class="bg-blue-50/50 p-3 rounded-xl border border-blue-100">
                    <h4 class="text-xs font-semibold text-blue-800 mb-1.5 flex items-center gap-1.5">
                      <i class="ph ph-thumbs-up"></i> 推荐理由
                    </h4>
                    <p class="text-xs text-blue-900/80 leading-relaxed">
                      {{ paper.RelevanceReason || '暂无' }}
                    </p>
                  </div>

                  <!-- Potential help -->
                  <div v-if="paper.PotentialHelp" class="bg-green-50/50 p-3 rounded-xl border border-green-100">
                    <h4 class="text-xs font-semibold text-green-800 mb-1.5 flex items-center gap-1.5">
                      <i class="ph ph-lightbulb"></i> 潜在帮助
                    </h4>
                    <p class="text-xs text-green-900/80 leading-relaxed">
                      {{ paper.PotentialHelp }}
                    </p>
                  </div>

                  <!-- Chinese abstract -->
                  <el-collapse v-model="abstractCollapse" class="inner-collapse">
                    <el-collapse-item name="cn">
                      <template #title>
                        <span class="text-xs font-bold text-gray-700">中文摘要</span>
                      </template>
                      <p class="text-xs text-gray-700 leading-relaxed">
                        {{ paper.AbstractCN || '暂无翻译' }}
                      </p>
                    </el-collapse-item>
                    <el-collapse-item name="en">
                      <template #title>
                        <span class="text-xs font-bold text-gray-500">English Abstract</span>
                      </template>
                      <p class="text-xs text-gray-500 leading-relaxed">
                        {{ paper.Abstract }}
                      </p>
                    </el-collapse-item>
                  </el-collapse>

                  <!-- Metadata grid -->
                  <div class="grid grid-cols-2 gap-3 pt-2 border-t border-gray-100">
                    <div>
                      <span class="text-xs text-gray-400 block mb-0.5">作者</span>
                      <span class="text-xs text-gray-800 line-clamp-2">{{ paper.Author || '-' }}</span>
                    </div>
                    <div>
                      <span class="text-xs text-gray-400 block mb-0.5">机构</span>
                      <span class="text-xs text-gray-800 line-clamp-2">{{ paper.Affiliation || '-' }}</span>
                    </div>
                    <div>
                      <span class="text-xs text-gray-400 block mb-0.5">DOI</span>
                      <span class="text-xs text-gray-800 font-mono break-all">{{ paper.DOI }}</span>
                    </div>
                    <div>
                      <span class="text-xs text-gray-400 block mb-0.5">来源</span>
                      <span class="text-xs text-gray-800">{{ paper.Source || '-' }}</span>
                    </div>
                    <div>
                      <span class="text-xs text-gray-400 block mb-0.5">年份</span>
                      <span class="text-xs text-gray-800">{{ paper.PublicationYear || '-' }}</span>
                    </div>
                  </div>
                </div>
              </el-collapse-item>

              <!-- Full text translation section -->
              <el-collapse-item name="translate">
                <template #title>
                  <div class="flex items-center gap-2 text-sm font-semibold text-gray-700">
                    <i class="ph ph-translate text-base"></i>
                    全文翻译
                  </div>
                </template>

                <div class="pt-1">
                  <button
                    v-if="!translating && !translation"
                    @click="handleTranslate"
                    class="w-full px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors flex items-center justify-center gap-2"
                  >
                    <i class="ph ph-translate"></i>
                    翻译全文
                  </button>

                  <!-- Translating -->
                  <div v-if="translating" class="flex items-center justify-center py-6">
                    <i class="ph ph-spinner-gap text-2xl text-primary animate-spin mr-2"></i>
                    <span class="text-sm text-gray-500">{{ translatingMessage || '正在翻译，请稍候...' }}</span>
                  </div>

                  <div v-if="translating" class="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      class="h-full bg-primary transition-all duration-300"
                      :style="{ width: `${Math.max(5, translatingProgress)}%` }"
                    ></div>
                  </div>

                  <!-- Translation result -->
                  <div v-if="translation" class="mt-2">
                    <div class="flex items-center justify-between mb-2">
                      <span class="text-xs font-medium text-gray-500">翻译已完成</span>
                      <button
                        @click="resetTranslation"
                        class="text-xs text-gray-400 hover:text-gray-600 transition-colors"
                      >
                        <i class="ph ph-arrow-counter-clockwise mr-0.5"></i>重新翻译
                      </button>
                    </div>

                    <div class="text-xs text-gray-500 mb-2">
                      选择在 Markdown 阅读区的显示方式：
                    </div>

                    <div class="grid grid-cols-3 gap-2 mb-2">
                      <button
                        @click="applyTranslationMode('overwrite')"
                        :class="[
                          'px-2 py-1.5 rounded-lg text-xs border transition-colors',
                          translationDisplayMode === 'overwrite'
                            ? 'bg-primary text-white border-primary'
                            : 'bg-white text-gray-600 border-gray-200 hover:border-primary/40'
                        ]"
                      >
                        覆盖
                      </button>
                      <button
                        @click="applyTranslationMode('bilingual')"
                        :class="[
                          'px-2 py-1.5 rounded-lg text-xs border transition-colors',
                          translationDisplayMode === 'bilingual'
                            ? 'bg-primary text-white border-primary'
                            : 'bg-white text-gray-600 border-gray-200 hover:border-primary/40'
                        ]"
                      >
                        双语对照
                      </button>
                      <button
                        @click="applyTranslationMode('original')"
                        :class="[
                          'px-2 py-1.5 rounded-lg text-xs border transition-colors',
                          translationDisplayMode === 'original'
                            ? 'bg-primary text-white border-primary'
                            : 'bg-white text-gray-600 border-gray-200 hover:border-primary/40'
                        ]"
                      >
                        显示原文
                      </button>
                    </div>

                    <button
                      @click="viewMode = 'markdown'"
                      class="w-full px-3 py-2 text-xs rounded-lg border border-primary/30 text-primary bg-primary/5 hover:bg-primary/10 transition-colors"
                    >
                      在 Markdown 中查看当前效果
                    </button>
                  </div>

                  <p v-if="translateError" class="text-xs text-red-500 mt-2">
                    {{ translateError }}
                  </p>
                </div>
              </el-collapse-item>

              <!-- AI Discussion -->
              <el-collapse-item name="ai" class="ai-collapse-item">
                <template #title>
                  <div class="flex items-center gap-2 text-sm font-semibold text-gray-700">
                    <i class="ph ph-chats-circle text-base"></i>
                    AI 精读
                  </div>
                </template>
                <div class="pt-1 h-full min-h-0">
                  <ChatPanel :doi="doi" :paper="paper" />
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { defineAsyncComponent, ref, computed, watch, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { fetchPaperByDoi, translateFullPaper, fetchTranslateFullStatus, getTranslateFullStreamUrl, fetchPaperMarkdown, convertPaperToMarkdown, fetchConvertStatus } from '@/api'
import MarkdownViewer from '@/components/reader/MarkdownViewer.vue'
import ChatPanel from '@/components/reader/ChatPanel.vue'

const route = useRoute()
const PdfViewer = defineAsyncComponent(() => import('@/components/reader/PdfViewer.vue'))

// State
const paper = ref(null)
const loading = ref(true)
const error = ref('')
const viewMode = ref('pdf')
const sidebarVisible = ref(true)
const pdfLoading = ref(true)

// HTML state
const htmlLoading = ref(true)
const htmlError = ref('')

// Sidebar collapse state
const activeCollapse = ref(['info', 'ai'])
const abstractCollapse = ref(['cn'])

// Translation state
const translating = ref(false)
const translatingProgress = ref(0)
const translatingMessage = ref('')
const translation = ref('')
const bilingualMarkdown = ref('')
const translateError = ref('')
const translationDisplayMode = ref('bilingual')

// Markdown state
const markdownContent = ref('')
const markdownLoading = ref(false)
const markdownConverting = ref(false)
const markdownError = ref('')
let convertPollTimer = null
let translatePollTimer = null
let translateStream = null

// Computed
const doi = computed(() => route.params.doi)
const pdfUrl = computed(() => `/api/papers/${encodeURIComponent(doi.value)}/pdf`)
const hasHtmlVersion = computed(() => {
  const link = paper.value?.PDFLink || paper.value?.Link || ''
  return link.includes('arxiv.org/pdf/')
})
const htmlDirectUrl = computed(() => {
  const link = paper.value?.PDFLink || paper.value?.Link || ''
  if (link.includes('arxiv.org/pdf/')) {
    return link.replace('/pdf/', '/html/')
  }
  return ''
})
const htmlProxyUrl = computed(() => `/api/papers/${encodeURIComponent(doi.value)}/html`)

const splitMarkdownParagraphs = (text) => {
  if (!text || !text.trim()) return []
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const blocks = []
  let current = []
  let inCodeBlock = false

  const flushCurrent = () => {
    const merged = current.join('\n').trim()
    if (merged) blocks.push(merged)
    current = []
  }

  for (const line of lines) {
    const trimmed = line.trim()

    if (trimmed.startsWith('```')) {
      current.push(line)
      inCodeBlock = !inCodeBlock
      if (!inCodeBlock) flushCurrent()
      continue
    }

    if (inCodeBlock) {
      current.push(line)
      continue
    }

    if (!trimmed) {
      flushCurrent()
      continue
    }

    if (/^#{1,6}\s+\S/.test(trimmed)) {
      flushCurrent()
      blocks.push(trimmed)
      continue
    }

    current.push(line)
  }

  flushCurrent()
  return blocks
}

const buildBilingualMarkdown = (original, translated) => {
  const originalParts = splitMarkdownParagraphs(original)
  const translatedParts = splitMarkdownParagraphs(translated)

  if (!originalParts.length || !translatedParts.length) {
    return [
      '# 中文译文',
      '',
      translated || '_暂无译文内容_',
      '',
      '---',
      '',
      '# 原文',
      '',
      original || '_暂无可显示的原文 Markdown 内容_'
    ].join('\n')
  }

  const lines = ['# 双语逐段对照', '']
  const maxLen = Math.max(originalParts.length, translatedParts.length)

  for (let i = 0; i < maxLen; i += 1) {
    const originalPart = originalParts[i]
    const translatedPart = translatedParts[i]

    if (originalPart) {
      lines.push(`> 原文 ${i + 1}`)
      lines.push('')
      lines.push(originalPart)
      lines.push('')
    }

    if (translatedPart) {
      lines.push(`> 译文 ${i + 1}`)
      lines.push('')
      lines.push(translatedPart)
      lines.push('')
    }

    lines.push('---')
    lines.push('')
  }

  return lines.join('\n')
}

const displayMarkdownContent = computed(() => {
  const original = markdownContent.value || ''
  const translated = translation.value || ''

  if (!translated || translationDisplayMode.value === 'original') {
    return original
  }

  if (translationDisplayMode.value === 'overwrite') {
    return translated
  }

  if (bilingualMarkdown.value) {
    return bilingualMarkdown.value
  }

  return buildBilingualMarkdown(original, translated)
})

// Methods
const fetchPaper = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await fetchPaperByDoi(doi.value)
    if (res.data?.success && res.data?.data) {
      paper.value = res.data.data
    } else {
      error.value = '未找到该论文'
    }
  } catch (e) {
    if (e.response?.status === 404) {
      error.value = '未找到该论文'
    } else {
      error.value = '加载论文失败，请检查网络连接'
    }
  } finally {
    loading.value = false
  }
}

const handleTranslate = async (force = false) => {
  if (translating.value) return
  translating.value = true
  translatingProgress.value = 0
  translatingMessage.value = '翻译任务已启动...'
  translateError.value = ''
  try {
    await translateFullPaper(doi.value, 'markdown', force)
    startTranslateStream()
  } catch (e) {
    translating.value = false
    translateError.value = '翻译请求失败，请稍后重试'
  }
}

const applyTranslateTaskData = (data) => {
  const status = data?.status

  if (status === 'completed') {
    translating.value = false
    translatingProgress.value = 100
    translatingMessage.value = '翻译完成'
    translation.value = data.translation || '翻译完成，但未返回结果'
    bilingualMarkdown.value = data.bilingual_markdown || ''
    translationDisplayMode.value = 'bilingual'
    viewMode.value = 'markdown'
    return true
  }

  if (status === 'failed' || status === 'error') {
    translating.value = false
    translateError.value = data.error || data.message || '翻译失败'
    return true
  }

  if (status === 'processing') {
    translating.value = true
    translatingProgress.value = Number(data.progress || 0)
    translatingMessage.value = data.message || '正在翻译，请稍候...'
  } else if (status === 'pending') {
    translating.value = true
    translatingMessage.value = data.message || '等待翻译任务开始...'
  }

  return false
}

const startTranslateStream = () => {
  if (translateStream) {
    translateStream.close()
    translateStream = null
  }

  const streamUrl = getTranslateFullStreamUrl(doi.value)
  translateStream = new EventSource(streamUrl)

  translateStream.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      const done = applyTranslateTaskData(data)
      if (done && translateStream) {
        translateStream.close()
        translateStream = null
      }
    } catch (e) {
      // 忽略单条消息解析失败，继续接收下一条
    }
  }

  translateStream.onerror = () => {
    if (translateStream) {
      translateStream.close()
      translateStream = null
    }
    // 流中断时自动降级轮询，避免误报翻译失败
    if (translating.value) {
      translatingMessage.value = '连接波动，正在切换到轮询模式...'
      startTranslatePolling()
    }
  }
}

const startTranslatePolling = () => {
  if (translatePollTimer) clearInterval(translatePollTimer)
  let failure_count = 0
  translatePollTimer = setInterval(async () => {
    try {
      const res = await fetchTranslateFullStatus(doi.value)
      const data = res.data?.data || {}
      failure_count = 0
      const done = applyTranslateTaskData(data)
      if (done) {
        clearInterval(translatePollTimer)
        translatePollTimer = null
        return
      }
    } catch (e) {
      failure_count += 1
      translating.value = true
      translatingMessage.value = '网络波动，正在重试获取进度...'
      // 连续多次失败再提示，但不直接中断后台任务
      if (failure_count >= 8) {
        clearInterval(translatePollTimer)
        translatePollTimer = null
        translating.value = false
        translateError.value = '进度查询异常，请稍后点“翻译全文”继续查看状态'
      }
    }
  }, 2000)
}

const applyTranslationMode = (mode) => {
  translationDisplayMode.value = mode
  viewMode.value = 'markdown'
}

const resetTranslation = async () => {
  if (translating.value) return
  translation.value = ''
  bilingualMarkdown.value = ''
  translationDisplayMode.value = 'bilingual'
  await handleTranslate(true)
}

// Load existing markdown content
const loadMarkdown = async () => {
  if (!doi.value) return
  markdownLoading.value = true
  markdownError.value = ''
  try {
    const res = await fetchPaperMarkdown(doi.value)
    if (res.data?.success && res.data?.data?.markdown) {
      markdownContent.value = res.data.data.markdown
    } else {
      markdownContent.value = ''
    }
  } catch (e) {
    // 404 means no markdown yet - that's fine, show convert button
    if (e.response?.status !== 404) {
      markdownError.value = '加载 Markdown 失败'
    }
    markdownContent.value = ''
  } finally {
    markdownLoading.value = false
  }
}

// Trigger conversion
const handleConvertToMarkdown = async () => {
  if (markdownConverting.value) return
  markdownConverting.value = true
  markdownError.value = ''
  try {
    await convertPaperToMarkdown(doi.value)
    // Start polling for status
    startConvertPolling()
  } catch (e) {
    markdownConverting.value = false
    markdownError.value = '转换请求失败，请稍后重试'
  }
}

const startConvertPolling = () => {
  if (convertPollTimer) clearInterval(convertPollTimer)
  convertPollTimer = setInterval(async () => {
    try {
      const res = await fetchConvertStatus(doi.value)
      const status = res.data?.data?.status
      if (status === 'completed' || status === 'done') {
        clearInterval(convertPollTimer)
        convertPollTimer = null
        markdownConverting.value = false
        await loadMarkdown()
      } else if (status === 'failed' || status === 'error') {
        clearInterval(convertPollTimer)
        convertPollTimer = null
        markdownConverting.value = false
        markdownError.value = res.data?.data?.error || '转换失败'
      }
    } catch (e) {
      clearInterval(convertPollTimer)
      convertPollTimer = null
      markdownConverting.value = false
      markdownError.value = '查询转换状态失败'
    }
  }, 3000)
}

// When switching to markdown mode, try loading existing content
// When switching to html mode, reset loading state
watch(viewMode, (mode) => {
  if (mode === 'markdown' && !markdownContent.value && !markdownLoading.value) {
    loadMarkdown()
  }
  if (mode === 'html') {
    htmlLoading.value = true
    htmlError.value = ''
  }
})

onBeforeUnmount(() => {
  if (convertPollTimer) {
    clearInterval(convertPollTimer)
    convertPollTimer = null
  }
  if (translatePollTimer) {
    clearInterval(translatePollTimer)
    translatePollTimer = null
  }
  if (translateStream) {
    translateStream.close()
    translateStream = null
  }
})

watch(doi, () => {
  fetchPaper()
}, { immediate: true })
</script>

<style scoped>
.sidebar-slide-enter-active,
.sidebar-slide-leave-active {
  transition: all 0.25s ease;
}
.sidebar-slide-enter-from,
.sidebar-slide-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

/* Override Element Plus collapse styling for reader sidebar */
.reader-sidebar-collapse :deep(.el-collapse-item__header) {
  padding: 8px 0;
  height: auto;
  line-height: 1.5;
  border-bottom: none;
  background: transparent;
}

.reader-sidebar-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
  background: transparent;
}

.reader-sidebar-collapse :deep(.el-collapse-item__content) {
  padding-bottom: 0;
}

.reader-sidebar-collapse :deep(.el-collapse) {
  border-top: none;
  border-bottom: none;
}

.reader-sidebar-collapse {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.reader-sidebar-collapse :deep(.el-collapse-item.ai-collapse-item) {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.reader-sidebar-collapse :deep(.el-collapse-item.ai-collapse-item > .el-collapse-item__wrap) {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.reader-sidebar-collapse :deep(.el-collapse-item.ai-collapse-item .el-collapse-item__content) {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.inner-collapse :deep(.el-collapse-item__header) {
  padding: 4px 0;
  height: auto;
  line-height: 1.5;
  font-size: 12px;
  border-bottom: none;
  background: transparent;
}

.inner-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
  background: transparent;
}

.inner-collapse :deep(.el-collapse) {
  border-top: none;
  border-bottom: none;
}
</style>
