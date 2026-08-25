<template>
  <div class="pb-10">
    <!-- 重新运行向导按钮 -->
    <div class="mb-4 flex justify-end">
      <button
        @click="$emit('open-wizard')"
        type="button"
        class="min-h-11 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 text-sm"
      >
        <i class="ph ph-arrows-clockwise"></i>
        重新运行配置向导
      </button>
    </div>

    <div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
      <div class="border-b border-gray-100">
        <nav class="flex -mb-px overflow-x-auto" aria-label="配置分类">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            @click="activeTab = tab.key"
            type="button"
            :aria-pressed="activeTab === tab.key"
            :class="['shrink-0 px-6 py-4 text-sm font-medium border-b-2 transition-colors',
              activeTab === tab.key ? 'border-primary text-primary' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300']"
          >
            {{ tab.label }}
          </button>
        </nav>
      </div>

      <div class="p-4 md:p-6" v-if="configData">
        <!-- ==================== Tab 1: LLM 筛选 ==================== -->
        <div v-if="activeTab === 'llm_filter'" class="space-y-6">
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <h3 class="text-lg font-medium text-gray-900">LLM 筛选设置</h3>
            <label class="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" v-model="configData.llm_filter.enable" class="sr-only peer">
              <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/30 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
              <span class="ml-3 text-sm font-medium text-gray-700">启用筛选</span>
            </label>
          </div>

          <div class="grid grid-cols-1 gap-6">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">API Key</label>
              <input type="password" v-model="configData.llm_filter.api_key" placeholder="例如: sk-xxxxxxxxxxxxxxxx"
                class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
              <p class="mt-1 text-xs text-gray-500">示例：填写 OpenAI、DeepSeek、SiliconFlow 等兼容服务提供的 API Key。</p>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Base URL</label>
              <input type="text" v-model="configData.llm_filter.base_url" placeholder="例如: https://api.openai.com/v1"
                class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
              <p class="mt-1 text-xs text-gray-500">示例：OpenAI 用 https://api.openai.com/v1，DeepSeek 用 https://api.deepseek.com/v1。</p>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">模型名称</label>
                <input type="text" v-model="configData.llm_filter.model" placeholder="例如: gpt-4o-mini 或 deepseek-chat"
                  class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">并行线程数</label>
                <input type="number" min="1" max="32" v-model="configData.llm_filter.max_workers"
                  class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
                <p class="mt-1 text-xs text-gray-500">建议8-16，过高可能被限流</p>
              </div>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">最低分数要求 (0-100)</label>
                <input type="number" min="0" max="100" v-model="configData.llm_filter.min_score"
                  class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
                <p class="mt-1 text-xs text-gray-500">100分制，60分及格</p>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Temperature</label>
                <input type="number" min="0" max="2" step="0.1" v-model="configData.llm_filter.temperature"
                  class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
                <p class="mt-1 text-xs text-gray-500">0-2，越低越稳定</p>
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Max Tokens</label>
              <input type="number" min="256" max="8192" v-model="configData.llm_filter.max_tokens" placeholder="例如: 2048"
                class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
            </div>

            <!-- 提示词编辑区 -->
            <div class="border-t border-gray-200 pt-6 space-y-4">
              <div class="flex items-center justify-between">
                <div>
                  <h4 class="text-base font-medium text-gray-900">筛选提示词</h4>
                  <p class="text-sm text-gray-500 mt-1">这些提示词会直接影响论文筛选结果，可查看、编辑并立即生效。</p>
                </div>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">系统提示词</label>
                <textarea v-model="configData.prompt_config.llm_system_prompt" rows="5"
                  class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50 font-mono text-sm"></textarea>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">评估模板</label>
                <textarea v-model="configData.prompt_config.llm_evaluation_template" rows="12"
                  class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50 font-mono text-sm"></textarea>
              </div>
            </div>
          </div>

          <div class="flex flex-col sm:flex-row sm:justify-end gap-3 pt-4">
            <button type="button" @click="savePromptConfig" class="min-h-11 px-4 py-2 bg-white text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">保存筛选提示词</button>
            <button type="button" @click="saveConfigSection('llm_filter')" class="min-h-11 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors">保存 LLM 设置</button>
          </div>
        </div>

        <!-- ==================== Tab 2: 研究方向 ==================== -->
        <div v-if="activeTab === 'research'" class="space-y-6">
          <!-- 研究方向描述 -->
          <div>
            <h3 class="text-lg font-medium text-gray-900 mb-2">研究方向描述</h3>
            <p class="text-sm text-gray-500 mb-4">这段描述会被用于LLM评估论文相关度，请详细描述你的研究方向、关注的技术和问题。</p>
          </div>
          <div>
            <textarea v-model="configData.research_description" rows="12"
              class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50 font-mono text-sm"
              placeholder="示例：&#10;1. 我关注多模态大模型、医学影像分析与报告生成。&#10;2. 重点跟踪视觉语言模型、检索增强、可靠性评估。&#10;3. 更关心可迁移方法，而不是单数据集刷榜。"></textarea>
            <p class="mt-2 text-xs text-gray-500">提示：可以列出关键词、研究主题、技术方向、关注的问题等，越详细评分越精准。</p>
          </div>

          <!-- AI 生成按钮 -->
          <div class="bg-purple-50 rounded-lg p-4 border border-purple-200">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-2">
                <i class="ph ph-sparkle text-purple-600"></i>
                <span class="font-medium text-purple-800">AI 辅助生成评分配置</span>
              </div>
            </div>
            <p class="text-sm text-gray-600 mb-3">基于您的研究方向，AI 可以自动生成评分锚点关键词和评分示例，提高筛选精准度。</p>
            <div class="flex flex-col sm:flex-row gap-3">
              <input v-model="researchBrief" type="text" placeholder="例如：我的研究方向是多模态大模型在医疗影像中的应用"
                class="flex-1 min-h-11 rounded-lg border-gray-300 shadow-sm focus:border-purple-500 focus:ring focus:ring-purple-500/50 text-sm">
              <button type="button" @click="generateResearch" :disabled="generatingResearch || !researchBrief"
                class="min-h-11 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2">
                <i class="ph ph-magic-wand"></i>
                <span v-if="generatingResearch">生成中...</span>
                <span v-else>AI 生成</span>
              </button>
            </div>
          </div>

          <!-- 评分锚点配置 -->
          <div class="border-t border-gray-200 pt-6">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-medium text-gray-900 flex items-center gap-2">
                <i class="ph ph-target text-primary"></i> 评分锚点配置
              </h3>
              <span class="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">用于 LLM 评分参考</span>
            </div>
            <p class="text-sm text-gray-500 mb-4">这些关键词会指导 LLM 如何给论文评分。高分关键词越多，相关度分数越高。</p>

            <!-- 高分关键词 -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
                <i class="ph ph-trend-up text-green-500"></i> 高分关键词 (20-25分)
              </label>
              <textarea v-model="configData.scoring_anchors_high" rows="4"
                class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50 text-sm font-mono"
                placeholder="每行一个关键词，例如：&#10;multimodal learning&#10;vision language model&#10;chart understanding"></textarea>
              <p class="mt-1 text-xs text-gray-500">每行一个关键词或短语，匹配这些内容的论文会得到高分</p>
            </div>

            <!-- 中等分数信号 -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
                <i class="ph ph-minus text-yellow-500"></i> 中等分数信号 (10-19分)
              </label>
              <textarea v-model="configData.scoring_anchors_medium" rows="3"
                class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50 text-sm font-mono"
                placeholder="每行一个关键词，例如：&#10;retrieval augmented generation&#10;weakly supervised learning&#10;clinical benchmark"></textarea>
            </div>

            <!-- 低分/排除关键词 -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
                <i class="ph ph-trend-down text-red-500"></i> 低分/排除关键词 (0-9分)
              </label>
              <textarea v-model="configData.scoring_anchors_low" rows="3"
                class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50 text-sm font-mono"
                placeholder="每行一个关键词，例如：&#10;social media&#10;sentiment analysis&#10;recommendation system"></textarea>
              <p class="mt-1 text-xs text-gray-500">匹配这些内容的论文会被认为是低相关度</p>
            </div>
          </div>

          <!-- 评分示例配置 -->
          <div class="border-t border-gray-200 pt-6">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-medium text-gray-900 flex items-center gap-2">
                <i class="ph ph-lightbulb text-yellow-500"></i> 评分示例配置
              </h3>
              <span class="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">Few-shot 示例</span>
            </div>
            <p class="text-sm text-gray-500 mb-4">提供评分示例帮助 LLM 理解评分标准。建议包含高分、中等、低分各一个示例。</p>

            <div class="grid grid-cols-1 gap-4">
              <!-- 高分示例 -->
              <div class="bg-green-50 rounded-lg p-4 border border-green-200">
                <label class="block text-sm font-medium text-green-800 mb-2 flex items-center gap-1">
                  <i class="ph ph-star text-green-600"></i> 高分示例 (80-100分)
                </label>
                <textarea v-model="configData.few_shot_high" rows="6"
                  class="w-full rounded-lg border-green-300 shadow-sm focus:border-green-500 focus:ring focus:ring-green-500/50 text-sm font-mono"
                  placeholder="示例格式：&#10;标题：论文标题&#10;摘要：论文摘要...&#10;&#10;评分理由：这篇论文与我的研究方向高度相关..."></textarea>
              </div>

              <!-- 中等示例 -->
              <div class="bg-yellow-50 rounded-lg p-4 border border-yellow-200">
                <label class="block text-sm font-medium text-yellow-800 mb-2 flex items-center gap-1">
                  <i class="ph ph-star-half text-yellow-600"></i> 中等示例 (60-79分)
                </label>
                <textarea v-model="configData.few_shot_medium" rows="6"
                  class="w-full rounded-lg border-yellow-300 shadow-sm focus:border-yellow-500 focus:ring focus:ring-yellow-500/50 text-sm font-mono"
                  placeholder="示例格式：&#10;标题：Retrieval-Augmented Clinical QA with Lightweight Adaptation&#10;摘要：方法相关，但与核心任务并非完全重合...&#10;&#10;评分理由：技术路线可借鉴，但研究问题不是当前重点。"></textarea>
              </div>

              <!-- 低分示例 -->
              <div class="bg-red-50 rounded-lg p-4 border border-red-200">
                <label class="block text-sm font-medium text-red-800 mb-2 flex items-center gap-1">
                  <i class="ph ph-star-light text-red-600"></i> 低分示例 (0-59分)
                </label>
                <textarea v-model="configData.few_shot_low" rows="6"
                  class="w-full rounded-lg border-red-300 shadow-sm focus:border-red-500 focus:ring focus:ring-red-500/50 text-sm font-mono"
                  placeholder="示例格式：&#10;标题：Sentiment Analysis for Social Media Posts&#10;摘要：研究社交媒体文本情感分类...&#10;&#10;评分理由：场景与技术路线都偏离当前研究重点。"></textarea>
              </div>
            </div>
          </div>

          <!-- 保存按钮 -->
          <div class="flex justify-end pt-6 border-t border-gray-200">
            <button type="button" @click="saveResearchConfig" class="min-h-11 px-6 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors flex items-center gap-2">
              <i class="ph ph-check"></i> 保存研究方向配置
            </button>
          </div>
        </div>

        <!-- ==================== Tab 3: ArXiv 搜索 ==================== -->
        <div v-if="activeTab === 'arxiv'" class="space-y-6">
          <h3 class="text-lg font-medium text-gray-900">ArXiv 搜索设置</h3>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">搜索关键词/分类 (每行一个)</label>
            <textarea v-model="configData.arxiv.keywords_str" rows="6"
              class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50 font-mono text-sm"
              placeholder="例如：&#10;cs.CL&#10;cat:cs.AI&#10;large language model&#10;multimodal retrieval"></textarea>
            <p class="mt-1 text-xs text-gray-500">例如: cs.CL, cs.CV, cat:cs.AI</p>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">每个关键词最大结果数</label>
              <input type="number" v-model="configData.arxiv.max_results_per_keyword"
                class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
              <p class="mt-1 text-xs text-gray-500">留空或0表示不限制</p>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">API请求间隔 (秒)</label>
              <input type="number" v-model="configData.arxiv.request_delay"
                class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
              <p class="mt-1 text-xs text-gray-500">建议3秒，避免被限流</p>
            </div>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">获取论文天数范围</label>
              <input type="number" v-model="configData.arxiv.recent_days"
                class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
              <p class="mt-1 text-xs text-gray-500">获取最近N天内的论文，建议3天</p>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">连续重复停止阈值</label>
              <input type="number" v-model="configData.arxiv.consecutive_duplicate_threshold"
                class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
              <p class="mt-1 text-xs text-gray-500">连续遇到多少篇已检索的论文后停止搜索</p>
            </div>
          </div>
          <div class="flex justify-end pt-4">
            <button type="button" @click="saveConfigSection('arxiv')" class="min-h-11 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors">保存 ArXiv 设置</button>
          </div>
        </div>

        <!-- ==================== Tab 4: 定时任务 ==================== -->
        <div v-if="activeTab === 'schedule'" class="space-y-6">
          <h3 class="text-lg font-medium text-gray-900">定时任务设置</h3>

          <!-- 论文获取任务 -->
          <div class="bg-gray-50 p-4 rounded-lg border border-gray-200">
            <div class="flex items-center justify-between mb-4">
              <h4 class="font-medium text-gray-800">论文获取任务</h4>
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="configData.schedule.fetch_papers.enable" class="sr-only peer">
                <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/30 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
              </label>
            </div>
            <div class="space-y-3">
              <div class="flex items-center gap-4">
                <label class="text-sm text-gray-600 w-24">执行时间</label>
                <input type="time" v-model="configData.schedule.fetch_papers.time"
                  class="rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
              </div>
              <div>
                <label class="text-sm text-gray-600 block mb-1">每次处理旧论文数量</label>
                <input type="number" v-model="configData.schedule.fetch_papers.backlog_limit"
                  class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
                <p class="mt-1 text-xs text-gray-500">每次任务最多处理多少篇数据库中未筛选的旧论文</p>
              </div>
            </div>
          </div>

          <!-- 论文处理配置 -->
          <div class="bg-gray-50 p-4 rounded-lg border border-gray-200">
            <h4 class="font-medium text-gray-800 mb-4">论文处理配置</h4>
            <div>
              <label class="text-sm text-gray-600 block mb-1">立即解析批次大小</label>
              <input type="number" v-model="configData.schedule.process_papers.batch_size"
                class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
              <p class="mt-1 text-xs text-gray-500">点击"立即解析"按钮时，每次最多处理多少篇未解析的论文</p>
            </div>
          </div>

          <!-- 论文推送任务 -->
          <div class="bg-gray-50 p-4 rounded-lg border border-gray-200">
            <div class="flex items-center justify-between mb-4">
              <h4 class="font-medium text-gray-800">论文推送任务</h4>
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="configData.schedule.push_papers.enable" class="sr-only peer">
                <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/30 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
              </label>
            </div>
            <div class="space-y-3">
              <label class="text-sm text-gray-600 block">推送时间点 (多个时间用逗号分隔)</label>
              <input type="text" v-model="configData.schedule.push_papers.times_str"
                class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50"
                placeholder="09:00, 14:30">
              <label class="text-sm text-gray-600 block mt-2">每次推送最大数量</label>
              <input type="number" v-model="configData.schedule.push_papers.max_papers_per_push"
                class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
            </div>
          </div>

          <div class="flex justify-end pt-4">
            <button type="button" @click="saveConfigSection('schedule')" class="min-h-11 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors">保存调度设置</button>
          </div>
        </div>

        <!-- ==================== Tab 5: 通知渠道 ==================== -->
        <div v-if="activeTab === 'notify' && configData.notify" class="space-y-6">
          <NotifyChannelConfig
            :config="configData.notify"
            @update:config="onNotifyUpdate"
          />

          <div class="flex justify-end pt-4">
            <button type="button" @click="saveConfigSection('notify')" class="min-h-11 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors">保存通知设置</button>
          </div>
        </div>

        <!-- ==================== Tab 6: MinerU 转换 ==================== -->
        <div v-if="activeTab === 'mineru' && configData.mineru_config" class="space-y-6">
          <div class="flex items-center gap-3">
            <h3 class="text-lg font-medium text-gray-900">MinerU 转换设置</h3>
            <a
              href="https://mineru.net/"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center gap-1 text-sm font-medium text-primary transition hover:text-primary/80 hover:underline"
            >
              访问官网
              <i class="ph ph-arrow-square-out text-base"></i>
            </a>
          </div>
          <p class="text-sm text-gray-500">配置 MinerU PDF 转 Markdown 的转换方式，支持云端 API 和本地部署两种模式。</p>

          <!-- Mode selector -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">转换模式</label>
            <el-radio-group v-model="configData.mineru_config.mode">
              <el-radio value="cloud">云端 API</el-radio>
              <el-radio value="local">本地部署</el-radio>
            </el-radio-group>
          </div>

          <!-- Cloud mode settings -->
          <div v-if="configData.mineru_config.mode === 'cloud'" class="space-y-4">
            <div class="bg-blue-50 rounded-lg p-4 border border-blue-200">
              <div class="flex items-center gap-2 mb-2">
                <i class="ph ph-cloud text-blue-600"></i>
                <span class="font-medium text-blue-800">云端 API 模式</span>
              </div>
              <p class="text-sm text-blue-700/80">使用 MinerU 云端服务进行转换，需要提供有效的 API Key。</p>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">API Key</label>
              <input type="password" v-model="configData.mineru_config.api_key"
                placeholder="输入 MinerU API Key"
                class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
              <p class="mt-1 text-xs text-gray-500">从 MinerU 平台获取的 API Key</p>
            </div>
          </div>

          <!-- Local mode settings -->
          <div v-if="configData.mineru_config.mode === 'local'" class="space-y-4">
            <div class="bg-green-50 rounded-lg p-4 border border-green-200">
              <div class="flex items-center gap-2 mb-2">
                <i class="ph ph-desktop text-green-600"></i>
                <span class="font-medium text-green-800">本地部署模式</span>
              </div>
              <p class="text-sm text-green-700/80">使用本地部署的 MinerU 服务，需要先启动 MinerU 服务端。</p>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">服务端地址</label>
              <input type="text" v-model="configData.mineru_config.endpoint"
                placeholder="http://localhost:18000"
                class="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary focus:ring focus:ring-primary/50 focus:ring-opacity-50">
              <p class="mt-1 text-xs text-gray-500">本地 MinerU 服务的地址，默认 http://localhost:18000</p>
            </div>
          </div>

          <div class="flex justify-end pt-4 border-t border-gray-200">
            <button type="button" @click="saveConfigSection('mineru_config')" class="min-h-11 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors flex items-center gap-2">
              <i class="ph ph-check"></i> 保存 MinerU 设置
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import NotifyChannelConfig from '@/components/notify/NotifyChannelConfig.vue'
import { fetchAllConfig, saveConfig, savePrompt as savePromptApi, generateResearch as apiGenerateResearch } from '@/api'

