<template>
  <div ref="rootEl" class="space-y-4 h-full">
    <!-- 筛选栏 -->
    <div class="bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex flex-wrap gap-4 items-center justify-between">
      <div class="flex items-center gap-4 flex-1 flex-wrap">
        <div class="relative flex-1 max-w-md">
          <i class="ph ph-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"></i>
          <input v-model="searchQuery" type="text" placeholder="搜索标题、作者..." class="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm">
        </div>
        <div class="flex items-center gap-2">
          <input v-model="filterDateStart" type="date" class="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50" placeholder="开始日期">
          <span class="text-gray-400 text-sm">至</span>
          <input v-model="filterDateEnd" type="date" class="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50" placeholder="结束日期">
        </div>
        <select v-model="filterStars" class="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50">
          <option value="0">所有分数</option>
          <option value="90">90+ (高度相关)</option>
          <option value="80">80+ (很相关)</option>
          <option value="70">70+ (较相关)</option>
          <option value="60">60+ (及格)</option>
        </select>
        <select v-model="filterComment" class="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50">
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
        <button @click="onConfirmFilters" class="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors flex items-center gap-2 shadow-sm shadow-primary/30">
          <i class="ph ph-funnel"></i>
          确定筛选
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
        @click="openDrawer(paper)"
        @toggle-mark="toggleMark"
        @retranslate="retranslatePaper"
        @delete="deletePaper"
      />

      <!-- 空状态 -->
      <div v-if="papers.length === 0 && !loading" class="text-center py-12 text-gray-500">
        <i class="ph ph-files text-4xl mb-2 opacity-50"></i>
        <p>没有找到符合条件的论文</p>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="totalPages > 1" class="flex items-center justify-between mt-6 bg-white p-4 rounded-xl shadow-sm border border-gray-100">
      <div class="text-sm text-gray-600">
        第 {{ currentPage }} / {{ totalPages }} 页，共 {{ totalCount }} 篇论文
      </div>
      <div class="flex gap-2">
        <button @click="goToPage(1)" :disabled="currentPage === 1" class="px-3 py-1 rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed text-sm">
          首页
        </button>
        <button @click="goToPage(currentPage - 1)" :disabled="currentPage === 1" class="px-3 py-1 rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed text-sm">
          上一页
        </button>
        <button @click="goToPage(currentPage + 1)" :disabled="currentPage === totalPages" class="px-3 py-1 rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed text-sm">
          下一页
        </button>
        <button @click="goToPage(totalPages)" :disabled="currentPage === totalPages" class="px-3 py-1 rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed text-sm">
          末页
        </button>
      </div>
    </div>

    <!-- 抽屉 -->
    <PaperDrawer
      v-model:open="drawerOpen"
      :paper="selectedPaper"
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

// 筛选状态
const searchQuery = ref('')
const filterStars = ref('0')
const filterMarked = ref(false)
const filterComment = ref('all')
const showPushed = ref(true)
const filterDateStart = ref('')
const filterDateEnd = ref('')
const useConfirmedFilters = ref(false)

// 分页状态
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)

const totalPages = computed(() => {
  return Math.ceil(totalCount.value / pageSize.value)
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

// 打开抽屉
const openDrawer = (paper) => {
  selectedPaper.value = paper
  drawerOpen.value = true
}

// 标记/取消标记
const toggleMark = async (paper) => {
  const newStatus = !paper.is_marked
  // 乐观更新
  paper.is_marked = newStatus

  try {
    const res = await togglePaperMark(paper.DOI, newStatus)
    if (!res.data?.success) {
      throw new Error('Failed')
    }
    showToast(newStatus ? '已标记' : '已取消标记')
  } catch (e) {
    paper.is_marked = !newStatus // 回滚
    showToast('操作失败', 'error')
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
  try {
    await ElMessageBox.confirm(
      `确定要删除论文《${paper.TitleCN || paper.Title}》吗？`,
      '确认删除',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return // 用户取消
  }

  try {
    const res = await deletePaperApi(paper.DOI)
    if (res.data?.success) {
      // 从列表中移除
      papers.value = papers.value.filter(p => p.DOI !== paper.DOI)
      drawerOpen.value = false
      showToast('论文已删除')
    } else {
      throw new Error('Failed')
    }
  } catch (e) {
    showToast('删除失败', 'error')
  }
}

// 重新翻译
const retranslatePaper = async (paper) => {
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
