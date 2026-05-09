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

    <div v-if="getChannelExampleTip(config.active_channel)" class="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
      <p class="text-sm font-medium text-blue-800">示例填写</p>
      <p class="mt-1 text-xs leading-5 text-blue-700">{{ getChannelExampleTip(config.active_channel) }}</p>
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
        <input type="text" v-model="channelData.bark.BARK_PUSH" placeholder="例如: https://api.day.app/DxHcxxxxxRxxxxxxcm/"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">BARK_ARCHIVE</label>
        <input type="text" v-model="channelData.bark.BARK_ARCHIVE" placeholder="例如: 1"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">BARK_GROUP</label>
        <input type="text" v-model="channelData.bark.BARK_GROUP" placeholder="例如: DailyScholar"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">BARK_SOUND</label>
        <input type="text" v-model="channelData.bark.BARK_SOUND" placeholder="例如: bell"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">BARK_ICON</label>
        <input type="text" v-model="channelData.bark.BARK_ICON" placeholder="例如: https://example.com/icon.png"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">BARK_LEVEL</label>
        <input type="text" v-model="channelData.bark.BARK_LEVEL" placeholder="例如: active"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">BARK_URL</label>
        <input type="text" v-model="channelData.bark.BARK_URL" placeholder="例如: https://arxiv.org"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
    </div>

    <!-- dingtalk_app -->
    <div v-if="config.active_channel === 'dingtalk_app'" class="bg-gray-50 p-4 rounded-lg border border-gray-200 space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">App Key</label>
        <input type="text" v-model="channelData.dingtalk_app.app_key" placeholder="例如: dingxxxxxxxxxxxxxxxx"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">App Secret</label>
        <input type="password" v-model="channelData.dingtalk_app.app_secret" placeholder="填写钉钉应用 App Secret"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">Robot Code</label>
        <input type="text" v-model="channelData.dingtalk_app.robot_code" placeholder="例如: dingxxxxxxxxxxxxxxxx"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">Open Conversation ID</label>
        <input type="text" v-model="channelData.dingtalk_app.open_conversation_id" placeholder="例如: cidxxxxxxxxxxxxxxxx"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
    </div>

    <!-- dingtalk_webhook -->
    <div v-if="config.active_channel === 'dingtalk_webhook'" class="bg-gray-50 p-4 rounded-lg border border-gray-200 space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">DD_BOT_TOKEN</label>
        <input type="text" v-model="channelData.dingtalk_webhook.DD_BOT_TOKEN" placeholder="填写 access_token= 后的值"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">DD_BOT_SECRET</label>
        <input type="text" v-model="channelData.dingtalk_webhook.DD_BOT_SECRET" placeholder="例如: SECxxxxxxxxxxxxxxxx"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
    </div>

    <!-- feishu -->
    <div v-if="config.active_channel === 'feishu'" class="bg-gray-50 p-4 rounded-lg border border-gray-200 space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">FSKEY</label>
        <input type="text" v-model="channelData.feishu.FSKEY" placeholder="填写飞书 Webhook 地址最后一段"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">FSSECRET</label>
        <input type="text" v-model="channelData.feishu.FSSECRET" placeholder="例如: xxxx（启用签名校验时填写）"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
    </div>

    <!-- telegram -->
    <div v-if="config.active_channel === 'telegram'" class="bg-gray-50 p-4 rounded-lg border border-gray-200 space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">TG_BOT_TOKEN</label>
        <input type="text" v-model="channelData.telegram.TG_BOT_TOKEN" placeholder="例如: 1407203283:AAG9rt-6RDaaX0HBLZQq0laNOh898iFYaRQ"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">TG_USER_ID</label>
        <input type="text" v-model="channelData.telegram.TG_USER_ID" placeholder="例如: 1434078534"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">TG_API_HOST</label>
        <input type="text" v-model="channelData.telegram.TG_API_HOST" placeholder="例如: https://api.telegram.org"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">TG_PROXY_HOST</label>
        <input type="text" v-model="channelData.telegram.TG_PROXY_HOST" placeholder="例如: 127.0.0.1"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">TG_PROXY_PORT</label>
        <input type="text" v-model="channelData.telegram.TG_PROXY_PORT" placeholder="例如: 7890"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">TG_PROXY_AUTH</label>
        <input type="text" v-model="channelData.telegram.TG_PROXY_AUTH" placeholder="例如: username:password"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
    </div>

    <!-- smtp -->
    <div v-if="config.active_channel === 'smtp'" class="bg-gray-50 p-4 rounded-lg border border-gray-200 space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">SMTP_SERVER</label>
        <input type="text" v-model="channelData.smtp.SMTP_SERVER" placeholder="例如: smtp.exmail.qq.com:465"
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
        <input type="text" v-model="channelData.smtp.SMTP_EMAIL" placeholder="例如: your-name@example.com"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">SMTP_PASSWORD</label>
        <input type="password" v-model="channelData.smtp.SMTP_PASSWORD" placeholder="填写邮箱密码或授权码"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">SMTP_NAME</label>
        <input type="text" v-model="channelData.smtp.SMTP_NAME" placeholder="例如: DailyScholar Bot"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
    </div>

    <!-- wxpusher -->
    <div v-if="config.active_channel === 'wxpusher'" class="bg-gray-50 p-4 rounded-lg border border-gray-200 space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">WXPUSHER_APP_TOKEN</label>
        <input type="text" v-model="channelData.wxpusher.WXPUSHER_APP_TOKEN" placeholder="例如: AT_xxxxxxxxxxxxxxxxxxxx"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">WXPUSHER_TOPIC_IDS</label>
        <input type="text" v-model="channelData.wxpusher.WXPUSHER_TOPIC_IDS" placeholder="例如: 12345;67890"
          class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">WXPUSHER_UIDS</label>
        <input type="text" v-model="channelData.wxpusher.WXPUSHER_UIDS" placeholder="例如: UID_xxx;UID_yyy"
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

const notifyChannelExampleTips = {
  bark: 'BARK_PUSH 可填完整 Bark 地址，也可只填设备码；其余字段按需选填即可。',
  dingtalk_app: '需要从钉钉开放平台复制 App Key、App Secret、Robot Code 和目标会话的 Open Conversation ID。',
  dingtalk_webhook: 'DD_BOT_TOKEN 填 Webhook 地址里 access_token= 后的值；DD_BOT_SECRET 只有在机器人开启加签校验时才需要填写。',
  feishu: 'FSKEY 填飞书 Webhook 地址最后一段；如果开启签名校验，再补充 FSSECRET。',
  telegram: 'TG_BOT_TOKEN 由 BotFather 创建机器人后获取，TG_USER_ID 填个人或群组 chat id。',
  smtp: 'SMTP_SERVER 形如 smtp.exmail.qq.com:465，SMTP_PASSWORD 很多场景下需要填写邮箱授权码。',
  wxpusher: '至少填写 appToken；推送目标用主题 ID 或用户 UID，二者填一个即可，多个值用英文分号分隔。'
}

const getChannelExampleTip = (channel) => notifyChannelExampleTips[channel] || ''

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
