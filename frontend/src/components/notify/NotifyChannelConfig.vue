<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h3 class="text-lg font-medium text-gray-900">通知渠道设置</h3>
    </div>

    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">当前使用渠道</label>
      <select
        :value="config.active_channel"
        @change="onChannelChange"
        class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50"
      >
        <option value="console">控制台（无需配置）</option>
        <option value="bark">Bark</option>
        <option value="dingtalk_app">钉钉应用机器人</option>
        <option value="dingtalk_webhook">钉钉Webhook机器人</option>
        <option value="feishu">飞书机器人</option>
        <option value="telegram">Telegram</option>
        <option value="smtp">SMTP邮件</option>
        <option value="wxpusher">WxPusher</option>
      </select>
    </div>

    <!-- console -->
    <div v-if="config.active_channel === 'console'" class="bg-gray-50 p-4 rounded-lg border border-gray-200">
      <label class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
        <input type="checkbox" v-model="channelData.console.CONSOLE" class="rounded text-primary focus:ring-primary">
        启用控制台输出
      </label>
    </div>

    <!-- bark -->
    <div v-if="config.active_channel === 'bark'" class="bg-gray-50 p-4 rounded-lg border border-gray-200 space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">BARK_PUSH</label>
        <input type="text" v-model="channelData.bark.BARK_PUSH" placeholder="必填"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">BARK_ARCHIVE</label>
        <input type="text" v-model="channelData.bark.BARK_ARCHIVE"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">BARK_GROUP</label>
        <input type="text" v-model="channelData.bark.BARK_GROUP"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">BARK_SOUND</label>
        <input type="text" v-model="channelData.bark.BARK_SOUND"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">BARK_ICON</label>
        <input type="text" v-model="channelData.bark.BARK_ICON"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">BARK_LEVEL</label>
        <input type="text" v-model="channelData.bark.BARK_LEVEL"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">BARK_URL</label>
        <input type="text" v-model="channelData.bark.BARK_URL"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
    </div>

    <!-- dingtalk_app -->
    <div v-if="config.active_channel === 'dingtalk_app'" class="bg-gray-50 p-4 rounded-lg border border-gray-200 space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">App Key</label>
        <input type="text" v-model="channelData.dingtalk_app.app_key" placeholder="必填"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">App Secret</label>
        <input type="password" v-model="channelData.dingtalk_app.app_secret" placeholder="必填"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">Robot Code</label>
        <input type="text" v-model="channelData.dingtalk_app.robot_code" placeholder="必填"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">Open Conversation ID</label>
        <input type="text" v-model="channelData.dingtalk_app.open_conversation_id" placeholder="必填"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
    </div>

    <!-- dingtalk_webhook -->
    <div v-if="config.active_channel === 'dingtalk_webhook'" class="bg-gray-50 p-4 rounded-lg border border-gray-200 space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">DD_BOT_TOKEN</label>
        <input type="text" v-model="channelData.dingtalk_webhook.DD_BOT_TOKEN" placeholder="必填"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">DD_BOT_SECRET</label>
        <input type="text" v-model="channelData.dingtalk_webhook.DD_BOT_SECRET"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
    </div>

    <!-- feishu -->
    <div v-if="config.active_channel === 'feishu'" class="bg-gray-50 p-4 rounded-lg border border-gray-200 space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">FSKEY</label>
        <input type="text" v-model="channelData.feishu.FSKEY" placeholder="必填"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">FSSECRET</label>
        <input type="text" v-model="channelData.feishu.FSSECRET"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
    </div>

    <!-- telegram -->
    <div v-if="config.active_channel === 'telegram'" class="bg-gray-50 p-4 rounded-lg border border-gray-200 space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">TG_BOT_TOKEN</label>
        <input type="text" v-model="channelData.telegram.TG_BOT_TOKEN" placeholder="必填"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">TG_USER_ID</label>
        <input type="text" v-model="channelData.telegram.TG_USER_ID" placeholder="必填"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">TG_API_HOST</label>
        <input type="text" v-model="channelData.telegram.TG_API_HOST"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">TG_PROXY_HOST</label>
        <input type="text" v-model="channelData.telegram.TG_PROXY_HOST"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">TG_PROXY_PORT</label>
        <input type="text" v-model="channelData.telegram.TG_PROXY_PORT"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">TG_PROXY_AUTH</label>
        <input type="text" v-model="channelData.telegram.TG_PROXY_AUTH"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
    </div>

    <!-- smtp -->
    <div v-if="config.active_channel === 'smtp'" class="bg-gray-50 p-4 rounded-lg border border-gray-200 space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">SMTP_SERVER</label>
        <input type="text" v-model="channelData.smtp.SMTP_SERVER" placeholder="必填"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div class="pt-2">
        <label class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
          <input type="checkbox" v-model="channelData.smtp.SMTP_SSL" class="rounded text-primary focus:ring-primary">
          启用 SMTP SSL
        </label>
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">SMTP_EMAIL</label>
        <input type="text" v-model="channelData.smtp.SMTP_EMAIL" placeholder="必填"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">SMTP_PASSWORD</label>
        <input type="password" v-model="channelData.smtp.SMTP_PASSWORD" placeholder="必填"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">SMTP_NAME</label>
        <input type="text" v-model="channelData.smtp.SMTP_NAME" placeholder="必填"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
    </div>

    <!-- wxpusher -->
    <div v-if="config.active_channel === 'wxpusher'" class="bg-gray-50 p-4 rounded-lg border border-gray-200 space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">WXPUSHER_APP_TOKEN</label>
        <input type="text" v-model="channelData.wxpusher.WXPUSHER_APP_TOKEN" placeholder="必填"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">WXPUSHER_TOPIC_IDS</label>
        <input type="text" v-model="channelData.wxpusher.WXPUSHER_TOPIC_IDS"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">WXPUSHER_UIDS</label>
        <input type="text" v-model="channelData.wxpusher.WXPUSHER_UIDS"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue'

const props = defineProps({
  config: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['update:config'])

// 所有已知渠道
const ALL_CHANNELS = ['console', 'bark', 'dingtalk_app', 'dingtalk_webhook', 'feishu', 'telegram', 'smtp', 'wxpusher']

// 确保渠道配置存在
const ensureNotifyChannelConfig = (channel) => {
  if (!props.config) return
  if (!props.config.channels) {
    props.config.channels = {}
  }
  if (!props.config.channels[channel]) {
    props.config.channels[channel] = channel === 'console' ? { CONSOLE: true } : {}
  }
}

// 初始化所有渠道
ALL_CHANNELS.forEach(ch => ensureNotifyChannelConfig(ch))

// 代理对象，让 v-model 直接操作 props.config.channels.xxx
const channelData = reactive({})

// 为每个渠道创建代理引用
ALL_CHANNELS.forEach(ch => {
  ensureNotifyChannelConfig(ch)
  channelData[ch] = props.config.channels[ch]
})

// 切换渠道时确保配置存在
const onChannelChange = (e) => {
  const newChannel = e.target.value
  ensureNotifyChannelConfig(newChannel)
  // 更新 active_channel
  props.config.active_channel = newChannel
  // 更新代理引用
  channelData[newChannel] = props.config.channels[newChannel]
  emit('update:config', { ...props.config })
}

// 监听 config 变化（外部重新加载时）
watch(() => props.config, (newConfig) => {
  if (newConfig?.channels) {
    ALL_CHANNELS.forEach(ch => {
      if (newConfig.channels[ch]) {
        channelData[ch] = newConfig.channels[ch]
      }
    })
  }
}, { deep: true })
</script>
