<script setup lang="ts">
import { ref, computed } from 'vue'
import ResultHeader from './ResultHeader.vue'
import Pagination from './Pagination.vue'

const props = defineProps<{
  items: Record<string, unknown>[]
  total: number
  loading: boolean
  currentPage: number
  sortBy: string
  sortOrder: string
  favorites: Set<string>
}>()

const emit = defineEmits<{
  'page-change': [page: number]
  'sort-change': [field: string]
  'row-click': [code: string]
  'toggle-favorite': [code: string]
}>()

const ALL_COLUMNS = [
  { key: 'favorite', label: '', width: '28px', sortable: false },
  { key: 'code', label: '代码', width: '90px', sortable: false },
  { key: 'name', label: '名称', width: '100px', sortable: false },
  { key: 'close', label: '最新价', width: '70px', sortable: true },
  { key: 'volume', label: '成交量', width: '80px', sortable: false },
  { key: 'turnover_rate', label: '换手率(%)', width: '82px', sortable: true },
  { key: 'pe_ttm', label: 'PE', width: '70px', sortable: true },
  { key: 'pb', label: 'PB', width: '70px', sortable: true },
  { key: 'roe', label: 'ROE', width: '70px', sortable: true },
  { key: 'market_cap', label: '市值(亿)', width: '90px', sortable: true },
  { key: 'dividend_yield', label: '股息率', width: '70px', sortable: false },
  { key: 'revenue_growth_3y', label: '营收增长(%)', width: '90px', sortable: true },
  { key: 'change_pct', label: '涨跌幅(%)', width: '80px', sortable: true },
  { key: 'volume_ratio', label: '量比', width: '60px', sortable: false },
]

const STORAGE_KEY = 'stockScreenerColumns'

function loadVisibility(): Record<string, boolean> {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) return JSON.parse(stored)
  } catch { /* ignore */ }
  const defaults: Record<string, boolean> = {}
  // Default dividend_yield and revenue_growth_3y to hidden (Sina API doesn't provide them)
  const hiddenByDefault = new Set(['dividend_yield', 'revenue_growth_3y'])
  ALL_COLUMNS.forEach(c => { defaults[c.key] = !hiddenByDefault.has(c.key) })
  return defaults
}

const columnVisibility = ref<Record<string, boolean>>(loadVisibility())
const columnPickerOpen = ref(false)

const visibleColumns = computed(() => ALL_COLUMNS.filter(c => columnVisibility.value[c.key] !== false))

function toggleColumnPicker() {
  columnPickerOpen.value = !columnPickerOpen.value
}

function toggleColumn(key: string) {
  columnVisibility.value[key] = !columnVisibility.value[key]
  localStorage.setItem(STORAGE_KEY, JSON.stringify(columnVisibility.value))
}

function sortIndicator(key: string): string {
  if (props.sortBy !== key) return ''
  return props.sortOrder === 'asc' ? ' ▲' : ' ▼'
}

function fmt(val: unknown, key: string): string {
  if (val === null || val === undefined) return '-'
  const n = Number(val)
  if (isNaN(n)) return String(val)
  if (key === 'roe' || key === 'dividend_yield' || key === 'turnover_rate' || key === 'revenue_growth_3y') return n.toFixed(1) + '%'
  if (key === 'market_cap') return n >= 10000 ? (n / 10000).toFixed(1) + '万亿' : n.toFixed(0)
  if (key === 'pe_ttm' || key === 'pb' || key === 'close') return n.toFixed(2)
  if (key === 'volume') return n >= 1e8 ? (n / 1e8).toFixed(1) + '亿' : n >= 1e4 ? (n / 1e4).toFixed(0) + '万' : n.toFixed(0)
  if (key === 'change_pct') return n.toFixed(2) + '%'
  if (key === 'volume_ratio') return n.toFixed(2)
  return String(val)
}
</script>

