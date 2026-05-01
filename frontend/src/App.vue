<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import Sidebar from './components/Sidebar.vue'
import StockTable from './components/StockTable.vue'
import StockDetail from './components/StockDetail.vue'
import SectorRanking from './components/SectorRanking.vue'
import LimitStats from './components/LimitStats.vue'
import StrategyDashboard from './components/StrategyDashboard.vue'
import AiSettings from './components/AiSettings.vue'
import AgentChat from './components/AgentChat.vue'
import { api } from './api'
import { useWatchlist } from './composables/useWatchlist'

const activeTab = ref<'agent' | 'stocks' | 'sectors' | 'limit' | 'strategies' | 'favorites'>(
  (sessionStorage.getItem('activeTab') as 'agent' | 'stocks' | 'sectors' | 'limit' | 'strategies' | 'favorites') || 'stocks'
)
watch(activeTab, (val, prev) => {
  sessionStorage.setItem('activeTab', val)
  if (val === 'favorites') {
    watchlistOnly.value = true
  } else if (prev === 'favorites') {
    watchlistOnly.value = false
  }
})
const isDark = ref(false)

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

onMounted(() => {
  const saved = localStorage.getItem('theme')
  isDark.value = saved === 'dark'
  document.documentElement.classList.toggle('dark', isDark.value)
  handleSearch({})
  loadQuickStrategies()
})

const sidebarRef = ref<InstanceType<typeof Sidebar>>()
const watchlist = useWatchlist()
const watchlistOnly = ref(false)
watch(watchlistOnly, (val) => {
  if (!val && activeTab.value === 'favorites') {
    activeTab.value = 'stocks'
  }
  const filters = { ...currentFilters.value }
  delete filters.page
  delete filters.page_size
  delete filters.codes
  handleSearch(filters)
})
const quickStrategies = ref<{ name: string; filters: Record<string, unknown> }[]>([])

async function loadQuickStrategies() {
  try {
    const data = await api.getStrategies()
    quickStrategies.value = data.strategies
  } catch {}
}

const items = ref<Record<string, unknown>[]>([])
const total = ref(0)
const loading = ref(false)
const selectedCode = ref<string | null>(null)
const currentFilters = ref<Record<string, string>>({})

const displayItems = computed(() => {
  return watchlistOnly.value ? watchlist.filter(items.value) : items.value
})
const currentPage = computed(() => Number(currentFilters.value.page) || 1)
const sortBy = computed(() => currentFilters.value.sort_by || '')
const sortOrder = computed(() => currentFilters.value.order || 'asc')

async function handleSearch(filters: Record<string, string>) {
  loading.value = true
  const params: Record<string, string> = { ...filters, page: '1', page_size: '50' }
  if (watchlistOnly.value && watchlist.codes.value.size > 0) {
    params.codes = [...watchlist.codes.value].join(',')
  } else {
    delete params.codes
  }
  currentFilters.value = params
  try {
    const data = await api.getStocks(currentFilters.value)
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function handlePageChange(page: number) {
  loading.value = true
  const params = { ...currentFilters.value, page: String(page) }
  currentFilters.value = params
  try {
    const data = await api.getStocks(params)
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function handleSortChange(field: string) {
  const sameField = currentFilters.value.sort_by === field
  let nextSortBy: string
  let nextOrder: string
  if (!sameField) {
    nextSortBy = field
    nextOrder = 'asc'
  } else if (currentFilters.value.order === 'asc') {
    nextSortBy = field
    nextOrder = 'desc'
  } else {
    // third click: cancel sort
    nextSortBy = ''
    nextOrder = 'asc'
  }
  const params: Record<string, string> = { ...currentFilters.value, page: '1' }
  if (nextSortBy) {
    params.sort_by = nextSortBy
    params.order = nextOrder
  } else {
    delete params.sort_by
    delete params.order
  }
  currentFilters.value = params
  handleSearch(params)
}

const refreshing = ref(false)
const showAiSettings = ref(false)

async function handleRefresh() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    const result = await api.refreshData()
    if (result.status === 'ok') {
      handleSearch({})
    } else if (result.status === 'running') {
      alert(result.message || '数据刷新正在进行中，请稍后再试')
    } else {
      alert(result.reason || '刷新失败')
    }
  } catch (e) {
    alert('刷新请求失败，请检查后端是否运行')
  } finally {
    refreshing.value = false
  }
}

function handleRowClick(code: string) {
  selectedCode.value = code
}

function handleSectorSelect(code: string, name: string) {
  handleSearch(code ? { industry: code, industry_name: name } : { industry: name })
}

function handleStockFromLimit(code: string) {
  selectedCode.value = code
}

function handleStockSelect(code: string) {
  selectedCode.value = code
}

function handleReset() {
  currentFilters.value = {}
  watchlistOnly.value = false
  sidebarRef.value?.handleReset()
}

function handleApplyStrategy(filters: Record<string, unknown>) {
  const params: Record<string, string> = {}
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== null && v !== '') {
      params[k] = String(v)
    }
  }
  handleSearch(params)
}
</script>

