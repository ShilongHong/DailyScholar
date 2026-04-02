<template>
  <div class="chat-panel flex flex-col h-full min-h-0 overflow-hidden">
    <div ref="messageListRef" class="flex-1 min-h-0 overflow-y-auto space-y-3 pr-1 pb-2">
      <!-- 推荐问题（无消息时显示） -->
      <div v-if="messages.length === 0 && !streaming" class="space-y-2 mb-3">
        <p class="text-xs text-gray-400 mb-1">试试问我：</p>
        <button
          v-for="(s, i) in suggestions"
          :key="i"
          @click="sendSuggestion(s)"
          class="w-full text-left px-3 py-2 text-xs rounded-lg border border-gray-200 hover:border-primary/30 hover:bg-primary/5 text-gray-600 hover:text-primary transition-colors"
        >
          <i class="ph ph-lightbulb mr-1 text-primary/60"></i>{{ s }}
        </button>
      </div>

      <!-- 消息列表 -->
      <div
        v-for="msg in messages"
        :key="msg.id || msg.created_at"
        :class="[
          'rounded-xl px-3 py-2 text-xs leading-relaxed',
          msg.role === 'user'
            ? 'bg-primary text-white ml-6'
            : 'bg-gray-100 text-gray-800 mr-4'
        ]"
      >
        <div v-if="msg.role === 'assistant'" class="prose prose-sm max-w-none chat-markdown" v-html="renderMarkdown(msg.content)"></div>
        <div v-else>{{ msg.content }}</div>
      </div>

      <!-- 流式输出 -->
      <div v-if="streaming" class="bg-gray-100 rounded-xl px-3 py-2 mr-4 text-xs text-gray-800 leading-relaxed">
        <div class="prose prose-sm max-w-none chat-markdown" v-html="renderMarkdown(streamingContent)"></div>
        <span class="inline-block w-1.5 h-4 bg-primary/70 animate-pulse align-middle ml-0.5"></span>
      </div>

      <!-- 错误提示 -->
      <div v-if="error" class="text-center py-2">
        <p class="text-xs text-red-400">{{ error }}</p>
        <button @click="error = ''" class="text-xs text-gray-400 hover:text-gray-600 mt-1">关闭</button>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="flex gap-2 pt-2 mt-2 border-t border-gray-100 shrink-0 bg-white sticky bottom-0 z-10">
      <input
        ref="inputRef"
        v-model="inputText"
        @keyup.enter="send"
        :disabled="streaming"
        type="text"
        placeholder="输入问题，深入理解这篇论文..."
        class="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-xs focus:border-primary focus:ring-1 focus:ring-primary/30 outline-none disabled:bg-gray-50 disabled:text-gray-400"
      />
      <button
        @click="send"
        :disabled="streaming || !inputText.trim()"
        class="px-3 py-2 bg-primary text-white rounded-lg text-xs hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
      >
        <i class="ph ph-paper-plane-tilt"></i>
      </button>
      <button
        v-if="messages.length > 0"
        @click="clearAll"
        :disabled="streaming"
        class="px-2 py-2 text-gray-400 hover:text-red-500 transition-colors disabled:opacity-40 shrink-0"
        title="清空对话"
      >
        <i class="ph ph-trash text-xs"></i>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { sendChatMessage, fetchChatHistory, clearChatHistory, fetchChatSuggestions } from '@/api'

const props = defineProps({
  doi: { type: String, required: true },
  paper: { type: Object, default: null }
})

const messages = ref([])
const inputText = ref('')
const streaming = ref(false)
const streamingContent = ref('')
const suggestions = ref([])
const error = ref('')
const messageListRef = ref(null)
const inputRef = ref(null)