<template>
  <div class="stock-table-container">
    <ResultHeader :total="total" :loading="loading" :items="items" :visible-cols="visibleColumns.map(c => c.key)" />
    <div class="column-picker-wrap">
      <button class="column-picker-btn" @click="toggleColumnPicker">列设置 ▾</button>
      <div v-if="columnPickerOpen" class="column-picker-dropdown" @mouseleave="columnPickerOpen = false">
        <label v-for="col in ALL_COLUMNS" :key="col.key" class="column-picker-item" v-show="col.key !== 'favorite'">
          <input type="checkbox" :checked="columnVisibility[col.key] !== false" @change="toggleColumn(col.key)" />
          {{ col.label }}
        </label>
      </div>
    </div>
    <table class="stock-table">
      <thead>
        <tr>
          <th
            v-for="col in visibleColumns" :key="col.key"
            :style="{ width: col.width }"
            :class="{ sortable: col.sortable }"
            @click="col.sortable && emit('sort-change', col.key)"
          >
            {{ col.label }}<span class="sort-indicator">{{ sortIndicator(col.key) }}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="items.length === 0 && !loading">
          <td :colspan="visibleColumns.length" class="empty">暂无数据，请设置筛选条件</td>
        </tr>
        <tr v-for="item in items" :key="item.code as string"
          @click="emit('row-click', item.code as string)" class="data-row">
          <td v-for="col in visibleColumns" :key="col.key">
            <span v-if="col.key === 'favorite'" class="star-btn" :class="{ active: favorites.has(item.code as string) }" @click.stop="emit('toggle-favorite', item.code as string)">
              {{ favorites.has(item.code as string) ? '★' : '☆' }}
            </span>
            <span v-else :class="{ 'stock-code': col.key === 'code' }">{{ col.key === 'code' ? item[col.key] : fmt(item[col.key], col.key) }}</span>
          </td>
        </tr>
      </tbody>
    </table>
    <Pagination :total="total" :page-size="50" :model-value="currentPage" @page-change="(p: number) => emit('page-change', p)" />
  </div>
</template>

<style scoped>
.stock-table-container { flex: 1; padding: 0 20px; overflow-y: auto; }
.column-picker-wrap { position: relative; display: inline-block; margin-bottom: 4px; }
.column-picker-btn {
  padding: 2px 8px; border: 1px solid var(--border-strong); border-radius: 4px;
  background: var(--bg-surface); color: var(--text-secondary); font-size: 11px; cursor: pointer;
}
.column-picker-btn:hover { background: var(--bg-hover); }
.column-picker-dropdown {
  position: absolute; top: 100%; left: 0; z-index: 50;
  background: var(--bg-surface); border: 1px solid var(--border-strong);
  border-radius: 6px; padding: 6px 0; min-width: 150px; box-shadow: 0 4px 12px var(--shadow);
}
.column-picker-item {
  display: flex; align-items: center; gap: 6px; padding: 4px 10px;
  font-size: 12px; color: var(--text-primary); cursor: pointer;
}
.column-picker-item:hover { background: var(--bg-hover); }
.column-picker-item input { cursor: pointer; }
.stock-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.stock-table th {
  text-align: left; padding: 8px 6px; border-bottom: 2px solid var(--border);
  color: var(--text-secondary); font-weight: 600; position: sticky; top: 0; background: var(--bg-surface);
  user-select: none;
}
.stock-table th.sortable { cursor: pointer; }
.stock-table th.sortable:hover { color: var(--accent); }
.sort-indicator { color: var(--accent); font-size: 11px; }
.stock-table td { padding: 6px 6px; border-bottom: 1px solid var(--border); color: var(--text-primary); }
.data-row { cursor: pointer; }
.data-row:hover { background: var(--bg-hover); }
.stock-code { color: var(--accent); font-weight: 500; }
.empty { text-align: center; color: var(--text-muted); padding: 40px 0; }
.star-btn { cursor: pointer; color: var(--text-muted); font-size: 14px; }
.star-btn.active { color: #f59e0b; }
.star-btn:hover { color: #f59e0b; }
</style>
