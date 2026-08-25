<template>
  <aside class="w-full md:w-64 bg-white border-b md:border-b-0 md:border-r border-gray-200 flex md:flex-col shrink-0 shadow-sm z-10">
    <div class="p-4 md:p-6 flex items-center gap-3 border-r md:border-r-0 md:border-b border-gray-100 shrink-0">
      <div class="w-8 h-8 bg-gradient-to-br from-primary to-secondary rounded-lg flex items-center justify-center text-white font-bold">
        <i class="ph ph-book-open-text text-xl"></i>
      </div>
      <h1 class="font-bold text-lg tracking-tight text-gray-900">DailyScholar</h1>
    </div>

    <nav class="flex-1 p-2 md:p-4 flex md:block gap-3 md:space-y-5 overflow-x-auto md:overflow-x-visible md:overflow-y-auto" aria-label="主导航">
      <div v-for="group in navGroups" :key="group.label" class="flex md:block shrink-0 md:space-y-1">
        <div class="hidden md:block px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
          {{ group.label }}
        </div>
        <div class="flex md:block gap-1 md:space-y-1">
        <router-link
          v-for="item in group.items"
          :key="item.to"
          :to="item.to"
          custom
          v-slot="{ href, isActive, navigate }"
        >
          <a
            :href="href"
            @click="navigate"
            :aria-current="isActive ? 'page' : undefined"
            :class="['flex items-center gap-2 md:gap-3 px-3 md:px-4 py-3 min-h-11 rounded-lg transition-colors whitespace-nowrap', isActive ? 'bg-primary/10 text-primary font-medium' : 'text-gray-600 hover:bg-gray-50']"
          >
            <i :class="[item.icon, 'text-xl']"></i>
            {{ item.label }}
            <span
              v-if="item.name === 'queue' && queueSize > 0"
              class="ml-auto bg-primary text-white text-xs px-2 py-0.5 rounded-full"
            >{{ queueSize }}</span>
          </a>
        </router-link>
        </div>
      </div>
    </nav>

    <div class="hidden md:block p-4 border-t border-gray-100">
      <div class="bg-gray-50 rounded-lg p-3 text-xs text-gray-500">
        <div class="flex justify-between mb-1">
          <span>版本</span>
          <span class="font-medium">v3.0</span>
        </div>
        <div class="flex justify-between">
          <span>状态</span>
          <span class="flex items-center gap-1 text-success font-medium">
            <span class="w-1.5 h-1.5 rounded-full bg-success"></span>
            运行中
          </span>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
defineProps({
  queueSize: {
    type: Number,
    default: 0
  }
})

const navGroups = [
  {
    label: '阅读工作区',
    items: [
      { to: '/', name: 'dashboard', icon: 'ph ph-squares-four', label: '仪表盘' },
      { to: '/papers', name: 'papers', icon: 'ph ph-article', label: '论文列表' },
      { to: '/queue', name: 'queue', icon: 'ph ph-queue', label: '推送队列' },
    ]
  },
  {
    label: '系统管理',
    items: [
      { to: '/logs', name: 'logs', icon: 'ph ph-terminal-window', label: '系统日志' },
      { to: '/config', name: 'config', icon: 'ph ph-gear', label: '系统配置' },
    ]
  }
]
</script>
