<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'

const PAGE_SIZE = 20

const emit = defineEmits<{ 'select-stock': [code: string] }>()
const sectors = ref<Record<string, unknown>[]>([])
const loading = ref(false)

const detailStocks = ref<Record<string, unknown>[]>([])
const detailLoading = ref(false)
const detailTitle = ref('')
const detailPage = ref(1)
const detailTotal = ref(0)
const detailParams = ref<Record<string, string> | null>(null)
const detailSortBy = ref('')
const detailSortOrder = ref<'asc' | 'desc'>('asc')

const DETAIL_COLUMNS = [
  { key: 'code', label: '代码', sortable: true },
  { key: 'name', label: '名称', sortable: true },
  { key: 'change_pct', label: '涨跌幅', sortable: true },
  { key: 'pe_ttm', label: 'PE', sortable: true },
  { key: 'pb', label: 'PB', sortable: true },
  { key: 'roe', label: 'ROE', sortable: true },
  { key: 'market_cap', label: '市值(亿)', sortable: true },
  { key: 'turnover_rate', label: '换手率', sortable: true },
  { key: 'volume_ratio', label: '量比', sortable: true },
]

function handleDetailSort(key: string) {
  if (detailSortBy.value === key) {
    if (detailSortOrder.value === 'asc') detailSortOrder.value = 'desc'
    else { detailSortBy.value = ''; detailSortOrder.value = 'asc'; return }
  } else {
    detailSortBy.value = key
    detailSortOrder.value = 'asc'
  }
  fetchDetailStocksPage(1)
}

function sortIndicator(key: string): string {
  if (detailSortBy.value !== key) return ''
  return detailSortOrder.value === 'asc' ? ' ▴' : ' ▾'
}

onMounted(async () => {
  await load()
})

async function load() {
  loading.value = true
  try {
    const data = await api.getSectors()
    sectors.value = data.sectors
  } finally {
    loading.value = false
  }
}

async function openSectorStocks(row: Record<string, unknown>) {
  const code = String(row.code || '')
  const name = String(row.name || '')
  if (!code && !name) return
  const params: Record<string, string> = { page_size: String(PAGE_SIZE) }
  if (code) params.industry = code
  params.industry_name = name
  detailParams.value = params
  detailTitle.value = name
  detailSortBy.value = ''
  detailSortOrder.value = 'asc'
  detailLoading.value = true
  try {
    await fetchDetailStocksPage(1)
  } finally {
    detailLoading.value = false
  }
}

async function fetchDetailStocksPage(page: number) {
  if (!detailParams.value) return
  detailLoading.value = true
  try {
    const params: Record<string, string> = { ...detailParams.value, page: String(page) }
    if (detailSortBy.value) {
      params.sort_by = detailSortBy.value
      params.order = detailSortOrder.value
    }
    const data = await api.getStocks(params)
    detailStocks.value = data.items
    detailTotal.value = data.total
    detailPage.value = page
  } finally {
    detailLoading.value = false
  }
}

const detailTotalPages = computed(() => Math.max(1, Math.ceil(detailTotal.value / PAGE_SIZE)))

function closeDetailStocks() {
  detailTitle.value = ''
  detailParams.value = null
  detailSortBy.value = ''
  detailSortOrder.value = 'asc'
}

function handleStockClick(st: Record<string, unknown>) {
  const code = String(st.code || '')
  if (code) emit('select-stock', code)
}

function fmt(val: unknown): string {
  if (val === null || val === undefined) return '-'
  return String(val)
}

function changeClass(val: unknown): string {
  const n = Number(val)
  if (isNaN(n) || n === 0) return ''
  return n > 0 ? 'num-up' : 'num-down'
}

const COLUMNS = [
  { key: 'name', label: '板块名称' },
  { key: 'stock_count', label: '成分股数' },
  { key: 'change_pct', label: '涨跌幅(%)' },
  { key: 'lead_stock', label: '领涨股票' },
  { key: 'lead_stock_change', label: '领涨涨跌幅(%)' },
]
</script>

