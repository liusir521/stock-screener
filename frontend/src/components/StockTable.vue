<script setup lang="ts">
import ResultHeader from './ResultHeader.vue'
import Pagination from './Pagination.vue'

defineProps<{
  items: Record<string, unknown>[]
  total: number
  loading: boolean
}>()

const emit = defineEmits<{
  'page-change': [page: number]
  'sort-change': [field: string]
  'row-click': [code: string]
}>()

const columns = [
  { key: 'code', label: '代码', width: '90px' },
  { key: 'name', label: '名称', width: '100px' },
  { key: 'pe_ttm', label: 'PE', width: '70px' },
  { key: 'pb', label: 'PB', width: '70px' },
  { key: 'roe', label: 'ROE', width: '70px' },
  { key: 'market_cap', label: '市值(亿)', width: '90px' },
  { key: 'dividend_yield', label: '股息率', width: '70px' },
]

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
    <ResultHeader :total="total" :loading="loading" :items="items" @sort-change="(f: string) => emit('sort-change', f)" />
    <table class="stock-table">
      <thead>
        <tr>
          <th v-for="col in columns" :key="col.key" :style="{ width: col.width }">{{ col.label }}</th>
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
    <Pagination :total="total" :page-size="50" @page-change="(p: number) => emit('page-change', p)" />
  </div>
</template>

<style scoped>
.stock-table-container { flex: 1; padding: 0 20px; overflow-y: auto; }
.stock-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.stock-table th {
  text-align: left; padding: 8px 6px; border-bottom: 2px solid #475569;
  color: #94a3b8; font-weight: 600; position: sticky; top: 0; background: #0f172a;
}
.stock-table td { padding: 6px 6px; border-bottom: 1px solid #1e293b; color: #e2e8f0; }
.data-row { cursor: pointer; }
.data-row:hover { background: #1e293b; }
.stock-code { color: #60a5fa; font-weight: 500; }
.empty { text-align: center; color: #64748b; padding: 40px 0; }
</style>
