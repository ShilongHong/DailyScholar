import { ref, nextTick } from 'vue'
import {
  fetchExistingConfig,
  saveConfig,
  saveResearchDescription,
  completeSetup,
  testDBConnection as apiTestDB,
  testLLMConnection as apiTestLLM,
  testNotifyChannel as apiTestNotify,
  generateResearch as apiGenerateResearch
} from '@/api'
import { useToast } from '@/composables/useToast'

export function useWizard() {
  const { showToast } = useToast()

  // ========== 向导状态 ==========
  const wizardOpen = ref(false)
  const wizardStep = ref(1)
  const wizardTesting = ref(false)
  const wizardTestResults = ref({ db: null, llm: null, notify: null })
  const existingConfig = ref(null)
  const configCheckDone = ref(false)

  const wizardData = ref({
    db: { db_type: 'sqlite', host: '', port: 3306, user: '', password: '', database: '', sqlite_path: 'data/papers.db' },
    research: '',
    llm: { api_key: '', base_url: '', model: '' },
    arxiv: { keywords: ['cs.CL', 'cs.CV', 'cs.LG', 'cs.AI'], max_results_per_keyword: 100 },
    notify: { channel: 'console', config: {} }
  })

  const wizardNewKeyword = ref('')
  const researchBrief = ref('')
  const generatingResearch = ref(false)
  const aiGeneratedKeywords = ref([])
  const aiGeneratedLlmConfig = ref(null)
  const editableGeneratedConfig = ref({
    anchors: { high: '', medium: '', low: '' },
    examples: {
      high: { title: '', abstract: '', score: 90, reason: '' },
      medium: { title: '', abstract: '', score: 60, reason: '' },
      low: { title: '', abstract: '', score: 15, reason: '' }
    }
  })

  // ========== 静态数据 ==========
  const wizardStepNames = ['欢迎', '数据库', 'LLM配置', '研究方向', 'ArXiv搜索', '通知渠道', '完成']

  const arxivCategories = [
    { code: 'cs.CL', name: '计算语言学' },
    { code: 'cs.CV', name: '计算机视觉' },
    { code: 'cs.LG', name: '机器学习' },
    { code: 'cs.AI', name: '人工智能' },
    { code: 'cs.IR', name: '信息检索' },
    { code: 'cs.RO', name: '机器人学' },
    { code: 'cs.NE', name: '神经与进化计算' },
    { code: 'cs.CR', name: '密码学与安全' },
    { code: 'cs.SE', name: '软件工程' },
    { code: 'cs.DC', name: '分布式计算' },
    { code: 'cs.NI', name: '网络与互联网' },
    { code: 'stat.ML', name: '统计机器学习' },
    { code: 'eess.SP', name: '信号处理' },
    { code: 'eess.IV', name: '图像与视频处理' }
  ]

  const notifyChannelOptions = [
    { value: 'console', label: '控制台（无需配置）' },
    { value: 'bark', label: 'Bark' },
    { value: 'dingtalk_app', label: '钉钉应用机器人' },
    { value: 'dingtalk_webhook', label: '钉钉Webhook机器人' },
    { value: 'feishu', label: '飞书机器人' },
    { value: 'telegram', label: 'Telegram' },
    { value: 'smtp', label: 'SMTP邮件' },
    { value: 'wxpusher', label: 'WxPusher' }
  ]

  const notifyChannelFields = {
    bark: [
      { key: 'BARK_PUSH', label: 'BARK_PUSH', required: true },
      { key: 'BARK_ARCHIVE', label: 'BARK_ARCHIVE' },
      { key: 'BARK_GROUP', label: 'BARK_GROUP' },
      { key: 'BARK_SOUND', label: 'BARK_SOUND' },
      { key: 'BARK_ICON', label: 'BARK_ICON' }
    ],
    dingtalk_app: [
      { key: 'app_key', label: 'App Key', required: true },
      { key: 'app_secret', label: 'App Secret', type: 'password', required: true },
      { key: 'robot_code', label: 'Robot Code', required: true },
      { key: 'open_conversation_id', label: 'Open Conversation ID', required: true }
    ],
    dingtalk_webhook: [
      { key: 'DD_BOT_TOKEN', label: 'DD_BOT_TOKEN', required: true },
      { key: 'DD_BOT_SECRET', label: 'DD_BOT_SECRET' }
    ],
    feishu: [
      { key: 'FSKEY', label: 'FSKEY', required: true },
      { key: 'FSSECRET', label: 'FSSECRET' }
    ],
    telegram: [
      { key: 'TG_BOT_TOKEN', label: 'TG_BOT_TOKEN', required: true },
      { key: 'TG_USER_ID', label: 'TG_USER_ID', required: true },
      { key: 'TG_API_HOST', label: 'TG_API_HOST' }
    ],
    smtp: [
      { key: 'SMTP_SERVER', label: 'SMTP_SERVER', required: true },
      { key: 'SMTP_EMAIL', label: 'SMTP_EMAIL', required: true },
      { key: 'SMTP_PASSWORD', label: 'SMTP_PASSWORD', type: 'password', required: true },
      { key: 'SMTP_NAME', label: 'SMTP_NAME', required: true }
    ],
    wxpusher: [
      { key: 'WXPUSHER_APP_TOKEN', label: 'WXPUSHER_APP_TOKEN', required: true },
      { key: 'WXPUSHER_TOPIC_IDS', label: 'WXPUSHER_TOPIC_IDS' },
      { key: 'WXPUSHER_UIDS', label: 'WXPUSHER_UIDS' }
    ]
  }

  // ========== 向导方法 ==========

  const loadExistingConfig = async () => {
    try {
      const res = await fetchExistingConfig()
      const data = res.data
      if (data.success) {
        existingConfig.value = data.data
        configCheckDone.value = true
        if (data.data.has_mysql && data.data.mysql) {
          wizardData.value.db = {
            db_type: data.data.mysql.db_type || 'mysql',
            host: data.data.mysql.host || '',
            port: data.data.mysql.port || 3306,
            user: data.data.mysql.user || '',
            password: '',
            database: data.data.mysql.database || '',
            sqlite_path: data.data.mysql.sqlite_path || 'data/papers.db'
          }
        }
        if (data.data.research_description) {
          wizardData.value.research = data.data.research_description
        }
        if (data.data.llm) {
          wizardData.value.llm = {
            api_key: '',
            base_url: data.data.llm.base_url || '',
            model: data.data.llm.model || ''
          }
        }
        if (data.data.arxiv) {
          wizardData.value.arxiv.keywords = data.data.arxiv.keywords || []
        }
        if (data.data.notify) {
          wizardData.value.notify.channel = data.data.notify.active_channel || 'console'
        }
      }
    } catch (e) {
      console.error('加载现有配置失败:', e)
    }
  }

  const resetWizardData = () => {
    wizardData.value = {
      db: { db_type: 'sqlite', host: '', port: 3306, user: '', password: '', database: '', sqlite_path: 'data/papers.db' },
      research: '',
      llm: { api_key: '', base_url: '', model: '' },
      arxiv: { keywords: ['cs.CL', 'cs.CV', 'cs.LG', 'cs.AI'], max_results_per_keyword: 100 },
      notify: { channel: 'console', config: {} }
    }
    wizardTestResults.value = { db: null, llm: null, notify: null }
    wizardStep.value = 2
  }

  const openWizard = async () => {
    configCheckDone.value = false
    existingConfig.value = null
    await loadExistingConfig()
    wizardStep.value = 1
    wizardTestResults.value = { db: null, llm: null, notify: null }
    wizardOpen.value = true
  }

  const nextWizardStep = async () => {
    await saveWizardStepData()
    if (wizardStep.value < 7) {
      if (wizardStep.value === 4 && aiGeneratedKeywords.value.length > 0) {
        const existing = new Set(wizardData.value.arxiv.keywords)
        aiGeneratedKeywords.value.forEach(kw => existing.add(kw))
        wizardData.value.arxiv.keywords = Array.from(existing)
      }
      wizardStep.value++
    } else {
      await completeWizard()
    }
  }

  const prevWizardStep = () => {
    if (wizardStep.value > 1) {
      wizardStep.value--
    }
  }

  const skipWizardStep = () => {
    if (wizardStep.value < 7) {
      wizardStep.value++
    }
  }

  // 保存当前步骤数据
  const saveWizardStepData = async () => {
    try {
      const step = wizardStep.value
      if (step === 2) {
        const dbConfig = {
          enable: true,
          db_type: wizardData.value.db.db_type || 'sqlite'
        }
        if (wizardData.value.db.db_type === 'mysql') {
          dbConfig.host = wizardData.value.db.host
          dbConfig.port = wizardData.value.db.port
          dbConfig.user = wizardData.value.db.user
          dbConfig.password = wizardData.value.db.password
          dbConfig.database = wizardData.value.db.database
        } else {
          dbConfig.sqlite_path = wizardData.value.db.sqlite_path || 'data/papers.db'
        }
        await saveConfig('mysql', dbConfig)
      } else if (step === 3) {
        await saveConfig('llm_filter', wizardData.value.llm)
      } else if (step === 4) {
        await saveResearchDescription(wizardData.value.research)
      } else if (step === 5) {
        await saveConfig('arxiv', {
          keywords: wizardData.value.arxiv.keywords,
          max_results_per_keyword: wizardData.value.arxiv.max_results_per_keyword
        })
      } else if (step === 6) {
        const notifyConfig = {
          active_channel: wizardData.value.notify.channel,
          channels: {}
        }
        notifyConfig.channels[wizardData.value.notify.channel] = wizardData.value.notify.config
        await saveConfig('notify', notifyConfig)
      }
    } catch (e) {
      console.error('保存向导步骤数据失败:', e)
    }
  }

  // 完成向导
  const completeWizard = async () => {
    try {
      // 如果有 AI 生成的 LLM 配置，先保存到 prompt_config
      if (aiGeneratedLlmConfig.value) {
        const config = {
          ...aiGeneratedLlmConfig.value,
          scoring_anchors: {
            high_score_keywords: editableGeneratedConfig.value.anchors.high.split('\n').map(v => v.trim()).filter(Boolean),
            medium_score_keywords: editableGeneratedConfig.value.anchors.medium.split('\n').map(v => v.trim()).filter(Boolean),
            low_score_keywords: editableGeneratedConfig.value.anchors.low.split('\n').map(v => v.trim()).filter(Boolean)
          },
          few_shot_examples: {
            high_score: { ...editableGeneratedConfig.value.examples.high },
            medium_score: { ...editableGeneratedConfig.value.examples.medium },
            low_score: { ...editableGeneratedConfig.value.examples.low }
          }
        }

        // 构建 scoring_anchors 字符串
        if (config.scoring_anchors) {
          const anchors = config.scoring_anchors
          const anchorsText = `## 评分参考锚点

### 高分信号（每项可得20-25分）
**问题相关关键词**：${(anchors.high_score_keywords || []).join(', ')}

**方法相关关键词**：视觉语言模型、多模态方法、深度学习架构

**数据/资源关键词**：开源数据集、可复现代码

### 中等分数信号（每项10-19分）
${(anchors.medium_score_keywords || []).map(k => `- ${k}`).join('\n')}

### 低分信号（每项0-9分）
${(anchors.low_score_keywords || []).map(k => `- ${k}`).join('\n')}`

          await saveConfig('prompt_config', { llm_scoring_anchors: anchorsText })
        }

        // 构建 few_shot_examples 字符串
        if (config.few_shot_examples) {
          const examples = config.few_shot_examples
          const examplesText = `## 评分示例

### 示例1（高分论文）
标题：${examples.high_score?.title || '高相关论文'}
摘要：${examples.high_score?.abstract || ''}

评估结果：
\`\`\`json
{
  "total_score": ${examples.high_score?.score || 90},
  "reason": "${examples.high_score?.reason || '高度相关'}"
}
\`\`\`

### 示例2（中等分数论文）
标题：${examples.medium_score?.title || '中等相关论文'}
摘要：${examples.medium_score?.abstract || ''}

评估结果：
\`\`\`json
{
  "total_score": ${examples.medium_score?.score || 60},
  "reason": "${examples.medium_score?.reason || '中等相关'}"
}
\`\`\`

### 示例3（低分论文）
标题：${examples.low_score?.title || '低相关论文'}
摘要：${examples.low_score?.abstract || ''}

评估结果：
\`\`\`json
{
  "total_score": ${examples.low_score?.score || 15},
  "reason": "${examples.low_score?.reason || '不相关'}"
}
\`\`\``

          await saveConfig('prompt_config', { llm_few_shot_examples: examplesText })
        }
      }

      // 标记配置完成
      const res = await completeSetup()
      const data = res.data
      if (data.success) {
        wizardOpen.value = false
        wizardStep.value = 1
        showToast('配置向导已完成！系统已就绪。')
      } else {
        showToast(data.message || '完成配置失败', 'error')
      }
    } catch (e) {
      showToast('完成配置失败', 'error')
    }
  }

  // 测试数据库连接
  const handleTestDBConnection = async () => {
    wizardTesting.value = true
    wizardTestResults.value.db = null
    try {
      const res = await apiTestDB(wizardData.value.db)
      const data = res.data
      wizardTestResults.value.db = data
      if (data.success) {
        showToast('数据库连接成功！')
      } else {
        showToast(data.message || '数据库连接失败', 'error')
      }
    } catch (e) {
      wizardTestResults.value.db = { success: false, message: '请求失败，请检查网络' }
      showToast('测试请求失败', 'error')
    } finally {
      wizardTesting.value = false
    }
  }

  // 测试LLM连接
  const handleTestLLMConnection = async () => {
    wizardTesting.value = true
    wizardTestResults.value.llm = null
    try {
      const res = await apiTestLLM(wizardData.value.llm)
      const data = res.data
      wizardTestResults.value.llm = data
      if (data.success) {
        showToast('LLM API 连接成功！')
      } else {
        showToast(data.message || 'LLM API 连接失败', 'error')
      }
    } catch (e) {
      wizardTestResults.value.llm = { success: false, message: '请求失败，请检查网络' }
      showToast('测试请求失败', 'error')
    } finally {
      wizardTesting.value = false
    }
  }

  // 测试通知渠道
  const handleTestNotifyChannel = async () => {
    wizardTesting.value = true
    wizardTestResults.value.notify = null
    try {
      const res = await apiTestNotify(wizardData.value.notify.channel, wizardData.value.notify.config)
      const data = res.data
      wizardTestResults.value.notify = data
      if (data.success) {
        showToast('通知测试成功！')
      } else {
        showToast(data.message || '通知测试失败', 'error')
      }
    } catch (e) {
      wizardTestResults.value.notify = { success: false, message: '请求失败，请检查网络' }
      showToast('测试请求失败', 'error')
    } finally {
      wizardTesting.value = false
    }
  }

  // ArXiv关键词管理
  const addArxivKeyword = (keyword) => {
    const kw = (keyword || wizardNewKeyword.value).trim()
    if (kw && !wizardData.value.arxiv.keywords.includes(kw)) {
      wizardData.value.arxiv.keywords.push(kw)
    }
    wizardNewKeyword.value = ''
  }

  const removeArxivKeyword = (index) => {
    wizardData.value.arxiv.keywords.splice(index, 1)
  }

  const toggleArxivCategory = (code) => {
    const idx = wizardData.value.arxiv.keywords.indexOf(code)
    if (idx >= 0) {
      wizardData.value.arxiv.keywords.splice(idx, 1)
    } else {
      wizardData.value.arxiv.keywords.push(code)
    }
  }

  // AI 生成研究方向
  const handleGenerateResearch = async () => {
    if (!researchBrief.value.trim()) return

    generatingResearch.value = true
    try {
      const res = await apiGenerateResearch(researchBrief.value)
      const data = res.data

      if (data.success) {
        wizardData.value.research = data.data.research_description
        aiGeneratedKeywords.value = data.data.arxiv_keywords || []
        aiGeneratedLlmConfig.value = data.data.llm_config || null
        if (aiGeneratedLlmConfig.value) {
          const anchors = aiGeneratedLlmConfig.value.scoring_anchors || {}
          const examples = aiGeneratedLlmConfig.value.few_shot_examples || {}

          const highAnchors = (anchors.high_score_keywords || []).join('\n')
          const mediumAnchors = (anchors.medium_score_keywords || []).join('\n')
          const lowAnchors = (anchors.low_score_keywords || []).join('\n')

          editableGeneratedConfig.value = {
            anchors: { high: highAnchors, medium: mediumAnchors, low: lowAnchors },
            examples: {
              high: {
                title: examples.high_score?.title || '',
                abstract: examples.high_score?.abstract || '',
                score: examples.high_score?.score || 90,
                reason: examples.high_score?.reason || ''
              },
              medium: {
                title: examples.medium_score?.title || '',
                abstract: examples.medium_score?.abstract || '',
                score: examples.medium_score?.score || 60,
                reason: examples.medium_score?.reason || ''
              },
              low: {
                title: examples.low_score?.title || '',
                abstract: examples.low_score?.abstract || '',
                score: examples.low_score?.score || 15,
                reason: examples.low_score?.reason || ''
              }
            }
          }

          nextTick(() => {
            const el = document.querySelector('[data-generated-config-section]')
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
          })
        }
        showToast('AI 已生成研究方向描述、锚点和评分示例！')
      } else {
        showToast(data.message || '生成失败', 'error')
      }
    } catch (e) {
      showToast('生成失败，请检查网络', 'error')
    } finally {
      generatingResearch.value = false
    }
  }

  const ensureNotifyChannelConfig = (channel) => {
    if (!wizardData.value.notify.config) {
      wizardData.value.notify.config = {}
    }
  }

  // 通过现有配置重新打开向导
  const reopenWizard = async () => {
    try {
      const { fetchAllConfig } = await import('@/api')
      const res = await fetchAllConfig()
      const data = res.data
      if (data.success) {
        const config = data.data
        if (config.mysql) {
          wizardData.value.db = {
            db_type: config.mysql.db_type || 'mysql',
            host: config.mysql.host || '',
            port: config.mysql.port || 3306,
            user: config.mysql.user || '',
            password: config.mysql.password || '',
            database: config.mysql.database || '',
            sqlite_path: config.mysql.sqlite_path || 'data/papers.db'
          }
        }
        if (config.research_description) {
          wizardData.value.research = config.research_description
        }
        if (config.llm_filter) {
          wizardData.value.llm = {
            api_key: config.llm_filter.api_key || '',
            base_url: config.llm_filter.base_url || '',
            model: config.llm_filter.model || ''
          }
        }
        if (config.arxiv && config.arxiv.keywords) {
          wizardData.value.arxiv.keywords = [...config.arxiv.keywords]
          wizardData.value.arxiv.max_results_per_keyword = config.arxiv.max_results_per_keyword || 100
        }
        if (config.notify) {
          wizardData.value.notify.channel = config.notify.active_channel || 'console'
          wizardData.value.notify.config = config.notify.channels?.[config.notify.active_channel] || {}
        }
      }
    } catch (e) {
      console.error('加载配置失败:', e)
    }
    wizardStep.value = 1
    wizardTestResults.value = { db: null, llm: null, notify: null }
    wizardOpen.value = true
  }

  return {
    // 状态
    wizardOpen,
    wizardStep,
    wizardTesting,
    wizardTestResults,
    existingConfig,
    configCheckDone,
    wizardData,
    wizardNewKeyword,
    researchBrief,
    generatingResearch,
    aiGeneratedKeywords,
    aiGeneratedLlmConfig,
    editableGeneratedConfig,

    // 静态数据
    wizardStepNames,
    arxivCategories,
    notifyChannelOptions,
    notifyChannelFields,

    // 方法
    openWizard,
    reopenWizard,
    resetWizardData,
    nextWizardStep,
    prevWizardStep,
    skipWizardStep,
    saveWizardStepData,
    completeWizard,
    handleTestDBConnection,
    handleTestLLMConnection,
    handleTestNotifyChannel,
    addArxivKeyword,
    removeArxivKeyword,
    toggleArxivCategory,
    handleGenerateResearch,
    ensureNotifyChannelConfig
  }
}
