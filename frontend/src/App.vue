<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Sidebar from './components/Sidebar.vue'
import StockTable from './components/StockTable.vue'
import StockDetail from './components/StockDetail.vue'
import { api } from './api'

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
})

const items = ref<Record<string, unknown>[]>([])
const total = ref(0)
const loading = ref(false)
const selectedCode = ref<string | null>(null)
const currentFilters = ref<Record<string, string>>({})
const currentPage = computed(() => Number(currentFilters.value.page) || 1)
const sortBy = computed(() => currentFilters.value.sort_by || '')
const sortOrder = computed(() => currentFilters.value.order || 'asc')

async function handleSearch(filters: Record<string, string>) {
  loading.value = true
  currentFilters.value = { ...filters, page: '1', page_size: '50' }
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

function handleRowClick(code: string) {
  selectedCode.value = code
}
</script>

<template>
  <div class="app-layout">
    <Sidebar @search="handleSearch" />
    <main class="main-content">
      <div class="top-bar">
        <span class="app-title">A股筛选器</span>
        <button class="theme-toggle" @click="toggleTheme">
          {{ isDark ? '☀️ 明' : '🌙 暗' }}
        </button>
      </div>
      <StockTable
        :items="items" :total="total" :loading="loading"
        :current-page="currentPage" :sort-by="sortBy" :sort-order="sortOrder"
        @page-change="handlePageChange" @sort-change="handleSortChange"
        @row-click="handleRowClick"
      />
    </main>
    <StockDetail :code="selectedCode" @close="selectedCode = null" />
  </div>
</template>

<style>
:root {
  --bg-body: #f0f2f5;
  --bg-surface: #ffffff;
  --bg-alt: #f8fafc;
  --bg-hover: #f1f5f9;
  --text-primary: #1a1a2e;
  --text-secondary: #64748b;
  --text-muted: #94a3b8;
  --border: #e2e8f0;
  --border-strong: #cbd5e1;
  --accent: #3b82f6;
  --accent-hover: #2563eb;
  --accent-light: #eff6ff;
  --shadow: rgba(0,0,0,0.08);
}

.dark {
  --bg-body: #0b1120;
  --bg-surface: #0f172a;
  --bg-alt: #1e293b;
  --bg-hover: #1e293b;
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --border: #1e293b;
  --border-strong: #475569;
  --accent-light: #1e3a5f;
  --shadow: rgba(0,0,0,0.4);
}

* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg-body); color: var(--text-primary); }
.app-layout { display: flex; min-height: 100vh; }
.main-content { flex: 1; display: flex; flex-direction: column; background: var(--bg-body); }
.top-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 20px; background: var(--bg-surface); border-bottom: 1px solid var(--border);
}
.app-title { font-size: 16px; font-weight: 700; }
.theme-toggle {
  padding: 4px 12px; border: 1px solid var(--border-strong); border-radius: 4px;
  background: var(--bg-surface); color: var(--text-secondary); font-size: 12px; cursor: pointer;
}
.theme-toggle:hover { background: var(--bg-hover); }
</style>
