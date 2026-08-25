<template>
  <div ref="rootEl" class="space-y-4 h-full">
    <!-- 筛选栏 -->
    <div class="bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex flex-wrap gap-4 items-center justify-between">
      <div class="flex items-center gap-4 flex-1 flex-wrap">
        <div class="relative flex-1 min-w-full sm:min-w-[220px] sm:max-w-md">
          <i class="ph ph-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"></i>
          <label for="paper-search" class="sr-only">搜索标题、作者</label>
          <input id="paper-search" v-model="searchQuery" type="text" placeholder="搜索标题、作者..." class="w-full min-h-11 pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm">
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <label for="paper-date-start" class="sr-only">开始日期</label>
          <input id="paper-date-start" v-model="filterDateStart" type="date" class="min-h-11 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50" placeholder="开始日期">
          <span class="text-gray-400 text-sm">至</span>
          <label for="paper-date-end" class="sr-only">结束日期</label>
          <input id="paper-date-end" v-model="filterDateEnd" type="date" class="min-h-11 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50" placeholder="结束日期">
        </div>
        <label for="paper-min-score" class="sr-only">最低分数</label>
        <select id="paper-min-score" v-model="filterStars" class="min-h-11 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50">
          <option value="0">所有分数</option>
          <option value="90">90+ (高度相关)</option>
          <option value="80">80+ (很相关)</option>
          <option value="70">70+ (较相关)</option>
          <option value="60">60+ (及格)</option>
        </select>
        <label for="paper-comment-filter" class="sr-only">评论筛选</label>
        <select id="paper-comment-filter" v-model="filterComment" class="min-h-11 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50">
          <option value="all">全部论文</option>
          <option value="with">有评论</option>
          <option value="without">无评论</option>
        </select>
        <label class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
          <input type="checkbox" v-model="filterMarked" class="rounded text-primary focus:ring-primary">
          仅看已标记
        </label>
        <label class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
          <input type="checkbox" v-model="showPushed" class="rounded text-primary focus:ring-primary">
          显示已推送
        </label>
        <button type="button" @click="onConfirmFilters" :disabled="loading" class="min-h-11 px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors flex items-center gap-2 shadow-sm shadow-primary/30 disabled:opacity-50 disabled:cursor-not-allowed">
          <i :class="loading ? 'ph ph-spinner animate-spin' : 'ph ph-funnel'"></i>
          {{ loading ? '筛选中...' : '确定筛选' }}
        </button>
      </div>
      <div class="text-sm text-gray-500">
        共 {{ totalCount }} 篇论文
      </div>
    </div>

    <!-- 列表 -->
    <div class="space-y-3">
      <PaperCard
        v-for="paper in papers"
        :key="paper.DOI"
        :paper="paper"
        :loading-mark="loadingMark.has(paper.DOI)"
        :loading-retranslate="loadingRetranslate.has(paper.DOI)"
        :loading-delete="loadingDelete.has(paper.DOI)"
        @click="openDrawer(paper)"
        @toggle-mark="toggleMark"
        @retranslate="retranslatePaper"
        @delete="deletePaper"
      />

      <!-- 空状态 -->
      <div v-if="papers.length === 0 && !loading" class="text-center py-12 text-gray-500">
        <i class="ph ph-files text-4xl mb-2 opacity-50"></i>
        <p>没有找到符合条件的论文</p>
        <button
          v-if="hasActiveFilters"
          type="button"
          @click="resetFilters"
          class="mt-4 px-4 py-2 rounded-lg border border-gray-300 bg-white text-gray-700 text-sm hover:bg-gray-50 transition-colors"
        >
          清空筛选条件
        </button>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="totalPages > 1" class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mt-6 bg-white p-4 rounded-xl shadow-sm border border-gray-100">
      <div class="text-sm text-gray-600">
        第 {{ currentPage }} / {{ totalPages }} 页，共 {{ totalCount }} 篇论文
      </div>
      <div class="flex flex-wrap gap-2">
        <button type="button" @click="goToPage(1)" :disabled="currentPage === 1" class="min-h-11 px-3 py-1 rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed text-sm">
          首页
        </button>
        <button type="button" @click="goToPage(currentPage - 1)" :disabled="currentPage === 1" class="min-h-11 px-3 py-1 rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed text-sm">
          上一页
        </button>
        <button type="button" @click="goToPage(currentPage + 1)" :disabled="currentPage === totalPages" class="min-h-11 px-3 py-1 rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed text-sm">
          下一页
        </button>
        <button type="button" @click="goToPage(totalPages)" :disabled="currentPage === totalPages" class="min-h-11 px-3 py-1 rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed text-sm">
          末页
        </button>
      </div>
    </div>

    <!-- 抽屉 -->
    <PaperDrawer
      v-model:open="drawerOpen"
      :paper="selectedPaper"
      :loading-mark="loadingMark.has(selectedPaper?.DOI)"
      :loading-retranslate="loadingRetranslate.has(selectedPaper?.DOI)"
      :loading-delete="loadingDelete.has(selectedPaper?.DOI)"
      @toggle-mark="toggleMark"
      @retranslate="retranslatePaper"
      @delete="deletePaper"
      @update-comment="updateComment"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessageBox } from 'element-plus'
