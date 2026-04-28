<script setup lang="ts">
import { reactive, ref } from 'vue'
import MarketFilter from './MarketFilter.vue'
import FilterGroup from './FilterGroup.vue'
import StrategySave from './StrategySave.vue'

const emit = defineEmits<{
  search: [filters: Record<string, string>]
  'update:watchlistOnly': [value: boolean]
}>()

const props = defineProps<{ watchlistOnly?: boolean }>()

const keyword = ref('')
const market = reactive({ value: '' })

const PE_DEFAULT: [number, number] = [-100, 500]

const fundamental = ref<Record<string, [number, number]>>({
  pe_ttm: PE_DEFAULT.slice() as [number, number],
  pb: [0, 10],
  roe: [0, 50],
  market_cap: [0, 5000],
  dividend_yield: [0, 10],
  revenue_growth_3y: [0, 100],
})

const technical = ref<Record<string, [number, number]>>({
  turnover_rate: [0, 20],
  change_pct: [-30, 30],
  volume_ratio: [0, 10],
})

function handleKeywordSearch() {
  const kw = keyword.value.trim()
  if (!kw) return
  // Reset filter state silently, then emit once (avoids race with handleReset's emit)
  market.value = ''
  fundamental.value = {
    pe_ttm: PE_DEFAULT.slice() as [number, number],
    pb: [0, 10],
    roe: [0, 50],
    market_cap: [0, 5000],
    dividend_yield: [0, 10],
    revenue_growth_3y: [0, 100],
  }
  technical.value = { turnover_rate: [0, 20], change_pct: [-10, 10], volume_ratio: [0, 10] }
  keyword.value = kw
  const params: Record<string, string> = {
    keyword: kw,
    page: '1',
    page_size: '50',
  }
  currentFilters.value = params
  emit('search', params)
}

function clearKeyword() {
  keyword.value = ''
}

function handleFilterSearch() {
  clearKeyword()
  const params: Record<string, string> = {}
  if (market.value) params.market = market.value
  params.exclude_st = 'true'

  const addRange = (key: string, range: [number, number]) => {
    params[`${key}_min`] = String(range[0])
    params[`${key}_max`] = String(range[1])
  }

  addRange('pe', fundamental.value.pe_ttm)
  addRange('pb', fundamental.value.pb)
  addRange('roe', fundamental.value.roe)
  addRange('market_cap', fundamental.value.market_cap)
  addRange('dividend_yield', fundamental.value.dividend_yield)
  addRange('revenue_growth', fundamental.value.revenue_growth_3y)

  addRange('change_pct', technical.value.change_pct)
  addRange('volume_ratio', technical.value.volume_ratio)

  params.sort_by = currentFilters.value.sort_by || 'pe_ttm'
  params.order = currentFilters.value.order || 'asc'
  params.page = '1'
  params.page_size = '50'

  currentFilters.value = params
  emit('search', params)
}

const currentFilters = ref<Record<string, string>>({})

function handleReset() {
  keyword.value = ''
  market.value = ''
  fundamental.value = {
    pe_ttm: PE_DEFAULT.slice() as [number, number],
    pb: [0, 10],
    roe: [0, 50],
    market_cap: [0, 5000],
    dividend_yield: [0, 10],
    revenue_growth_3y: [0, 100],
  }
  technical.value = { turnover_rate: [0, 20], change_pct: [-10, 10], volume_ratio: [0, 10] }
  currentFilters.value = {}
  emit('search', {})
}

function handleLoadStrategy(filters: Record<string, string>) {
  if (filters.market) market.value = filters.market
  const numKeys = ['pe_min', 'pe_max', 'pb_min', 'pb_max', 'roe_min', 'market_cap_min', 'market_cap_max', 'dividend_yield_min', 'revenue_growth_min', 'change_pct_min', 'change_pct_max', 'volume_ratio_min']
  numKeys.forEach(k => {
    if (filters[k]) {
      const val = Number(filters[k])
      if (k.startsWith('pe_')) {
        if (k === 'pe_min') fundamental.value.pe_ttm[0] = val
        else fundamental.value.pe_ttm[1] = val
      } else if (k.startsWith('pb_')) {
        if (k === 'pb_min') fundamental.value.pb[0] = val
        else fundamental.value.pb[1] = val
      } else if (k.startsWith('roe')) fundamental.value.roe[0] = val
      else if (k.startsWith('market_cap_')) {
        if (k === 'market_cap_min') fundamental.value.market_cap[0] = val
        else fundamental.value.market_cap[1] = val
      } else if (k.startsWith('dividend_yield')) fundamental.value.dividend_yield[0] = val
      else if (k.startsWith('revenue_growth')) fundamental.value.revenue_growth_3y[0] = val
      else if (k.startsWith('change_pct_')) {
        if (k === 'change_pct_min') technical.value.change_pct[0] = val
        else technical.value.change_pct[1] = val
      } else if (k.startsWith('volume_ratio')) technical.value.volume_ratio[0] = val
    }
  })
  handleFilterSearch()
}
</script>

