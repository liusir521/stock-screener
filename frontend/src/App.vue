<script setup lang="ts">
import { ref } from 'vue'
import Sidebar from './components/Sidebar.vue'
import StockTable from './components/StockTable.vue'
import StockDetail from './components/StockDetail.vue'
import { api } from './api'

const items = ref<Record<string, unknown>[]>([])
const total = ref(0)
const loading = ref(false)
const selectedCode = ref<string | null>(null)
const currentFilters = ref<Record<string, string>>({})

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
  const params = { ...currentFilters.value, sort_by: field, order: currentFilters.value.order === 'asc' ? 'desc' : 'asc', page: '1' }
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
      <StockTable
        :items="items" :total="total" :loading="loading"
        @page-change="handlePageChange" @sort-change="handleSortChange"
        @row-click="handleRowClick"
      />
    </main>
    <StockDetail :code="selectedCode" @close="selectedCode = null" />
  </div>
</template>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0b1120; color: #e2e8f0; }
.app-layout { display: flex; min-height: 100vh; }
.main-content { flex: 1; display: flex; flex-direction: column; background: #0b1120; }
</style>