import PaperCard from '@/components/PaperCard.vue'
import PaperDrawer from '@/components/PaperDrawer.vue'
import { useToast } from '@/composables/useToast'
import {
  fetchPapers as fetchPapersApi,
  confirmFilters as confirmFiltersApi,
  togglePaperMark,
  updatePaperComment,
  deletePaper as deletePaperApi,
  retranslatePaper as retranslatePaperApi
} from '@/api'

const { showToast } = useToast()

const rootEl = ref(null)

// 论文数据
const papers = ref([])
const loading = ref(false)
const selectedPaper = ref({})
const drawerOpen = ref(false)

// 按钮加载状态（按 DOI 记录）
const loadingMark = ref(new Set())
const loadingRetranslate = ref(new Set())
const loadingDelete = ref(new Set())

// 筛选状态
const searchQuery = ref('')
const filterStars = ref('0')
const filterMarked = ref(false)
const filterComment = ref('all')
const showPushed = ref(true)
// 默认只显示最近一个月的论文
const oneMonthAgo = new Date()
oneMonthAgo.setMonth(oneMonthAgo.getMonth() - 1)
const filterDateStart = ref(oneMonthAgo.toISOString().slice(0, 10))
const filterDateEnd = ref('')
const useConfirmedFilters = ref(false)

// 分页状态
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)

const totalPages = computed(() => {
  return Math.ceil(totalCount.value / pageSize.value)
})

const hasActiveFilters = computed(() => {
  return !!searchQuery.value ||
    filterStars.value !== '0' ||
    filterMarked.value ||
    filterComment.value !== 'all' ||
    !showPushed.value ||
    !!filterDateStart.value ||
    !!filterDateEnd.value ||
    useConfirmedFilters.value
})

// 获取论文列表
const fetchPapers = async () => {
  try {
    const offset = (currentPage.value - 1) * pageSize.value
    const params = {
      limit: pageSize.value,
      offset
    }

    if (useConfirmedFilters.value) {
      params.use_confirmed_filters = true
    } else {
      params.show_pushed = showPushed.value
      params.comment_filter = filterComment.value
      params.min_stars = filterStars.value
      params.only_marked = filterMarked.value
      if (filterDateStart.value) params.date_start = filterDateStart.value
      if (filterDateEnd.value) params.date_end = filterDateEnd.value
      if (searchQuery.value) params.search = searchQuery.value
    }

    const res = await fetchPapersApi(params)
    if (res.data?.success) {
      papers.value = res.data.data
      totalCount.value = res.data.total
    }
  } catch (e) {
    showToast('获取论文列表失败', 'error')
  }
}