<template>
  <div class="app-layout">
    <Sidebar ref="sidebarRef" :watchlist-only="watchlistOnly" @search="handleSearch" @update:watchlist-only="watchlistOnly = $event" />
    <main class="main-content">
      <div class="top-bar">
        <span class="app-title">A股筛选器</span>
        <div class="top-bar-actions">
          <button class="refresh-btn" :disabled="refreshing" @click="handleRefresh">
            {{ refreshing ? '刷新中...' : '刷新数据' }}
          </button>
          <button class="theme-toggle" @click="toggleTheme">
            {{ isDark ? '☀️ 明' : '🌙 暗' }}
          </button>
          <button class="ai-settings-btn" title="AI 配置" @click="showAiSettings = true">⚙</button>
        </div>
      </div>
      <div class="tab-bar">
        <button
          v-for="t in (['agent', 'stocks', 'favorites', 'strategies', 'sectors', 'limit'] as const)"
          :key="t"
          :class="['tab-btn', { active: activeTab === t }]"
          @click="activeTab = t"
        >{{ { agent: 'AI 选股', stocks: '股票筛选', favorites: '自选', strategies: '策略', sectors: '板块排名', limit: '涨跌停板' }[t] }}</button>
      </div>
      <div v-if="activeTab === 'stocks' || activeTab === 'favorites'" class="strategy-chips">
        <span class="strategy-chips-label">快捷策略:</span>
        <button
          v-for="s in quickStrategies" :key="s.name"
          class="strategy-chip"
          @click="handleApplyStrategy(s.filters)"
        >{{ s.name }}</button>
        <button class="strategy-chip reset-chip" @click="handleReset">重置</button>
      </div>
      <AgentChat v-if="activeTab === 'agent'" @select-stock="handleStockSelect" />
      <StockTable v-if="activeTab === 'stocks' || activeTab === 'favorites'"
        :items="displayItems" :total="total" :loading="loading"
        :current-page="currentPage" :sort-by="sortBy" :sort-order="sortOrder"
        :favorites="watchlist.codes.value"
        @page-change="handlePageChange" @sort-change="handleSortChange"
        @row-click="handleRowClick" @toggle-favorite="watchlist.toggle"
      />
      <StrategyDashboard v-else-if="activeTab === 'strategies'" @apply-strategy="handleApplyStrategy" @select-stock="handleStockSelect" />
      <SectorRanking v-else-if="activeTab === 'sectors'" @select-stock="handleStockSelect" />
      <LimitStats v-else-if="activeTab === 'limit'" @select-stock="handleStockFromLimit" />
    </main>
    <AiSettings v-if="showAiSettings" @close="showAiSettings = false" />
    <StockDetail :code="selectedCode" @close="selectedCode = null" />
  </div>
</template>

<style>
:root {
  --bg-body: #f1f5f9;
  --bg-surface: #ffffff;
  --bg-alt: #f8fafc;
  --bg-hover: #f1f5f9;
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-muted: #94a3b8;
  --border: #e2e8f0;
  --border-strong: #cbd5e1;
  --accent: #3b82f6;
  --accent-hover: #2563eb;
  --accent-light: #eff6ff;
  --shadow: rgba(0,0,0,0.06);
  --shadow-lg: rgba(0,0,0,0.1);
  --red: #ef4444;
  --green: #22c55e;
  --radius: 8px;
  --radius-sm: 6px;
  --transition: 0.2s ease;
}

