<script setup lang="ts">
import ResultHeader from './ResultHeader.vue'
import Pagination from './Pagination.vue'

const props = defineProps<{
  items: Record<string, unknown>[]
  total: number
  loading: boolean
  currentPage: number
  sortBy: string
  sortOrder: string
}>()

const emit = defineEmits<{
  'page-change': [page: number]
  'sort-change': [field: string]
  'row-click': [code: string]
}>()

const columns = [
  { key: 'code', label: '代码', width: '90px', sortable: false },
  { key: 'name', label: '名称', width: '100px', sortable: false },
  { key: 'pe_ttm', label: 'PE', width: '70px', sortable: true },
  { key: 'pb', label: 'PB', width: '70px', sortable: true },
  { key: 'roe', label: 'ROE', width: '70px', sortable: true },
  { key: 'market_cap', label: '市值(亿)', width: '90px', sortable: true },
  { key: 'dividend_yield', label: '股息率', width: '70px', sortable: false },
]

function sortIndicator(key: string): string {
  if (props.sortBy !== key) return ''
  return props.sortOrder === 'asc' ? ' ▲' : ' ▼'
}

function fmt(val: unknown, key: string): string {
  if (val === null || val === undefined) return '-'
  const n = Number(val)
  if (isNaN(n)) return String(val)
  if (key === 'roe' || key === 'dividend_yield') return n.toFixed(1) + '%'
  if (key === 'market_cap') return n >= 10000 ? (n / 10000).toFixed(1) + '万亿' : n.toFixed(0)
  if (key === 'pe_ttm' || key === 'pb') return n.toFixed(1)
  return String(val)
}
</script>

<template>
  <div class="stock-table-container">
    <ResultHeader :total="total" :loading="loading" :items="items" />
    <table class="stock-table">
      <thead>
        <tr>
          <th
            v-for="col in columns" :key="col.key"
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
          <td :colspan="columns.length" class="empty">暂无数据，请设置筛选条件</td>
        </tr>
        <tr v-for="item in items" :key="item.code as string"
          @click="emit('row-click', item.code as string)" class="data-row">
          <td v-for="col in columns" :key="col.key">
            <span :class="{ 'stock-code': col.key === 'code' }">{{ col.key === 'code' ? item[col.key] : fmt(item[col.key], col.key) }}</span>
          </td>
        </tr>
      </tbody>
    </table>
    <Pagination :total="total" :page-size="50" :model-value="currentPage" @page-change="(p: number) => emit('page-change', p)" />
  </div>
</template>

<style scoped>
.stock-table-container { flex: 1; padding: 0 20px; overflow-y: auto; }
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
</style>