<template>
  <div class="sector-ranking">
    <div class="sr-header">
      <span class="sr-title">板块涨跌排名</span>
      <button class="sr-refresh-btn" :disabled="loading" @click="load">
        {{ loading ? '加载中...' : '刷新' }}
      </button>
    </div>
    <div v-if="loading && !sectors.length" class="sr-loading">加载中...</div>
    <div v-else-if="!sectors.length" class="sr-empty">暂无数据</div>
    <div v-else class="sr-table-wrap">
      <table class="sr-table">
        <thead>
          <tr>
            <th v-for="col in COLUMNS" :key="col.key">{{ col.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in sectors" :key="i" @click="openSectorStocks(row)">
            <td v-for="col in COLUMNS" :key="col.key" :class="col.key === 'change_pct' || col.key === 'lead_stock_change' ? changeClass(row[col.key]) : ''">
              {{ fmt(row[col.key]) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Sector Stocks Detail Dialog -->
    <div v-if="detailTitle" class="sr-overlay" @click.self="closeDetailStocks">
      <div class="sr-dialog">
        <div class="sr-dialog-header">
          <h4>{{ detailTitle }} — 成分股</h4>
          <button class="sr-dialog-close" @click="closeDetailStocks">✕</button>
        </div>
        <div class="sr-summary-bar">
          共 <strong>{{ detailTotal }}</strong> 只股票
        </div>
        <div v-if="detailLoading" class="sr-loading">加载中...</div>
        <div v-else-if="!detailStocks.length" class="sr-empty">暂无数据</div>
        <table v-else class="sr-detail-table">
          <thead>
            <tr>
              <th v-for="col in DETAIL_COLUMNS" :key="col.key" :class="{ 'sortable-th': true, 'active-sort': detailSortBy === col.key }" @click="handleDetailSort(col.key)">
                {{ col.label }}{{ sortIndicator(col.key) }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="st in detailStocks" :key="String(st.code)" class="clickable-row" @click="handleStockClick(st)">
              <td class="td-code">{{ fmt(st.code) }}</td>
              <td>{{ fmt(st.name) }}</td>
              <td :class="changeClass(st.change_pct)">{{ fmt(st.change_pct) !== '-' ? (Number(st.change_pct) > 0 ? '+' : '') + Number(st.change_pct).toFixed(2) + '%' : '-' }}</td>
              <td>{{ fmt(st.pe_ttm) !== '-' ? Number(st.pe_ttm).toFixed(1) : '-' }}</td>
              <td>{{ fmt(st.pb) !== '-' ? Number(st.pb).toFixed(2) : '-' }}</td>
              <td>{{ fmt(st.roe) !== '-' ? Number(st.roe).toFixed(1) + '%' : '-' }}</td>
              <td>{{ fmt(st.market_cap) !== '-' ? Number(st.market_cap).toFixed(0) : '-' }}</td>
              <td>{{ fmt(st.turnover_rate) !== '-' ? Number(st.turnover_rate).toFixed(1) + '%' : '-' }}</td>
              <td>{{ fmt(st.volume_ratio) !== '-' ? Number(st.volume_ratio).toFixed(1) : '-' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="detailTotalPages > 1" class="sr-pagination">
          <button :disabled="detailPage <= 1" @click="fetchDetailStocksPage(detailPage - 1)">上一页</button>
          <span class="sr-page-info">{{ detailPage }} / {{ detailTotalPages }}</span>
          <button :disabled="detailPage >= detailTotalPages" @click="fetchDetailStocksPage(detailPage + 1)">下一页</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sector-ranking { padding: 20px 24px; }
.sr-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.sr-title { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.sr-refresh-btn {
  padding: 5px 14px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  background: var(--bg-surface); color: var(--text-secondary); font-size: 12px; font-weight: 500;
  cursor: pointer; transition: all var(--transition);
}
.sr-refresh-btn:hover { background: var(--bg-hover); color: var(--text-primary); border-color: var(--accent); }
.sr-loading, .sr-empty { text-align: center; padding: 40px 0; color: var(--text-muted); font-size: 13px; }
.sr-table-wrap { max-height: calc(100vh - 180px); overflow: auto; border: 1px solid var(--border); border-radius: var(--radius); }
.sr-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.sr-table thead { position: sticky; top: 0; z-index: 1; }
.sr-table th {
  background: var(--bg-alt); color: var(--text-secondary); font-weight: 600;
  padding: 8px 12px; text-align: right; border-bottom: 2px solid var(--border);
  white-space: nowrap; font-size: 12px;
}
.sr-table th:first-child { text-align: left; }
.sr-table td {
  padding: 7px 12px; text-align: right; border-bottom: 1px solid var(--border);
  color: var(--text-primary); white-space: nowrap;
}
.sr-table td:first-child { text-align: left; color: var(--accent); font-weight: 500; cursor: pointer; }
.sr-table tbody tr { transition: background var(--transition); cursor: pointer; }
.sr-table tbody tr:hover { background: var(--accent-light); }
.num-up { color: var(--red) !important; font-weight: 500; }
.num-down { color: var(--green) !important; font-weight: 500; }

/* Detail dialog */
.sr-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 200;
  display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(2px);
}
.sr-dialog {
  background: var(--bg-surface); padding: 24px; border-radius: var(--radius); width: 1100px; max-width: 96vw;
  max-height: 85vh; overflow-y: auto;
  box-shadow: 0 16px 48px var(--shadow-lg);
  animation: dialogIn 0.2s ease;
}
@keyframes dialogIn {
  from { transform: scale(0.95); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
.sr-dialog-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.sr-dialog-header h4 { margin-bottom: 0; font-size: 15px; font-weight: 700; color: var(--text-primary); }
.sr-dialog-close {
  background: none; border: none; color: var(--text-muted); cursor: pointer;
  font-size: 18px; padding: 2px 6px; border-radius: var(--radius-sm); line-height: 1;
  transition: all var(--transition);
}
.sr-dialog-close:hover { background: var(--bg-hover); color: var(--text-primary); }
.sr-summary-bar { font-size: 13px; color: var(--text-secondary); margin-bottom: 16px; padding: 10px 14px; background: var(--bg-alt); border-radius: var(--radius); border: 1px solid var(--border); }
.sr-summary-bar strong { color: var(--accent); }
.sr-detail-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.sr-detail-table th {
  background: var(--bg-alt); color: var(--text-secondary); font-weight: 600;
  padding: 6px 10px; text-align: right; border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 1; font-size: 11px;
}
.sr-detail-table th:first-child, .sr-detail-table td:first-child { text-align: left; }
.sortable-th { cursor: pointer; user-select: none; transition: color var(--transition); }
.sortable-th:hover { color: var(--accent); }
.active-sort { color: var(--accent); }
.sr-detail-table td {
  padding: 5px 10px; text-align: right; border-bottom: 1px solid var(--border);
  color: var(--text-primary); white-space: nowrap;
}
.sr-detail-table tbody tr:hover { background: var(--accent-light); }
.sr-detail-table .td-code { font-family: monospace; color: var(--accent); }
.clickable-row { cursor: pointer; }

/* Pagination */
.sr-pagination {
  display: flex; align-items: center; justify-content: center; gap: 12px;
  margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border);
}
.sr-pagination button {
  padding: 5px 14px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  background: var(--bg-alt); color: var(--text-secondary); font-size: 12px; font-weight: 500;
  cursor: pointer; transition: all var(--transition);
}
.sr-pagination button:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); background: var(--accent-light); }
.sr-pagination button:disabled { opacity: 0.4; cursor: default; }
.sr-page-info { font-size: 12px; color: var(--text-secondary); font-weight: 500; min-width: 60px; text-align: center; }
</style>