.dark {
  --bg-body: #0a0f1e;
  --bg-surface: #111827;
  --bg-alt: #1a2332;
  --bg-hover: #1e293b;
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --border: #1e293b;
  --border-strong: #334155;
  --accent: #3b82f6;
  --accent-hover: #60a5fa;
  --accent-light: #1e3a5f;
  --shadow: rgba(0,0,0,0.3);
  --shadow-lg: rgba(0,0,0,0.5);
  --red: #f87171;
  --green: #4ade80;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: var(--bg-body); color: var(--text-primary);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  letter-spacing: 0.01em;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--text-muted); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-secondary); }

/* Transition theme changes */
.app-layout, .top-bar, .sidebar, .stock-table-container, .stock-table th,
.drawer, .filter-group, .market-chip, .range-input, .keyword-input,
.strategy-save-dialog, .pagination button, .column-picker-dropdown,
.stock-table td, .detail-item, .daily-table th {
  transition: background var(--transition), border-color var(--transition), color var(--transition), box-shadow var(--transition);
}

.app-layout { display: flex; min-height: 100vh; }
.main-content { flex: 1; display: flex; flex-direction: column; background: var(--bg-body); }
.top-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 24px; background: var(--bg-surface); border-bottom: 1px solid var(--border);
  box-shadow: 0 1px 3px var(--shadow);
}
.app-title {
  font-size: 18px; font-weight: 800; letter-spacing: -0.01em;
  background: linear-gradient(135deg, var(--accent) 0%, #8b5cf6 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.top-bar-actions { display: flex; gap: 8px; align-items: center; }
.refresh-btn {
  padding: 6px 14px; border: 1px solid var(--accent); border-radius: var(--radius-sm);
  background: var(--accent-light); color: var(--accent); font-size: 12px; font-weight: 500;
  cursor: pointer; transition: all var(--transition);
}
.refresh-btn:hover { background: var(--accent); color: white; box-shadow: 0 2px 8px rgba(59,130,246,0.3); }
.refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; box-shadow: none; }
.theme-toggle {
  padding: 6px 12px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  background: var(--bg-surface); color: var(--text-secondary); font-size: 12px; font-weight: 500;
  cursor: pointer; transition: all var(--transition);
}
.theme-toggle:hover { background: var(--bg-hover); color: var(--text-primary); }
.ai-settings-btn {
  padding: 6px 10px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  background: var(--bg-surface); color: var(--text-secondary); font-size: 14px; font-weight: 500;
  cursor: pointer; transition: all var(--transition); line-height: 1;
}
.ai-settings-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.tab-bar {
  display: flex; gap: 0; background: var(--bg-surface); border-bottom: 1px solid var(--border);
  padding: 0 24px;
}
.tab-btn {
  padding: 10px 20px; border: none; background: transparent; color: var(--text-secondary);
  font-size: 13px; font-weight: 500; cursor: pointer; border-bottom: 2px solid transparent;
  transition: all var(--transition);
}
.tab-btn:hover { color: var(--text-primary); background: var(--bg-hover); }
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }

/* Strategy quick-select chips */
.strategy-chips {
  display: flex; align-items: center; gap: 6px; padding: 8px 24px;
  background: var(--bg-surface); border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
}
.strategy-chips-label { font-size: 11px; color: var(--text-muted); font-weight: 600; white-space: nowrap; }
.strategy-chip {
  padding: 3px 10px; border: 1px solid var(--border-strong); border-radius: 20px;
  background: var(--bg-alt); color: var(--text-secondary); font-size: 11px;
  cursor: pointer; font-weight: 500; transition: all var(--transition); white-space: nowrap;
}
.strategy-chip:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-light); }
.reset-chip { border-style: dashed; color: var(--text-muted); }
.reset-chip:hover { border-color: var(--text-muted); color: var(--text-primary); background: var(--bg-hover); }
</style>
