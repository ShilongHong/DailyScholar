<template>
  <!-- 配置向导覆盖层 -->
  <div class="fixed inset-0 z-[60] bg-gray-900/80 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="bg-white rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col shadow-2xl">
      <!-- 向导头部 -->
      <div class="px-6 py-5 border-b border-gray-100 bg-gradient-to-r from-primary/5 to-secondary/5">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 bg-gradient-to-br from-primary to-secondary rounded-lg flex items-center justify-center text-white">
              <i class="ph ph-magic-wand text-lg"></i>
            </div>
            <h2 class="text-xl font-bold text-gray-900">系统配置向导</h2>
          </div>
          <span class="text-sm text-gray-500 bg-white px-3 py-1 rounded-full border border-gray-200">步骤 {{ wizardStep }} / 7</span>
        </div>
        <!-- 步骤指示器 -->
        <div class="flex mt-4 gap-1">
          <div v-for="n in 7" :key="n" class="flex-1 h-2 rounded-full transition-all duration-300"
            :class="n < wizardStep ? 'bg-green-400' : n === wizardStep ? 'bg-primary' : 'bg-gray-200'"></div>
        </div>
        <div class="flex mt-2 gap-1">
          <div v-for="(name, idx) in wizardStepNames" :key="idx" class="flex-1 text-center text-xs"
            :class="idx + 1 <= wizardStep ? 'text-primary font-medium' : 'text-gray-400'">
            {{ name }}
          </div>
        </div>
      </div>

      <!-- 向导内容区 -->
      <div class="flex-1 overflow-y-auto p-6">

        <!-- Step 1: 欢迎页 -->
        <div v-if="wizardStep === 1" class="text-center py-8 max-w-2xl mx-auto">
          <div class="w-20 h-20 bg-gradient-to-br from-primary to-secondary rounded-2xl flex items-center justify-center text-white mx-auto mb-6 shadow-lg shadow-primary/30">
            <i class="ph ph-book-open-text text-4xl"></i>
          </div>
          <h3 class="text-3xl font-bold text-gray-900 mb-4">欢迎使用 Paper2Data</h3>
          <p class="text-gray-600 text-lg mb-6 leading-relaxed">
            您的 AI 科研情报助手。本系统会自动从 ArXiv 获取论文，通过 LLM 智能筛选与您研究方向相关的论文，并推送到您常用的通知渠道。
          </p>

          <!-- 检测到已有配置提示 -->
          <div v-if="existingConfig && (existingConfig.has_mysql || existingConfig.has_llm || existingConfig.has_research)"
            class="bg-amber-50 border border-amber-200 rounded-xl p-5 mb-6 text-left">
            <div class="flex items-start gap-3">
              <i class="ph ph-warning-circle text-2xl text-amber-600 flex-shrink-0 mt-0.5"></i>
              <div class="flex-1">
                <h4 class="font-semibold text-amber-800 mb-2">检测到已有配置</h4>
                <div class="flex flex-wrap gap-2 mb-3">
                  <span v-if="existingConfig.has_mysql" class="inline-flex items-center gap-1 bg-amber-100 text-amber-700 px-2.5 py-1 rounded-full text-xs font-medium">
                    <i class="ph ph-database"></i> 数据库
                  </span>
                  <span v-if="existingConfig.has_llm" class="inline-flex items-center gap-1 bg-amber-100 text-amber-700 px-2.5 py-1 rounded-full text-xs font-medium">
                    <i class="ph ph-brain"></i> LLM
                  </span>
                  <span v-if="existingConfig.has_research" class="inline-flex items-center gap-1 bg-amber-100 text-amber-700 px-2.5 py-1 rounded-full text-xs font-medium">
                    <i class="ph ph-target"></i> 研究方向
                  </span>
                  <span v-if="existingConfig.has_notify" class="inline-flex items-center gap-1 bg-amber-100 text-amber-700 px-2.5 py-1 rounded-full text-xs font-medium">
                    <i class="ph ph-bell"></i> 通知
                  </span>
                </div>
                <div class="flex flex-col sm:flex-row gap-2">
                  <button @click="wizardStep = 7"
                    class="flex-1 px-4 py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors flex items-center justify-center gap-2">
                    <i class="ph ph-check-circle"></i> 使用现有配置
                  </button>
                  <button @click="wizardStep = 2"
                    class="flex-1 px-4 py-2.5 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors flex items-center justify-center gap-2">
                    <i class="ph ph-pencil-simple"></i> 查看并修改
                  </button>
                  <button @click="resetWizardData"
                    class="px-4 py-2.5 bg-white border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors">
                    清空重配
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-3 gap-4 mb-6">
            <div class="bg-blue-50 rounded-xl p-4 border border-blue-100">
              <i class="ph ph-download-simple text-2xl text-blue-600 mb-2"></i>
              <h4 class="font-semibold text-gray-800 text-sm">自动获取</h4>
              <p class="text-xs text-gray-500 mt-1">每日定时从 ArXiv 获取最新论文</p>
            </div>
            <div class="bg-purple-50 rounded-xl p-4 border border-purple-100">
              <i class="ph ph-brain text-2xl text-purple-600 mb-2"></i>
              <h4 class="font-semibold text-gray-800 text-sm">智能筛选</h4>
              <p class="text-xs text-gray-500 mt-1">LLM 评估论文与您研究的相关度</p>
            </div>
            <div class="bg-green-50 rounded-xl p-4 border border-green-100">
              <i class="ph ph-paper-plane-right text-2xl text-green-600 mb-2"></i>
              <h4 class="font-semibold text-gray-800 text-sm">即时推送</h4>
              <p class="text-xs text-gray-500 mt-1">推送到钉钉、飞书、Telegram 等</p>
            </div>
          </div>
          <p class="text-sm text-gray-400">接下来将引导您完成 6 个配置步骤，预计需要 3-5 分钟。</p>
        </div>

        <!-- Step 2: 数据库配置 -->
        <div v-if="wizardStep === 2" class="max-w-2xl mx-auto">
          <div class="flex items-center gap-3 mb-6">
            <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <i class="ph ph-database text-xl text-blue-600"></i>
            </div>
            <div>
              <h3 class="text-xl font-bold text-gray-900">数据库配置</h3>
              <p class="text-sm text-gray-500">选择数据库类型并配置连接信息</p>
            </div>
          </div>

          <!-- 数据库类型选择 -->
          <div class="mb-6">
            <label class="block text-sm font-medium text-gray-700 mb-3">数据库类型</label>
            <div class="grid grid-cols-2 gap-3">
              <button @click="wizardData.db.db_type = 'sqlite'; wizardTestResults.db = null;"
                :class="['p-4 border-2 rounded-xl flex items-center gap-3 transition-all',
                  wizardData.db.db_type === 'sqlite' ? 'border-green-500 bg-green-50' : 'border-gray-200 hover:border-gray-300']">
                <div class="w-10 h-10 rounded-lg flex items-center justify-center"
                  :class="wizardData.db.db_type === 'sqlite' ? 'bg-green-100' : 'bg-gray-100'">
                  <i class="ph ph-file-sql text-xl" :class="wizardData.db.db_type === 'sqlite' ? 'text-green-600' : 'text-gray-400'"></i>
                </div>
                <div class="text-left">
                  <div class="font-medium" :class="wizardData.db.db_type === 'sqlite' ? 'text-green-700' : 'text-gray-700'">SQLite</div>
                  <div class="text-xs text-gray-500">轻量级，无需安装</div>
                </div>
              </button>
              <button @click="wizardData.db.db_type = 'mysql'; wizardTestResults.db = null;"
                :class="['p-4 border-2 rounded-xl flex items-center gap-3 transition-all',
                  wizardData.db.db_type === 'mysql' ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300']">
                <div class="w-10 h-10 rounded-lg flex items-center justify-center"
                  :class="wizardData.db.db_type === 'mysql' ? 'bg-blue-100' : 'bg-gray-100'">
                  <i class="ph ph-database text-xl" :class="wizardData.db.db_type === 'mysql' ? 'text-blue-600' : 'text-gray-400'"></i>
                </div>
                <div class="text-left">
                  <div class="font-medium" :class="wizardData.db.db_type === 'mysql' ? 'text-blue-700' : 'text-gray-700'">MySQL</div>
                  <div class="text-xs text-gray-500">功能完整，适合生产</div>
                </div>
              </button>
            </div>
          </div>

          <!-- SQLite 配置（简化） -->
          <div v-if="wizardData.db.db_type === 'sqlite'" class="bg-green-50 rounded-lg p-4 mb-6">
            <div class="flex items-start gap-3">
              <i class="ph ph-check-circle text-green-600 text-lg mt-0.5"></i>
              <div>
                <p class="text-sm text-green-800 font-medium">SQLite 模式</p>
                <p class="text-xs text-green-600 mt-1">数据将存储在本地文件 <code class="bg-green-100 px-1 rounded">{{ wizardData.db.sqlite_path || 'data/papers.db' }}</code>，无需额外配置</p>
              </div>
            </div>
          </div>

          <!-- MySQL 配置 -->
          <div v-if="wizardData.db.db_type === 'mysql'" class="space-y-4">
            <div class="grid grid-cols-3 gap-4">
              <div class="col-span-2">
                <label class="block text-sm font-medium text-gray-700 mb-1">主机地址</label>
                <input type="text" v-model="wizardData.db.host" placeholder="例如: localhost 或 192.168.1.100"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm">
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">端口</label>
                <input type="number" v-model="wizardData.db.port" placeholder="3306"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm">
              </div>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">用户名</label>
                <input type="text" v-model="wizardData.db.user" placeholder="例如: root"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm">
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">密码</label>
                <input type="password" v-model="wizardData.db.password" placeholder="例如: your-password"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm">
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">数据库名称</label>
              <input type="text" v-model="wizardData.db.database" placeholder="例如: dailyscholar"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm">
            </div>
            <div class="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-xs text-blue-700">
              示例填写：主机填 localhost，端口填 3306，用户名常见为 root，数据库名可用 dailyscholar。
            </div>
          </div>

          <!-- 测试连接按钮（仅 MySQL 模式显示） -->
          <div v-if="wizardData.db.db_type === 'mysql'" class="mt-6 flex items-center gap-4">
            <button @click="handleTestDBConnection" :disabled="wizardTesting"
              class="px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center gap-2">
              <i :class="wizardTesting ? 'ph ph-spinner animate-spin' : 'ph ph-plugs-connected'" class="text-lg"></i>
              {{ wizardTesting ? '测试中...' : '测试连接' }}
            </button>
            <div v-if="wizardTestResults.db" class="flex items-center gap-2 text-sm">
              <i :class="wizardTestResults.db.success ? 'ph-fill ph-check-circle text-green-500' : 'ph-fill ph-x-circle text-red-500'" class="text-lg"></i>
              <span :class="wizardTestResults.db.success ? 'text-green-700' : 'text-red-700'">
                {{ wizardTestResults.db.message || (wizardTestResults.db.success ? '连接成功' : '连接失败') }}
              </span>
            </div>
          </div>

          <!-- SQLite 就绪提示 -->
          <div v-if="wizardData.db.db_type === 'sqlite'" class="mt-6 flex items-center gap-2 text-sm text-green-700">
            <i class="ph-fill ph-check-circle text-green-500 text-lg"></i>
            <span>SQLite 已就绪，无需测试连接</span>
          </div>

          <div class="mt-6 p-4 bg-amber-50 rounded-lg border border-amber-200">
            <div class="flex items-start gap-2">
              <i class="ph ph-info text-amber-600 text-lg mt-0.5"></i>
              <div class="text-sm text-amber-800">
                <p class="font-medium mb-1">提示</p>
                <p v-if="wizardData.db.db_type === 'sqlite'">SQLite 适合个人使用和小规模部署，数据存储在本地文件中，开箱即用。</p>
                <p v-else>如果暂时没有数据库，可以点击"跳过"继续配置其他项，或切换到 SQLite 模式。</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Step 3: LLM 配置 -->
        <div v-if="wizardStep === 3" class="max-w-2xl mx-auto">
          <div class="flex items-center gap-3 mb-6">
            <div class="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <i class="ph ph-brain text-xl text-green-600"></i>
            </div>
            <div>
              <h3 class="text-xl font-bold text-gray-900">LLM 配置</h3>
              <p class="text-sm text-gray-500">配置用于论文筛选和翻译的大语言模型 API</p>
            </div>
          </div>

          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">API Key</label>
              <input type="password" v-model="wizardData.llm.api_key" placeholder="例如: sk-xxxxxxxxxxxxxxxx"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm">
              <p class="mt-1 text-xs text-gray-400">支持 OpenAI 兼容的 API（如 OpenAI、DeepSeek、SiliconFlow 等）</p>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Base URL</label>
              <input type="text" v-model="wizardData.llm.base_url" placeholder="https://api.openai.com/v1"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">模型名称</label>
              <input type="text" v-model="wizardData.llm.model" placeholder="例如: gpt-4o-mini 或 deepseek-chat"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm">
            </div>
            <div class="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-xs text-green-700">
              示例填写：OpenAI 可用 https://api.openai.com/v1 + gpt-4o-mini，DeepSeek 可用 https://api.deepseek.com/v1 + deepseek-chat。
            </div>
          </div>

          <!-- 测试API按钮 -->
          <div class="mt-6 flex items-center gap-4">
            <button @click="handleTestLLMConnection" :disabled="wizardTesting"
              class="px-5 py-2.5 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors flex items-center gap-2">
              <i :class="wizardTesting ? 'ph ph-spinner animate-spin' : 'ph ph-flask'" class="text-lg"></i>
              {{ wizardTesting ? '测试中...' : '测试 API' }}
            </button>
            <div v-if="wizardTestResults.llm" class="flex items-center gap-2 text-sm">
              <i :class="wizardTestResults.llm.success ? 'ph-fill ph-check-circle text-green-500' : 'ph-fill ph-x-circle text-red-500'" class="text-lg"></i>
              <span :class="wizardTestResults.llm.success ? 'text-green-700' : 'text-red-700'">
                {{ wizardTestResults.llm.message || (wizardTestResults.llm.success ? 'API 连接成功' : 'API 连接失败') }}
              </span>
            </div>
          </div>
        </div>

        <!-- Step 4: 研究方向 + AI 生成 -->
        <div v-if="wizardStep === 4" class="max-w-2xl mx-auto">
          <div class="flex items-center gap-3 mb-6">
            <div class="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <i class="ph ph-target text-xl text-purple-600"></i>
            </div>
            <div>
              <h3 class="text-xl font-bold text-gray-900">研究方向</h3>
              <p class="text-sm text-gray-500">描述您的研究领域，帮助AI筛选相关论文</p>
            </div>
          </div>

          <div class="bg-gradient-to-r from-purple-50 to-blue-50 rounded-xl p-5 mb-6 border border-purple-100">
            <label class="block text-sm font-medium text-gray-700 mb-2">
              <i class="ph ph-magic-wand text-purple-600"></i> 一句话描述您的研究方向
            </label>
            <div class="flex gap-2">
              <input type="text" v-model="researchBrief"
                placeholder="例如：我的研究方向是多模态大模型在医疗影像中的应用"
                class="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 text-sm">
              <button @click="handleGenerateResearch" :disabled="generatingResearch || !researchBrief"
                class="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-sm whitespace-nowrap">
                <i class="ph ph-sparkle"></i>
                <span v-if="generatingResearch">生成中...</span>
                <span v-else>AI 生成</span>
              </button>
            </div>
            <p class="text-xs text-gray-500 mt-2">示例：我的研究方向是多模态大模型在医疗影像中的应用。AI 会据此生成详细描述和推荐关键词。</p>
          </div>

          <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-1">研究方向详细描述</label>
            <textarea v-model="wizardData.research" rows="8"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm"
              placeholder="示例：&#10;1. 我关注多模态大模型、医学影像分析与报告生成。&#10;2. 重点跟踪视觉语言模型、检索增强与可靠性评估。&#10;3. 更关注可迁移方法，而不是只在单一数据集刷榜。"></textarea>
            <p class="text-xs text-gray-500 mt-1">描述越具体，AI 筛选越准确</p>
          </div>

          <div v-if="aiGeneratedKeywords.length > 0" class="bg-green-50 rounded-lg p-4 border border-green-200 mb-4">
            <div class="flex items-center gap-2 mb-2">
              <i class="ph ph-lightning text-green-600"></i>
              <span class="text-sm font-medium text-green-800">AI 推荐的 ArXiv 分类</span>
            </div>
            <div class="flex flex-wrap gap-2">
              <span v-for="kw in aiGeneratedKeywords" :key="kw"
                class="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium">
                {{ kw }}
              </span>
            </div>
            <p class="text-xs text-gray-500 mt-2">这些关键词将在下一步自动填入</p>
          </div>

          <div v-if="aiGeneratedLlmConfig && editableGeneratedConfig && editableGeneratedConfig.anchors && editableGeneratedConfig.examples" class="space-y-4" data-generated-config-section>
            <div class="bg-purple-50 rounded-xl p-5 border border-purple-200">
              <div class="flex items-center gap-2 mb-4">
                <i class="ph ph-sparkle text-purple-600"></i>
                <h4 class="text-sm font-semibold text-purple-900">AI 生成的筛选锚点（可编辑）</h4>
              </div>

              <div class="grid grid-cols-1 gap-4">
                <div class="bg-white rounded-lg p-4 border border-purple-100">
                  <div class="flex items-center gap-2 mb-2">
                    <i class="ph ph-trend-up text-green-600"></i>
                    <span class="text-sm font-medium text-gray-800">高分关键词</span>
                  </div>
                  <textarea v-model="editableGeneratedConfig.anchors.high" rows="4"
                    class="w-full px-3 py-2 border border-green-200 rounded-lg focus:ring-2 focus:ring-green-500/30 focus:border-green-400 text-sm"
                    placeholder="每行一个高分关键词，例如：&#10;multimodal medical imaging&#10;vision language model&#10;radiology report generation"></textarea>
                  <p class="text-xs text-gray-500 mt-1">每行一个关键词，匹配这些内容的论文会获得更高分。</p>
                </div>

                <div class="bg-white rounded-lg p-4 border border-purple-100">
                  <div class="flex items-center gap-2 mb-2">
                    <i class="ph ph-minus text-amber-600"></i>
                    <span class="text-sm font-medium text-gray-800">中等分数信号</span>
                  </div>
                  <textarea v-model="editableGeneratedConfig.anchors.medium" rows="3"
                    class="w-full px-3 py-2 border border-amber-200 rounded-lg focus:ring-2 focus:ring-amber-500/30 focus:border-amber-400 text-sm"
                    placeholder="每行一个中等分数信号，例如：&#10;retrieval augmented generation&#10;weakly supervised learning&#10;clinical benchmark"></textarea>
                </div>

                <div class="bg-white rounded-lg p-4 border border-purple-100">
                  <div class="flex items-center gap-2 mb-2">
                    <i class="ph ph-trend-down text-red-600"></i>
                    <span class="text-sm font-medium text-gray-800">低分/排除关键词</span>
                  </div>
                  <textarea v-model="editableGeneratedConfig.anchors.low" rows="3"
                    class="w-full px-3 py-2 border border-red-200 rounded-lg focus:ring-2 focus:ring-red-500/30 focus:border-red-400 text-sm"
                    placeholder="每行一个低分或排除关键词，例如：&#10;general social media analysis&#10;recommendation system&#10;non-medical sentiment analysis"></textarea>
                </div>
              </div>
            </div>

            <div class="bg-blue-50 rounded-xl p-5 border border-blue-200">
              <div class="flex items-center gap-2 mb-4">
                <i class="ph ph-brain text-blue-600"></i>
                <h4 class="text-sm font-semibold text-blue-900">AI 生成的评分示例（Few-shot，可编辑）</h4>
              </div>

              <div class="space-y-3">
                <div class="bg-white rounded-lg p-4 border border-blue-100" v-if="aiGeneratedLlmConfig.few_shot_examples?.high_score">
                  <div class="flex items-center gap-2 mb-2">
                    <i class="ph ph-star text-green-600"></i>
                    <span class="text-sm font-medium text-gray-800">高分示例</span>
                    <input type="number" v-model="editableGeneratedConfig.examples.high.score" min="0" max="100"
                      class="w-20 px-2 py-1 text-xs border border-green-200 rounded bg-green-50 text-green-700">
                  </div>
                  <input type="text" v-model="editableGeneratedConfig.examples.high.title"
                    class="w-full px-3 py-2 mb-2 border border-gray-200 rounded-lg text-sm" placeholder="例如：A Vision-Language Model for Radiology Report Generation">
                  <textarea v-model="editableGeneratedConfig.examples.high.abstract" rows="3"
                    class="w-full px-3 py-2 mb-2 border border-gray-200 rounded-lg text-sm" placeholder="示例摘要：提出面向胸片报告生成的视觉语言模型，并评估其临床可用性。"></textarea>
                  <textarea v-model="editableGeneratedConfig.examples.high.reason" rows="2"
                    class="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" placeholder="示例原因：任务、方法和评估目标都与研究方向高度一致。"></textarea>
                </div>

                <div class="bg-white rounded-lg p-4 border border-blue-100" v-if="aiGeneratedLlmConfig.few_shot_examples?.medium_score">
                  <div class="flex items-center gap-2 mb-2">
                    <i class="ph ph-star-half text-amber-600"></i>
                    <span class="text-sm font-medium text-gray-800">中等分示例</span>
                    <input type="number" v-model="editableGeneratedConfig.examples.medium.score" min="0" max="100"
                      class="w-20 px-2 py-1 text-xs border border-amber-200 rounded bg-amber-50 text-amber-700">
                  </div>
                  <input type="text" v-model="editableGeneratedConfig.examples.medium.title"
                    class="w-full px-3 py-2 mb-2 border border-gray-200 rounded-lg text-sm" placeholder="例如：Retrieval-Augmented Clinical QA with Lightweight Adaptation">
                  <textarea v-model="editableGeneratedConfig.examples.medium.abstract" rows="3"
                    class="w-full px-3 py-2 mb-2 border border-gray-200 rounded-lg text-sm" placeholder="示例摘要：结合检索增强与轻量适配提升临床问答效果，但与核心任务并非完全重合。"></textarea>
                  <textarea v-model="editableGeneratedConfig.examples.medium.reason" rows="2"
                    class="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" placeholder="示例原因：方法相关但研究问题不是当前最核心关注点。"></textarea>
                </div>

                <div class="bg-white rounded-lg p-4 border border-blue-100" v-if="aiGeneratedLlmConfig.few_shot_examples?.low_score">
                  <div class="flex items-center gap-2 mb-2">
                    <i class="ph ph-star text-red-600"></i>
                    <span class="text-sm font-medium text-gray-800">低分示例</span>
                    <input type="number" v-model="editableGeneratedConfig.examples.low.score" min="0" max="100"
                      class="w-20 px-2 py-1 text-xs border border-red-200 rounded bg-red-50 text-red-700">
                  </div>
                  <input type="text" v-model="editableGeneratedConfig.examples.low.title"
                    class="w-full px-3 py-2 mb-2 border border-gray-200 rounded-lg text-sm" placeholder="例如：Sentiment Analysis for Social Media Posts">
                  <textarea v-model="editableGeneratedConfig.examples.low.abstract" rows="3"
                    class="w-full px-3 py-2 mb-2 border border-gray-200 rounded-lg text-sm" placeholder="示例摘要：研究社交媒体文本情感分类，与当前研究主题关联较弱。"></textarea>
                  <textarea v-model="editableGeneratedConfig.examples.low.reason" rows="2"
                    class="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" placeholder="示例原因：场景和技术路线都偏离当前研究重点。"></textarea>
                </div>
              </div>

              <p class="text-xs text-blue-700 mt-3">这些配置会在完成向导时自动保存到提示词配置中，后续也可以在"系统配置"里继续查看和修改。</p>
            </div>
          </div>
        </div>

        <!-- Step 5: ArXiv 搜索配置 -->
        <div v-if="wizardStep === 5" class="max-w-2xl mx-auto">
          <div class="flex items-center gap-3 mb-6">
            <div class="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
              <i class="ph ph-magnifying-glass text-xl text-orange-600"></i>
            </div>
            <div>
              <h3 class="text-xl font-bold text-gray-900">ArXiv 搜索配置</h3>
              <p class="text-sm text-gray-500">选择要关注的 ArXiv 分类和关键词</p>
            </div>
          </div>

          <!-- 常用分类快速选择 -->
          <div class="mb-6">
            <label class="block text-sm font-medium text-gray-700 mb-3">常用分类（点击切换）</label>
            <div class="flex flex-wrap gap-2">
              <button v-for="cat in arxivCategories" :key="cat.code"
                @click="toggleArxivCategory(cat.code)"
                :class="['px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors',
                  wizardData.arxiv.keywords.includes(cat.code)
                    ? 'bg-primary text-white border-primary'
                    : 'bg-white text-gray-600 border-gray-300 hover:border-primary hover:text-primary']">
                {{ cat.code }} <span class="opacity-70">{{ cat.name }}</span>
              </button>
            </div>
          </div>

          <!-- 已选关键词 -->
          <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">已选关键词/分类</label>
            <div class="flex flex-wrap gap-2 min-h-[40px] p-3 bg-gray-50 rounded-lg border border-gray-200">
              <span v-for="(kw, idx) in wizardData.arxiv.keywords" :key="idx"
                class="inline-flex items-center gap-1 px-2.5 py-1 bg-primary/10 text-primary text-sm rounded-full">
                {{ kw }}
                <button @click="removeArxivKeyword(idx)" class="hover:text-red-500 transition-colors">
                  <i class="ph ph-x text-xs"></i>
                </button>
              </span>
              <span v-if="wizardData.arxiv.keywords.length === 0" class="text-sm text-gray-400">暂无关键词，请从上方选择或手动添加</span>
            </div>
          </div>

          <!-- 自定义关键词输入 -->
          <div class="flex gap-2 mb-6">
            <input type="text" v-model="wizardNewKeyword" @keyup.enter="addArxivKeyword()" placeholder="例如: cs.CL、cat:cs.AI、large language model"
              class="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm">
            <button @click="addArxivKeyword()" class="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors">
              <i class="ph ph-plus"></i> 添加
            </button>
          </div>
          <p class="mb-6 text-xs text-gray-500">示例填写：既可以填 ArXiv 分类如 cs.CL、cs.AI，也可以填 cat:cs.LG 或 large language model 这类检索关键词。</p>

          <!-- 每个关键词最大结果数 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">每个关键词最大结果数</label>
            <input type="number" v-model="wizardData.arxiv.max_results_per_keyword" min="10" max="500" placeholder="100"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm">
            <p class="mt-1 text-xs text-gray-400">建议 50-200，过大会增加获取时间</p>
          </div>
        </div>

        <!-- Step 6: 通知渠道配置 -->
        <div v-if="wizardStep === 6" class="max-w-2xl mx-auto">
          <div class="flex items-center gap-3 mb-6">
            <div class="w-10 h-10 bg-pink-100 rounded-lg flex items-center justify-center">
              <i class="ph ph-bell-ringing text-xl text-pink-600"></i>
            </div>
            <div>
              <h3 class="text-xl font-bold text-gray-900">通知渠道配置</h3>
              <p class="text-sm text-gray-500">选择论文推送的通知方式</p>
            </div>
          </div>

          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">选择通知渠道</label>
              <select v-model="wizardData.notify.channel" @change="wizardData.notify.config = {}; wizardTestResults.notify = null;"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm">
                <option v-for="opt in notifyChannelOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </div>

            <!-- Console无需配置 -->
            <div v-if="wizardData.notify.channel === 'console'" class="p-4 bg-gray-50 rounded-lg border border-gray-200">
              <div class="flex items-center gap-2 text-sm text-gray-600">
                <i class="ph ph-terminal-window text-lg"></i>
                <span>控制台模式无需额外配置，论文信息将输出到服务器日志中。适合开发调试使用。</span>
              </div>
            </div>

            <!-- 动态渠道配置表单 -->
            <div v-if="wizardData.notify.channel !== 'console' && notifyChannelFields[wizardData.notify.channel]"
              class="p-4 bg-gray-50 rounded-lg border border-gray-200 space-y-4">
              <div v-for="field in notifyChannelFields[wizardData.notify.channel]" :key="field.key">
                <label class="block text-sm font-medium text-gray-700 mb-1">
                  {{ field.label }}
                  <span v-if="field.required" class="text-red-500">*</span>
                </label>
                <input :type="field.type || 'text'" v-model="wizardData.notify.config[field.key]"
                  :placeholder="field.placeholder || (field.required ? '必填' : '选填')"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm">
                <p v-if="field.help" class="mt-1 text-xs text-gray-500">{{ field.help }}</p>
              </div>
            </div>
          </div>

          <!-- 测试通知按钮 -->
          <div class="mt-6 flex items-center gap-4">
            <button @click="handleTestNotifyChannel" :disabled="wizardTesting"
              class="px-5 py-2.5 bg-pink-600 text-white rounded-lg text-sm font-medium hover:bg-pink-700 disabled:opacity-50 transition-colors flex items-center gap-2">
              <i :class="wizardTesting ? 'ph ph-spinner animate-spin' : 'ph ph-paper-plane-right'" class="text-lg"></i>
              {{ wizardTesting ? '测试中...' : '测试通知' }}
            </button>
            <div v-if="wizardTestResults.notify" class="flex items-center gap-2 text-sm">
              <i :class="wizardTestResults.notify.success ? 'ph-fill ph-check-circle text-green-500' : 'ph-fill ph-x-circle text-red-500'" class="text-lg"></i>
              <span :class="wizardTestResults.notify.success ? 'text-green-700' : 'text-red-700'">
                {{ wizardTestResults.notify.message || (wizardTestResults.notify.success ? '通知测试成功' : '通知测试失败') }}
              </span>
            </div>
          </div>
        </div>

        <!-- Step 7: 配置摘要 & 完成 -->
        <div v-if="wizardStep === 7" class="max-w-2xl mx-auto">
          <div class="flex items-center gap-3 mb-6">
            <div class="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
              <i class="ph ph-check-circle text-xl text-emerald-600"></i>
            </div>
            <div>
              <h3 class="text-xl font-bold text-gray-900">配置完成</h3>
              <p class="text-sm text-gray-500">请确认以下配置信息</p>
            </div>
          </div>

          <div class="space-y-4">
            <!-- 数据库摘要 -->
            <div class="p-4 bg-gray-50 rounded-lg border border-gray-200">
              <div class="flex items-center justify-between mb-2">
                <h4 class="font-medium text-gray-800 flex items-center gap-2">
                  <i class="ph ph-database text-blue-600"></i> 数据库
                </h4>
                <span v-if="wizardData.db.db_type === 'sqlite' || (wizardTestResults.db && wizardTestResults.db.success)" class="text-xs text-green-600 flex items-center gap-1">
                  <i class="ph-fill ph-check-circle"></i> {{ wizardData.db.db_type === 'sqlite' ? '已就绪' : '已验证' }}
                </span>
              </div>
              <p class="text-sm text-gray-600" v-if="wizardData.db.db_type === 'sqlite'">
                SQLite 模式 - {{ wizardData.db.sqlite_path || 'data/papers.db' }}
              </p>
              <p class="text-sm text-gray-600" v-else-if="wizardData.db.host">
                {{ wizardData.db.host }}:{{ wizardData.db.port }} / {{ wizardData.db.database }}（{{ wizardData.db.user }}）
              </p>
              <p class="text-sm text-gray-400" v-else>未配置</p>
            </div>

            <!-- 研究方向摘要 -->
            <div class="p-4 bg-gray-50 rounded-lg border border-gray-200">
              <h4 class="font-medium text-gray-800 flex items-center gap-2 mb-2">
                <i class="ph ph-compass text-purple-600"></i> 研究方向
              </h4>
              <p class="text-sm text-gray-600 line-clamp-3" v-if="wizardData.research">{{ wizardData.research }}</p>
              <p class="text-sm text-gray-400" v-else>未配置</p>
            </div>

            <!-- LLM 摘要 -->
            <div class="p-4 bg-gray-50 rounded-lg border border-gray-200">
              <div class="flex items-center justify-between mb-2">
                <h4 class="font-medium text-gray-800 flex items-center gap-2">
                  <i class="ph ph-brain text-green-600"></i> LLM 配置
                </h4>
                <span v-if="wizardTestResults.llm && wizardTestResults.llm.success" class="text-xs text-green-600 flex items-center gap-1">
                  <i class="ph-fill ph-check-circle"></i> 已验证
                </span>
              </div>
              <p class="text-sm text-gray-600" v-if="wizardData.llm.model">
                模型: {{ wizardData.llm.model }} | Base URL: {{ wizardData.llm.base_url || '默认' }} | API Key: {{ wizardData.llm.api_key ? '****' + wizardData.llm.api_key.slice(-4) : '未设置' }}
              </p>
              <p class="text-sm text-gray-400" v-else>未配置</p>
            </div>

            <!-- ArXiv 摘要 -->
            <div class="p-4 bg-gray-50 rounded-lg border border-gray-200">
              <h4 class="font-medium text-gray-800 flex items-center gap-2 mb-2">
                <i class="ph ph-magnifying-glass text-orange-600"></i> ArXiv 搜索
              </h4>
              <div v-if="wizardData.arxiv.keywords.length > 0" class="flex flex-wrap gap-1.5">
                <span v-for="kw in wizardData.arxiv.keywords" :key="kw"
                  class="px-2 py-0.5 bg-orange-100 text-orange-700 text-xs rounded-full">{{ kw }}</span>
              </div>
              <p class="text-sm text-gray-400" v-else>未配置</p>
            </div>

            <!-- 通知渠道摘要 -->
            <div class="p-4 bg-gray-50 rounded-lg border border-gray-200">
              <div class="flex items-center justify-between mb-2">
                <h4 class="font-medium text-gray-800 flex items-center gap-2">
                  <i class="ph ph-bell-ringing text-pink-600"></i> 通知渠道
                </h4>
                <span v-if="wizardTestResults.notify && wizardTestResults.notify.success" class="text-xs text-green-600 flex items-center gap-1">
                  <i class="ph-fill ph-check-circle"></i> 已验证
                </span>
              </div>
              <p class="text-sm text-gray-600">
                {{ notifyChannelOptions.find(o => o.value === wizardData.notify.channel)?.label || wizardData.notify.channel }}
              </p>
            </div>
          </div>

          <!-- AI 筛选配置预览 -->
          <div v-if="aiGeneratedLlmConfig" class="mt-4 p-4 bg-purple-50 rounded-lg border border-purple-200">
            <div class="flex items-center gap-2 mb-3">
              <i class="ph ph-sparkle text-purple-600"></i>
              <span class="font-medium text-purple-800">AI 生成的筛选配置</span>
            </div>

            <!-- 评分锚点 -->
            <div class="space-y-3 text-sm">
              <!-- 高分关键词 -->
              <div class="bg-white rounded-lg p-3 border border-purple-100">
                <div class="flex items-center justify-between mb-2">
                  <span class="font-medium text-gray-700 flex items-center gap-1">
                    <i class="ph ph-trend-up text-green-500"></i> 高分关键词 (20-25分)
                  </span>
                  <span class="text-xs text-gray-400">{{ (aiGeneratedLlmConfig.scoring_anchors?.high_score_keywords || []).length }} 个</span>
                </div>
                <div class="text-gray-600 text-xs leading-relaxed max-h-20 overflow-y-auto">
                  {{ (aiGeneratedLlmConfig.scoring_anchors?.high_score_keywords || []).join(', ') }}
                </div>
              </div>

              <!-- 中等分数信号 -->
              <div class="bg-white rounded-lg p-3 border border-purple-100">
                <div class="flex items-center justify-between mb-2">
                  <span class="font-medium text-gray-700 flex items-center gap-1">
                    <i class="ph ph-minus text-yellow-500"></i> 中等分数信号 (10-19分)
                  </span>
                  <span class="text-xs text-gray-400">{{ (aiGeneratedLlmConfig.scoring_anchors?.medium_score_signals || []).length }} 个</span>
                </div>
                <div class="text-gray-600 text-xs leading-relaxed max-h-16 overflow-y-auto">
                  {{ (aiGeneratedLlmConfig.scoring_anchors?.medium_score_signals || []).join(', ') }}
                </div>
              </div>

              <!-- 低分/排除关键词 -->
              <div class="bg-white rounded-lg p-3 border border-purple-100">
                <div class="flex items-center justify-between mb-2">
                  <span class="font-medium text-gray-700 flex items-center gap-1">
                    <i class="ph ph-trend-down text-red-500"></i> 低分/排除关键词 (0-9分)
                  </span>
                  <span class="text-xs text-gray-400">{{ (aiGeneratedLlmConfig.scoring_anchors?.low_score_keywords || []).length }} 个</span>
                </div>
                <div class="text-gray-600 text-xs leading-relaxed max-h-16 overflow-y-auto">
                  {{ (aiGeneratedLlmConfig.scoring_anchors?.low_score_keywords || []).join(', ') }}
                </div>
              </div>

              <!-- 建议筛选阈值 -->
              <div class="flex justify-between items-center bg-white rounded-lg p-3 border border-purple-100">
                <span class="font-medium text-gray-700">建议筛选阈值</span>
                <span class="font-bold text-purple-700 bg-purple-100 px-3 py-1 rounded-full">{{ aiGeneratedLlmConfig.suggested_min_score || 60 }}分</span>
              </div>

              <!-- Few-shot 示例提示 -->
              <div class="bg-blue-50 rounded-lg p-3 border border-blue-200">
                <div class="flex items-center gap-2 mb-1">
                  <i class="ph ph-lightbulb text-blue-600"></i>
                  <span class="font-medium text-blue-800">评分示例已生成</span>
                </div>
                <p class="text-xs text-blue-600">
                  AI 已生成 {{ (aiGeneratedLlmConfig.few_shot_examples || []).length }} 个评分示例（高分/中等/低分各一个），用于指导 LLM 评分。
                  <span class="text-blue-800 font-medium">您可以在"系统配置"页面的"研究方向"标签中查看和编辑完整配置。</span>
                </p>
              </div>
            </div>
          </div>

          <div class="mt-6 p-4 bg-emerald-50 rounded-lg border border-emerald-200">
            <div class="flex items-start gap-2">
              <i class="ph ph-rocket-launch text-emerald-600 text-lg mt-0.5"></i>
              <div class="text-sm text-emerald-800">
                <p class="font-medium mb-1">准备就绪！</p>
                <p>点击"完成配置"后，系统将开始按照您的设置自动运行。您可以随时在"系统配置"页面修改任何设置。</p>
              </div>
            </div>
          </div>
        </div>

      </div>

      <!-- 向导底部按钮 -->
      <div class="px-6 py-4 border-t border-gray-100 bg-gray-50 flex items-center justify-between">
        <div>
          <button v-if="wizardStep > 1" @click="prevWizardStep"
            class="px-4 py-2 text-gray-600 bg-white border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors flex items-center gap-2">
            <i class="ph ph-arrow-left"></i> 上一步
          </button>
        </div>
        <div class="flex items-center gap-3">
          <button v-if="wizardStep > 1 && wizardStep < 7" @click="skipWizardStep"
            class="px-4 py-2 text-gray-500 text-sm hover:text-gray-700 transition-colors">
            跳过
          </button>
          <button @click="handleNextWizardStep"
            :class="['px-6 py-2.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 shadow-sm',
              wizardStep === 7
                ? 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-emerald-600/30'
                : 'bg-primary text-white hover:bg-primary/90 shadow-primary/30']">
            <span v-if="wizardStep === 1">开始配置 <i class="ph ph-arrow-right"></i></span>
            <span v-else-if="wizardStep === 7"><i class="ph ph-check"></i> 完成配置</span>
            <span v-else>下一步 <i class="ph ph-arrow-right"></i></span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useWizard } from '@/composables/useWizard'

const emit = defineEmits(['close'])

const {
  // 向导显示状态（由 composable 统一管理）
  wizardOpen,

  // 向导步骤状态
  wizardStep,
  wizardTesting,
  wizardTestResults,
  existingConfig,
  configCheckDone,

  // 表单数据
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
  ensureNotifyChannelConfig,
  openWizard,
  reopenWizard
} = useWizard()

const handleNextWizardStep = async () => {
  const completed = await nextWizardStep()
  if (completed) {
    emit('close')
  }
}
</script>