defineEmits(['open-wizard'])

// Tab 定义
const tabs = [
  { key: 'llm_filter', label: 'LLM 筛选' },
  { key: 'research', label: '研究方向' },
  { key: 'arxiv', label: 'ArXiv 搜索' },
  { key: 'schedule', label: '定时任务' },
  { key: 'notify', label: '通知渠道' },
  { key: 'mineru', label: 'MinerU 转换' }
]

const activeTab = ref('llm_filter')
const configData = ref(null)

// 研究方向 AI 生成
const researchBrief = ref('')
const generatingResearch = ref(false)

// 加载配置
const loadConfig = async () => {
  try {
    const res = await fetchAllConfig()
    if (res.data?.success) {
      const config = res.data.data

      // 处理数组转字符串，方便编辑
      if (config.arxiv?.keywords) {
        config.arxiv.keywords_str = config.arxiv.keywords.join('\n')
      }
      if (config.schedule?.push_papers?.times) {
        config.schedule.push_papers.times_str = config.schedule.push_papers.times.join(', ')
      }

      if (!config.prompt_config) {
        config.prompt_config = {}
      }

      if (!config.notify) {
        config.notify = { active_channel: 'console', channels: {} }
      }
      if (!config.notify.channels) {
        config.notify.channels = {}
      }
      // 确保所有渠道配置存在
      const allChannels = ['console', 'bark', 'dingtalk_app', 'dingtalk_webhook', 'feishu', 'telegram', 'smtp', 'wxpusher']
      allChannels.forEach(ch => {
        if (!config.notify.channels[ch]) {
          config.notify.channels[ch] = ch === 'console' ? { CONSOLE: true } : {}
        }
      })

      // 初始化 MinerU 配置
      if (!config.mineru_config) {
        config.mineru_config = { mode: 'cloud', api_key: '', endpoint: 'http://localhost:18000' }
      }
      if (!config.mineru_config.mode) {
        config.mineru_config.mode = 'cloud'
      }
      if (!config.mineru_config.endpoint) {
        config.mineru_config.endpoint = 'http://localhost:18000'
      }

      // 初始化评分锚点和示例字段
      config.scoring_anchors_high = ''
      config.scoring_anchors_medium = ''
      config.scoring_anchors_low = ''
      config.few_shot_high = ''
      config.few_shot_medium = ''
      config.few_shot_low = ''

      // 从 prompt_config 解析评分锚点和示例
      if (config.prompt_config) {
        const promptConfig = config.prompt_config

        // 解析评分锚点
        if (promptConfig.llm_scoring_anchors) {
          const anchorsText = promptConfig.llm_scoring_anchors
          const highMatch = anchorsText.match(/### 高分信号.*?\n(.*?)\n\n###/s)
          const mediumMatch = anchorsText.match(/### 中等分数信号.*?\n(.*?)\n\n###/s)
          const lowMatch = anchorsText.match(/### 低分信号.*?\n(.*?)$/s)

          config.scoring_anchors_high = highMatch ? highMatch[1].trim() : ''
          config.scoring_anchors_medium = mediumMatch ? mediumMatch[1].trim() : ''
          config.scoring_anchors_low = lowMatch ? lowMatch[1].trim() : ''
        }

        // 解析评分示例
        if (promptConfig.llm_few_shot_examples) {
          const examplesText = promptConfig.llm_few_shot_examples
          const matchSection = (patterns) => {
            for (const pattern of patterns) {
              const match = examplesText.match(pattern)
              if (match && match[1]) return match[1].trim()
            }
            return ''
          }

          config.few_shot_high = matchSection([
            /### 高分示例\n(.*?)\n\n###/s,
            /### 示例1（高分论文）\n(.*?)\n\n###/s
          ])
          config.few_shot_medium = matchSection([
            /### 中等示例\n(.*?)\n\n###/s,
            /### 示例2（中等分数论文）\n(.*?)\n\n###/s
          ])
          config.few_shot_low = matchSection([
            /### 低分示例\n(.*?)$/s,
            /### 示例3（低分论文）\n(.*?)$/s
          ])
        }
      }

      configData.value = config
    }
  } catch (e) {
    ElMessage.error('获取配置失败')
  }
}

// 保存配置（通用）
const saveConfigSection = async (section) => {
  if (!configData.value) return

  try {
    if (section === 'notify') {
      // 通知配置直接保存
      await saveConfig('notify', configData.value.notify)
      ElMessage.success('通知设置已保存')
      return
    }

    if (section === 'mineru_config') {
      // MinerU 配置直接保存
      await saveConfig('mineru_config', configData.value.mineru_config)
      ElMessage.success('MinerU 设置已保存')
      return
    }

    const config = JSON.parse(JSON.stringify(configData.value[section]))

    // 处理字符串转数组
    if (section === 'arxiv') {
      config.keywords = configData.value.arxiv.keywords_str
        .split('\n')
        .map(k => k.trim())
        .filter(k => k)
      delete config.keywords_str
    }
    if (section === 'schedule') {
      config.push_papers.times = configData.value.schedule.push_papers.times_str
        .split(',')
        .map(t => t.trim())
        .filter(t => t)
      delete config.push_papers.times_str
    }

    const res = await saveConfig(section, config)
    if (res.data?.success) {
      ElMessage.success('配置已保存')
    } else {
      ElMessage.error(res.data?.message || '保存失败')
    }
  } catch (e) {
    ElMessage.error('保存配置失败')
  }
}

// 保存提示词配置
const savePromptConfig = async () => {
  if (!configData.value) return

  try {
    const promptConfig = configData.value.prompt_config || {}

    await savePromptApi('llm_system_prompt', promptConfig.llm_system_prompt || '')
    await savePromptApi('llm_evaluation_template', promptConfig.llm_evaluation_template || '')

    ElMessage.success('筛选提示词已保存')
    await loadConfig()
  } catch (e) {
    ElMessage.error('保存提示词失败')
  }
}

// 保存研究方向配置（包括评分锚点和示例）
const saveResearchConfig = async () => {
  if (!configData.value) return

  try {
    // 1. 保存研究方向描述
    await saveConfig('research_description', { content: configData.value.research_description })

    // 2. 构建并保存评分锚点
    const anchorsText = `## 评分参考锚点\n\n### 高分信号（每项可得20-25分）\n${configData.value.scoring_anchors_high || ''}\n\n### 中等分数信号（每项10-19分）\n${configData.value.scoring_anchors_medium || ''}\n\n### 低分信号（每项0-9分）\n${configData.value.scoring_anchors_low || ''}`

    await savePromptApi('llm_scoring_anchors', anchorsText)

    // 3. 构建并保存评分示例
    const examplesText = `## 评分示例\n\n### 高分示例\n${configData.value.few_shot_high || ''}\n\n### 中等示例\n${configData.value.few_shot_medium || ''}\n\n### 低分示例\n${configData.value.few_shot_low || ''}`

    await savePromptApi('llm_few_shot_examples', examplesText)

    await loadConfig()
    ElMessage.success('研究方向配置已保存')
  } catch (e) {
    console.error('保存失败:', e)
    ElMessage.error('保存失败')
  }
}

// AI 生成研究方向
const generateResearch = async () => {
  if (!researchBrief.value.trim()) return

  generatingResearch.value = true
  try {
    const res = await apiGenerateResearch(researchBrief.value)
    if (res.data?.success) {
      const data = res.data.data
      configData.value.research_description = data.research_description || configData.value.research_description

      // 填充 AI 生成的锚点和示例
      if (data.llm_config) {
        const anchors = data.llm_config.scoring_anchors || {}
        const examples = data.llm_config.few_shot_examples || {}

        const highAnchors = (anchors.high_score_keywords || []).join('\n')
        const mediumAnchors = (anchors.medium_score_keywords || []).join('\n')
        const lowAnchors = (anchors.low_score_keywords || []).join('\n')

        configData.value.scoring_anchors_high = highAnchors
        configData.value.scoring_anchors_medium = mediumAnchors
        configData.value.scoring_anchors_low = lowAnchors

        // 填充 few-shot 示例为文本
        if (examples.high_score) {
          configData.value.few_shot_high = `标题：${examples.high_score.title || ''}\n摘要：${examples.high_score.abstract || ''}\n\n评分：${examples.high_score.score || 90}\n理由：${examples.high_score.reason || ''}`
        }
        if (examples.medium_score) {
          configData.value.few_shot_medium = `标题：${examples.medium_score.title || ''}\n摘要：${examples.medium_score.abstract || ''}\n\n评分：${examples.medium_score.score || 60}\n理由：${examples.medium_score.reason || ''}`
        }
        if (examples.low_score) {
          configData.value.few_shot_low = `标题：${examples.low_score.title || ''}\n摘要：${examples.low_score.abstract || ''}\n\n评分：${examples.low_score.score || 15}\n理由：${examples.low_score.reason || ''}`
        }
      }

      ElMessage.success('AI 已生成研究方向描述、锚点和评分示例！')
    } else {
      ElMessage.error(res.data?.message || '生成失败')
    }
  } catch (e) {
    ElMessage.error('生成失败，请检查网络')
  } finally {
    generatingResearch.value = false
  }
}

// 通知渠道配置更新
const onNotifyUpdate = (newConfig) => {
  if (configData.value) {
    configData.value.notify = newConfig
  }
}

// 暴露 refresh 方法供 App.vue 调用
defineExpose({ refresh: loadConfig })

onMounted(() => {
  loadConfig()
})
</script>