// 确认筛选
const onConfirmFilters = async () => {
  loading.value = true
  try {
    const payload = {
      search: searchQuery.value,
      date_start: filterDateStart.value || null,
      date_end: filterDateEnd.value || null,
      min_stars: filterStars.value,
      comment_filter: filterComment.value,
      only_marked: filterMarked.value,
      show_pushed: showPushed.value
    }

    const res = await confirmFiltersApi(payload)
    if (res.data?.success) {
      showToast('筛选已生效')
      useConfirmedFilters.value = true
      currentPage.value = 1
      await fetchPapers()
    } else {
      showToast(res.data?.message || '筛选失败', 'error')
    }
  } catch (e) {
    showToast('请求失败', 'error')
  } finally {
    loading.value = false
  }
}

// 分页
const goToPage = async (page) => {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
    await fetchPapers()
    const container = rootEl.value?.closest('.overflow-y-auto')
    if (container) container.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

// 重置筛选
const resetFilters = async () => {
  searchQuery.value = ''
  filterStars.value = '0'
  filterMarked.value = false
  filterComment.value = 'all'
  showPushed.value = true
  filterDateStart.value = ''
  filterDateEnd.value = ''
  useConfirmedFilters.value = false
  currentPage.value = 1
  await fetchPapers()
}

// 打开抽屉
const openDrawer = (paper) => {
  selectedPaper.value = paper
  drawerOpen.value = true
}

// 标记/取消标记
const toggleMark = async (paper) => {
  if (loadingMark.value.has(paper.DOI)) return
  loadingMark.value.add(paper.DOI)
  const newStatus = !paper.is_marked
  paper.is_marked = newStatus

  try {
    const res = await togglePaperMark(paper.DOI, newStatus)
    if (!res.data?.success) {
      throw new Error('Failed')
    }
    showToast(newStatus ? '已标记' : '已取消标记')
  } catch (e) {
    paper.is_marked = !newStatus
    showToast('操作失败', 'error')
  } finally {
    loadingMark.value.delete(paper.DOI)
  }
}

// 更新评论
const updateComment = async (paper, comment) => {
  try {
    const res = await updatePaperComment(paper.DOI, comment)
    if (res.data?.success) {
      paper.comment = comment
      showToast('评论已保存')
      return true
    }
    throw new Error('Failed')
  } catch (e) {
    showToast('保存评论失败', 'error')
    return false
  }
}

// 删除论文
const deletePaper = async (paper) => {
  if (loadingDelete.value.has(paper.DOI)) return
  try {
    await ElMessageBox.confirm(
      `确定要删除论文《${paper.TitleCN || paper.Title}》吗？`,
      '确认删除',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }

  loadingDelete.value.add(paper.DOI)
  try {
    const res = await deletePaperApi(paper.DOI)
    if (res.data?.success) {
      papers.value = papers.value.filter(p => p.DOI !== paper.DOI)
      drawerOpen.value = false
      showToast('论文已删除')
    } else {
      throw new Error('Failed')
    }
  } catch (e) {
    showToast('删除失败', 'error')
  } finally {
    loadingDelete.value.delete(paper.DOI)
  }
}

// 重新翻译
const retranslatePaper = async (paper) => {
  if (loadingRetranslate.value.has(paper.DOI)) return
  loadingRetranslate.value.add(paper.DOI)
  try {
    showToast('正在重新翻译...', 'info')
    const res = await retranslatePaperApi(paper.DOI)
    if (res.data?.success) {
      paper.TitleCN = res.data.TitleCN
      paper.AbstractCN = res.data.AbstractCN
      showToast('翻译完成')
    } else {
      throw new Error('Failed')
    }
  } catch (e) {
    showToast('翻译失败', 'error')
  } finally {
    loadingRetranslate.value.delete(paper.DOI)
  }
}

// 暴露 refresh 给父组件调用
const refresh = async () => {
  await fetchPapers()
}

onMounted(() => {
  fetchPapers()
})

defineExpose({ refresh })
</script>