<template>
  <aside class="sidebar">
    <h2 class="sidebar-title">筛选条件</h2>
    <div class="keyword-search">
      <div class="keyword-input-wrap">
        <input
          v-model="keyword"
          type="text"
          placeholder="搜索股票名称或代码"
          class="keyword-input"
          @keydown.enter.prevent="handleKeywordSearch"
        />
        <button v-if="keyword" class="keyword-clear" @click="clearKeyword">✕</button>
      </div>
      <button class="keyword-btn" @click="handleKeywordSearch">搜索</button>
    </div>
    <MarketFilter v-model="market.value" />
    <FilterGroup title="基本面"
      :filters="[
        { key: 'pe_ttm', label: 'PE (TTM)', min: -100, max: 500, step: 1 },
        { key: 'pb', label: 'PB', min: 0, max: 20, step: 0.1 },
        { key: 'roe', label: 'ROE (%)', min: -50, max: 100, step: 1 },
        { key: 'market_cap', label: '市值（亿）', min: 0, max: 10000, step: 10 },
        { key: 'dividend_yield', label: '股息率 (%)', min: 0, max: 20, step: 0.1 },
        { key: 'revenue_growth_3y', label: '营收增长率 (%)', min: -100, max: 500, step: 1 },
      ]"
      v-model="fundamental"
    />
    <FilterGroup title="技术面"
      :filters="[
        { key: 'turnover_rate', label: '换手率 (%)', min: 0, max: 50, step: 0.5 },
        { key: 'change_pct', label: '涨跌幅 (%)', min: -30, max: 30, step: 0.1 },
        { key: 'volume_ratio', label: '量比', min: 0, max: 20, step: 0.1 },
      ]"
      v-model="technical"
    />
    <label class="watchlist-toggle">
      <input type="checkbox" :checked="props.watchlistOnly" @change="emit('update:watchlistOnly', ($event.target as HTMLInputElement).checked)" />
      仅看自选
    </label>
    <button class="search-btn" @click="handleFilterSearch">筛选</button>
    <button class="reset-btn" @click="handleReset">重置</button>
    <StrategySave :active-filters="currentFilters" @load="handleLoadStrategy" />
  </aside>
</template>

<style scoped>
.sidebar {
  width: 270px; flex-shrink: 0; background: var(--bg-surface); padding: 20px 16px;
  border-right: 1px solid var(--border); overflow-y: auto; height: 100vh;
  box-shadow: 1px 0 8px var(--shadow);
}
.sidebar-title {
  font-size: 16px; font-weight: 800; margin-bottom: 16px; color: var(--text-primary);
  letter-spacing: -0.01em;
}
.keyword-search { display: flex; gap: 6px; margin-bottom: 16px; }
.keyword-input-wrap { position: relative; flex: 1; }
.keyword-input {
  width: 100%; padding: 7px 30px 7px 12px; border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm); background: var(--bg-alt); color: var(--text-primary);
  font-size: 13px; outline: none; transition: all var(--transition);
}
.keyword-input:focus {
  border-color: var(--accent); background: var(--bg-surface);
  box-shadow: 0 0 0 3px rgba(59,130,246,0.12);
}
.keyword-input::placeholder { color: var(--text-muted); }
.keyword-clear {
  position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
  background: none; border: none; color: var(--text-muted); cursor: pointer;
  font-size: 14px; padding: 2px 4px; line-height: 1; border-radius: 50%;
  width: 18px; height: 18px; display: flex; align-items: center; justify-content: center;
}
.keyword-clear:hover { background: var(--border); color: var(--text-secondary); }
.keyword-btn {
  padding: 7px 14px; border: none; border-radius: var(--radius-sm);
  background: var(--accent); color: white; font-size: 13px; font-weight: 500;
  cursor: pointer; white-space: nowrap; flex-shrink: 0;
  transition: all var(--transition);
}
.keyword-btn:hover { background: var(--accent-hover); box-shadow: 0 2px 8px rgba(59,130,246,0.3); }
.search-btn {
  width: 100%; padding: 9px; background: var(--accent); color: white; border: none;
  border-radius: var(--radius-sm); font-size: 14px; font-weight: 600; cursor: pointer;
  margin-bottom: 8px; transition: all var(--transition);
}
.search-btn:hover { background: var(--accent-hover); box-shadow: 0 4px 12px rgba(59,130,246,0.35); }
.reset-btn {
  width: 100%; padding: 7px; background: transparent; color: var(--text-secondary);
  border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  font-size: 12px; cursor: pointer; font-weight: 500; transition: all var(--transition);
}
.reset-btn:hover { background: var(--bg-hover); color: var(--text-primary); border-color: var(--text-muted); }
.watchlist-toggle {
  display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-secondary);
  cursor: pointer; padding: 8px 0; margin-bottom: 8px; font-weight: 500;
}
.watchlist-toggle input[type="checkbox"] {
  cursor: pointer; width: 16px; height: 16px; accent-color: var(--accent);
}
</style>
