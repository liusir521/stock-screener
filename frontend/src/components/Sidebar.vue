<script setup lang="ts">
import { reactive } from 'vue'
import MarketFilter from './MarketFilter.vue'
import FilterGroup from './FilterGroup.vue'

const emit = defineEmits<{
  search: [filters: Record<string, string>]
}>()

const market = reactive({ value: '' })

const fundamental = reactive<Record<string, [number, number]>>({
  pe_ttm: [0, 100],
  pb: [0, 10],
  roe: [0, 50],
  market_cap: [0, 5000],
  dividend_yield: [0, 10],
})

const technical = reactive<Record<string, [number, number]>>({
  turnover_rate: [0, 20],
})

function handleSearch() {
  const params: Record<string, string> = {}
  if (market.value) params.market = market.value
  params.exclude_st = 'true'

  const addRange = (key: string, range: [number, number], defaults: [number, number]) => {
    if (range[0] !== defaults[0]) params[`${key}_min`] = String(range[0])
    if (range[1] !== defaults[1]) params[`${key}_max`] = String(range[1])
  }

  addRange('pe', fundamental.pe_ttm, [0, 100])
  addRange('pb', fundamental.pb, [0, 10])
  addRange('roe', fundamental.roe, [0, 50])
  addRange('market_cap', fundamental.market_cap, [0, 5000])
  addRange('dividend_yield', fundamental.dividend_yield, [0, 10])

  params.sort_by = 'pe_ttm'
  params.order = 'asc'
  params.page = '1'
  params.page_size = '50'

  emit('search', params)
}
</script>

<template>
  <aside class="sidebar">
    <h2 class="sidebar-title">筛选条件</h2>
    <MarketFilter v-model="market.value" />
    <FilterGroup title="基本面"
      :filters="[
        { key: 'pe_ttm', label: 'PE (TTM)', min: 0, max: 500, step: 1 },
        { key: 'pb', label: 'PB', min: 0, max: 20, step: 0.1 },
        { key: 'roe', label: 'ROE (%)', min: -50, max: 100, step: 1 },
        { key: 'market_cap', label: '市值（亿）', min: 0, max: 10000, step: 10 },
        { key: 'dividend_yield', label: '股息率 (%)', min: 0, max: 20, step: 0.1 },
      ]"
      v-model="fundamental"
    />
    <FilterGroup title="技术面"
      :filters="[
        { key: 'turnover_rate', label: '换手率 (%)', min: 0, max: 50, step: 0.5 },
      ]"
      v-model="technical"
    />
    <button class="search-btn" @click="handleSearch">筛选</button>
    <button class="reset-btn" @click="$emit('search', {})">重置</button>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 260px; flex-shrink: 0; background: #0f172a; padding: 16px;
  border-right: 1px solid #1e293b; overflow-y: auto; height: 100vh;
}
.sidebar-title { font-size: 16px; font-weight: 700; margin-bottom: 16px; }
.search-btn {
  width: 100%; padding: 8px; background: #3b82f6; color: white; border: none;
  border-radius: 6px; font-size: 14px; cursor: pointer; margin-bottom: 6px;
}
.search-btn:hover { background: #2563eb; }
.reset-btn {
  width: 100%; padding: 6px; background: transparent; color: #94a3b8;
  border: 1px solid #475569; border-radius: 6px; font-size: 12px; cursor: pointer;
}
</style>