const renderMarkdown = (text) => {
  if (!text) return ''
  return DOMPurify.sanitize(marked(text))
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

const loadHistory = async () => {
  try {
    const res = await fetchChatHistory(props.doi)
    if (res.data?.success && res.data?.data) {
      messages.value = res.data.data
      scrollToBottom()
    }
  } catch (e) {
    // 404 = no history yet, that's fine
  }
}

const loadSuggestions = async () => {
  try {
    const res = await fetchChatSuggestions(props.doi)
    if (res.data?.success && res.data?.data) {
      suggestions.value = res.data.data
    }
  } catch (e) {
    suggestions.value = [
      '总结这篇论文的核心贡献和创新点',
      '详细解释论文使用的方法论',
      '分析这篇论文的局限性和改进方向',
      '解释论文中的关键公式和数学推导',
    ]
  }
}

const sendSuggestion = (text) => {
  inputText.value = text
  send()
}

const send = async () => {
  const text = inputText.value.trim()
  if (!text || streaming.value) return

  // Optimistic: show user message immediately
  messages.value.push({
    role: 'user',
    content: text,
    created_at: new Date().toISOString()
  })
  inputText.value = ''
  error.value = ''
  scrollToBottom()

  streaming.value = true
  streamingContent.value = ''

  try {
    const response = await sendChatMessage(props.doi, text)

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.detail || `请求失败 (${response.status})`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // Parse SSE lines
      const lines = buffer.split('\n')
      buffer = lines.pop() || '' // Keep incomplete line

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)

        if (data === '[DONE]') {
          // Stream complete
          if (streamingContent.value) {
            messages.value.push({
              role: 'assistant',
              content: streamingContent.value,
              created_at: new Date().toISOString()
            })
          }
          streaming.value = false
          streamingContent.value = ''
          scrollToBottom()
          return
        }

        try {
          const parsed = JSON.parse(data)
          if (parsed.error) {
            error.value = parsed.error
            streaming.value = false
            streamingContent.value = ''
            return
          }
          if (parsed.content) {
            streamingContent.value += parsed.content
            scrollToBottom()
          }
        } catch (e) {
          // Ignore malformed JSON chunks
        }
      }
    }

    // If we exit loop without [DONE], still save what we have
    if (streamingContent.value) {
      messages.value.push({
        role: 'assistant',
        content: streamingContent.value,
        created_at: new Date().toISOString()
      })
    }
  } catch (e) {
    error.value = e.message || '发送失败，请稍后重试'
  } finally {
    streaming.value = false
    streamingContent.value = ''
    scrollToBottom()
  }
}

const clearAll = async () => {
  try {
    await clearChatHistory(props.doi)
    messages.value = []
  } catch (e) {
    error.value = '清空对话失败'
  }
}

watch(() => props.doi, () => {
  messages.value = []
  streaming.value = false
  streamingContent.value = ''
  error.value = ''
  loadHistory()
  loadSuggestions()
})

onMounted(() => {
  loadHistory()
  loadSuggestions()
})
</script>

<style scoped>
.chat-panel {
  min-height: 0;
}

.chat-panel > :first-child {
  scrollbar-gutter: stable;
}

.chat-markdown :deep(h1),
.chat-markdown :deep(h2),
.chat-markdown :deep(h3) {
  font-size: inherit;
  font-weight: 600;
  margin: 0.5rem 0 0.25rem;
}

.chat-markdown :deep(p) {
  margin: 0.3rem 0;
  line-height: 1.6;
}

.chat-markdown :deep(pre) {
  background: #1e293b;
  color: #e2e8f0;
  padding: 0.5rem;
  border-radius: 0.375rem;
  overflow-x: auto;
  font-size: 0.75rem;
  margin: 0.5rem 0;
}

.chat-markdown :deep(code) {
  font-size: 0.75rem;
}

.chat-markdown :deep(ul),
.chat-markdown :deep(ol) {
  padding-left: 1.2rem;
  margin: 0.3rem 0;
}

.chat-markdown :deep(blockquote) {
  border-left: 2px solid #6366f1;
  padding-left: 0.75rem;
  color: #6b7280;
  margin: 0.5rem 0;
}

.chat-markdown :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 0.5rem 0;
  font-size: 0.7rem;
}

.chat-markdown :deep(th),
.chat-markdown :deep(td) {
  border: 1px solid #e5e7eb;
  padding: 0.25rem 0.5rem;
  text-align: left;
}

.chat-markdown :deep(th) {
  background: #f9fafb;
  font-weight: 600;
}
</style>
