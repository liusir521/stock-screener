<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'

const emit = defineEmits<{ 'apply-strategy': [filters: Record<string, unknown>]; 'select-stock': [code: string] }>()

interface StrategyResult {
  name: string
  description: string
  filters: Record<string, unknown>
  match_count: number
  top_stocks: Record<string, unknown>[]
  preset: boolean
}

interface Intersection {
  strategies: string[]
  count: number
  sample_codes: string[]
}

const dashboard = ref<{ total_stocks: number; strategies: StrategyResult[]; intersections: Intersection[] }>({
  total_stocks: 0, strategies: [], intersections: [],
})
const loading = ref(false)
const viewMode = ref<'dashboard' | 'compare' | 'intersect'>('dashboard')

const showCreate = ref(false)
const createName = ref('')
const createDesc = ref('')
const createFilters = ref<Record<string, string>>({ sort_by: '', order: 'desc', exclude_st: 'true' })

const SORT_OPTIONS = [
  { value: '', label: '默认' },
  { value: 'pe_ttm', label: 'PE (TTM)' },
  { value: 'pb', label: 'PB' },
  { value: 'roe', label: 'ROE' },
  { value: 'market_cap', label: '市值' },
  { value: 'change_pct', label: '涨跌幅' },
  { value: 'volume_ratio', label: '量比' },
  { value: 'turnover_rate', label: '换手率' },
  { value: 'dividend_yield', label: '股息率' },
  { value: 'revenue_growth_3y', label: '营收增长' },
  { value: 'close', label: '收盘价' },
]

const MARKET_OPTIONS = [
  { value: '', label: '全部' },
  { value: 'sh_sz', label: '沪深A股' },
  { value: 'chinext', label: '创业板' },
  { value: 'star', label: '科创板' },
  { value: 'bse', label: '北交所' },
]

onMounted(async () => { await load() })

async function load() {
  loading.value = true
  try {
    dashboard.value = await api.getStrategyDashboard()
  } finally {
    loading.value = false
  }
}

const PAGE_SIZE = 20

const detailStocks = ref<Record<string, unknown>[]>([])
const detailStocksLoading = ref(false)
const detailStocksTitle = ref('')
const detailStocksPage = ref(1)
const detailStocksTotal = ref(0)
const detailStocksFilters = ref<Record<string, unknown> | null>(null)
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

async function openStrategyStocks(strategy: StrategyResult) {
  detailStocksLoading.value = true
  detailStocksTitle.value = strategy.name
  detailStocksFilters.value = strategy.filters
  detailStocksPage.value = 1
  detailSortBy.value = ''
  detailSortOrder.value = 'asc'
  try {
    await fetchDetailStocksPage(1)
  } finally {
    detailStocksLoading.value = false
  }
}

async function fetchDetailStocksPage(page: number) {
  if (!detailStocksFilters.value) return
  detailStocksLoading.value = true
  try {
    const params: Record<string, string> = { page: String(page), page_size: String(PAGE_SIZE) }
    for (const [k, v] of Object.entries(detailStocksFilters.value)) {
      if (v !== undefined && v !== null && v !== '') params[k] = String(v)
    }
    if (detailSortBy.value) {
      params.sort_by = detailSortBy.value
      params.order = detailSortOrder.value
    }
    const data = await api.getStocks(params)
    detailStocks.value = data.items
    detailStocksTotal.value = data.total
    detailStocksPage.value = page
  } finally {
    detailStocksLoading.value = false
  }
}

const detailTotalPages = computed(() => Math.max(1, Math.ceil(detailStocksTotal.value / PAGE_SIZE)))

function closeDetailStocks() {
  detailStocksTitle.value = ''
  detailStocksFilters.value = null
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

function getTopStockNames(strategy: StrategyResult): string[] {
  return strategy.top_stocks.slice(0, 3).map(s => String(s.name || s.code || ''))
}

const showIntersect = ref(false)
const intersectLoading = ref(false)
const intersectPage = ref(1)
const intersectSortBy = ref('change_pct')
const intersectSortOrder = ref<'asc' | 'desc'>('desc')
const intersectResult = ref<{ stocks: Record<string, unknown>[]; strategies: string[]; count: number }>({ stocks: [], strategies: [], count: 0 })

function sortedIntersectStocks() {
  const arr = [...intersectResult.value.stocks]
  if (!intersectSortBy.value) return arr
  return arr.sort((a, b) => {
    const va = Number(a[intersectSortBy.value]) || 0
    const vb = Number(b[intersectSortBy.value]) || 0
    return intersectSortOrder.value === 'asc' ? va - vb : vb - va
  })
}

const intersectPageStocks = computed(() => {
  const sorted = sortedIntersectStocks()
  const start = (intersectPage.value - 1) * PAGE_SIZE
  return sorted.slice(start, start + PAGE_SIZE)
})
const intersectTotalPages = computed(() => Math.max(1, Math.ceil(intersectResult.value.stocks.length / PAGE_SIZE)))

function handleIntersectSort(key: string) {
  if (intersectSortBy.value === key) {
    if (intersectSortOrder.value === 'asc') intersectSortOrder.value = 'desc'
    else { intersectSortBy.value = ''; intersectSortOrder.value = 'asc'; return }
  } else {
    intersectSortBy.value = key
    intersectSortOrder.value = 'asc'
  }
  intersectPage.value = 1
}

function intersectSortIndicator(key: string): string {
  if (intersectSortBy.value !== key) return ''
  return intersectSortOrder.value === 'asc' ? ' ▴' : ' ▾'
}

async function openIntersection(names: string[]) {
  intersectLoading.value = true
  intersectPage.value = 1
  intersectSortBy.value = 'change_pct'
  intersectSortOrder.value = 'desc'
  showIntersect.value = true
  try {
    intersectResult.value = await api.getStrategyIntersection(names)
  } finally {
    intersectLoading.value = false
  }
}

function closeIntersection() {
  showIntersect.value = false
  intersectResult.value = { stocks: [], strategies: [], count: 0 }
}

async function handleCreate() {
  const name = createName.value.trim()
  if (!name) return
  const filters: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(createFilters.value)) {
    if (v !== undefined && v !== null && v !== '') filters[k] = v === 'true' ? true : isNaN(Number(v)) ? v : Number(v)
  }
  await api.saveStrategy(name, filters as Record<string, string>, createDesc.value.trim())
  createName.value = ''
  createDesc.value = ''
  createFilters.value = { sort_by: '', order: 'desc', exclude_st: 'true' }
  showCreate.value = false
  await load()
}

async function handleDelete(name: string) {
  if (!confirm(`确定要删除策略 "${name}" 吗？`)) return
  try {
    await api.deleteStrategy(name)
    await load()
  } catch {
    alert('删除失败')
  }
}
</script>

<template>
  <div class="strategy-dashboard">
    <div class="sd-header">
      <span class="sd-title">策略分析</span>
      <div class="sd-header-right">
        <div class="sd-view-tabs">
          <button :class="['sd-view-btn', { active: viewMode === 'dashboard' }]" @click="viewMode = 'dashboard'">总览</button>
          <button :class="['sd-view-btn', { active: viewMode === 'compare' }]" @click="viewMode = 'compare'">对比</button>
          <button :class="['sd-view-btn', { active: viewMode === 'intersect' }]" @click="viewMode = 'intersect'">交集</button>
        </div>
        <button class="sd-create-btn" @click="showCreate = true">＋ 新建策略</button>
        <button class="sd-refresh-btn" :disabled="loading" @click="load">
          {{ loading ? '加载中...' : '刷新' }}
        </button>
      </div>
    </div>

    <div v-if="loading && !dashboard.strategies.length" class="sd-loading">加载中...</div>

    <!-- Dashboard: Summary Cards -->
    <template v-else-if="viewMode === 'dashboard'">
      <div class="sd-summary-bar">
        全市场 <strong>{{ dashboard.total_stocks }}</strong> 只股票，
        <strong>{{ dashboard.strategies.length }}</strong> 个策略
      </div>
      <div class="sd-cards">
        <div
          v-for="s in dashboard.strategies" :key="s.name"
          class="sd-card"
          @click="openStrategyStocks(s)"
        >
          <div class="sd-card-header">
            <span class="sd-card-name">{{ s.name }}</span>
            <span class="sd-card-count">{{ s.match_count }} 只</span>
            <button v-if="!s.preset" class="sd-card-delete" @click.stop="handleDelete(s.name)" title="删除策略">✕</button>
          </div>
          <div v-if="s.description" class="sd-card-desc">{{ s.description }}</div>
          <div class="sd-card-stocks" v-if="s.top_stocks.length">
            <span
              v-for="st in s.top_stocks.slice(0, 5)" :key="String(st.code)"
              class="sd-stock-tag"
              :class="changeClass(st.change_pct)"
            >
              {{ st.name || st.code }}
              <small>({{ fmt(st.change_pct) !== '-' ? (Number(st.change_pct) > 0 ? '+' : '') + Number(st.change_pct).toFixed(1) + '%' : '-' }})</small>
            </span>
          </div>
          <div v-else class="sd-card-empty">暂无匹配股票</div>
        </div>
      </div>
    </template>

    <!-- Compare: Side-by-side top stocks -->
    <template v-else-if="viewMode === 'compare'">
      <div class="sd-compare-grid">
        <div v-for="s in dashboard.strategies" :key="s.name" class="sd-compare-col">
          <h4 class="sd-compare-title" @click="openStrategyStocks(s)">{{ s.name }}</h4>
          <div class="sd-compare-count">{{ s.match_count }} 只</div>
          <table class="sd-compare-table" v-if="s.top_stocks.length">
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th>涨跌幅</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="st in s.top_stocks" :key="String(st.code)" class="clickable-row" @click="handleStockClick(st)">
                <td class="td-code">{{ fmt(st.code) }}</td>
                <td>{{ fmt(st.name) }}</td>
                <td :class="changeClass(st.change_pct)">{{ fmt(st.change_pct) !== '-' ? (Number(st.change_pct) > 0 ? '+' : '') + Number(st.change_pct).toFixed(2) + '%' : '-' }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="sd-card-empty">暂无数据</div>
        </div>
      </div>
    </template>

    <!-- Intersect: Strategy overlaps -->
    <template v-else-if="viewMode === 'intersect'">
      <div class="sd-summary-bar">
        策略交集分析 — 展示同时满足多个策略的股票数量
      </div>
      <div v-if="!dashboard.intersections.length" class="sd-empty">暂无交集数据</div>
      <div v-else class="sd-intersect-list">
        <div
          v-for="(x, i) in dashboard.intersections" :key="i"
          class="sd-intersect-row"
          @click="openIntersection(x.strategies)"
        >
          <span class="sd-intersect-names">{{ x.strategies.join(' + ') }}</span>
          <span class="sd-intersect-count">{{ x.count }} 只</span>
          <span class="sd-intersect-samples">{{ x.sample_codes.join(', ') }}</span>
        </div>
      </div>
    </template>

    <!-- Create Strategy Dialog -->
    <div v-if="showCreate" class="sd-overlay" @click.self="showCreate = false">
      <div class="sd-dialog">
        <h4>新建自定义策略</h4>
        <input v-model="createName" placeholder="策略名称（必填）" class="sd-input" />
        <textarea v-model="createDesc" placeholder="策略描述（可选）" class="sd-textarea" rows="2" />
        <div class="sd-filter-grid">
          <div class="sd-filter-field">
            <label>市场</label>
            <select v-model="createFilters.market">
              <option v-for="m in MARKET_OPTIONS" :key="m.value" :value="m.value">{{ m.label }}</option>
            </select>
          </div>
          <div class="sd-filter-field sd-filter-field-2col">
            <label>PE 范围</label>
            <div class="sd-range-row">
              <input v-model="createFilters.pe_min" placeholder="最小" type="number" step="1" />
              <span class="sd-range-sep">–</span>
              <input v-model="createFilters.pe_max" placeholder="最大" type="number" step="1" />
            </div>
          </div>
          <div class="sd-filter-field sd-filter-field-2col">
            <label>PB 范围</label>
            <div class="sd-range-row">
              <input v-model="createFilters.pb_min" placeholder="最小" type="number" step="0.1" />
              <span class="sd-range-sep">–</span>
              <input v-model="createFilters.pb_max" placeholder="最大" type="number" step="0.1" />
            </div>
          </div>
          <div class="sd-filter-field">
            <label>ROE 最低 (%)</label>
            <input v-model="createFilters.roe_min" placeholder="0" type="number" step="0.1" />
          </div>
          <div class="sd-filter-field sd-filter-field-2col">
            <label>市值范围（亿）</label>
            <div class="sd-range-row">
              <input v-model="createFilters.market_cap_min" placeholder="最小" type="number" step="1" />
              <span class="sd-range-sep">–</span>
              <input v-model="createFilters.market_cap_max" placeholder="最大" type="number" step="1" />
            </div>
          </div>
          <div class="sd-filter-field">
            <label>股息率最低 (%)</label>
            <input v-model="createFilters.dividend_yield_min" placeholder="0" type="number" step="0.1" />
          </div>
          <div class="sd-filter-field">
            <label>营收增长最低 (%)</label>
            <input v-model="createFilters.revenue_growth_min" placeholder="0" type="number" step="1" />
          </div>
          <div class="sd-filter-field">
            <label>换手率最低 (%)</label>
            <input v-model="createFilters.turnover_rate_min" placeholder="0" type="number" step="0.1" />
          </div>
          <div class="sd-filter-field sd-filter-field-2col">
            <label>涨跌幅范围 (%)</label>
            <div class="sd-range-row">
              <input v-model="createFilters.change_pct_min" placeholder="最小" type="number" step="0.1" />
              <span class="sd-range-sep">–</span>
              <input v-model="createFilters.change_pct_max" placeholder="最大" type="number" step="0.1" />
            </div>
          </div>
          <div class="sd-filter-field">
            <label>量比最低</label>
            <input v-model="createFilters.volume_ratio_min" placeholder="0" type="number" step="0.1" />
          </div>
          <div class="sd-filter-field">
            <label>排序字段</label>
            <select v-model="createFilters.sort_by">
              <option v-for="s in SORT_OPTIONS" :key="s.value" :value="s.value">{{ s.label }}</option>
            </select>
          </div>
          <div class="sd-filter-field">
            <label>排序方向</label>
            <select v-model="createFilters.order">
              <option value="desc">降序</option>
              <option value="asc">升序</option>
            </select>
          </div>
          <div class="sd-filter-field sd-filter-field-check">
            <label>
              <input type="checkbox" v-model="createFilters.exclude_st" true-value="true" false-value="false" />
              排除ST
            </label>
          </div>
        </div>
        <div class="sd-dialog-btns">
          <button class="sd-confirm-btn" @click="handleCreate">创建</button>
          <button class="sd-cancel-btn" @click="showCreate = false">取消</button>
        </div>
      </div>
    </div>

    <!-- Intersection Detail Dialog -->
    <div v-if="showIntersect" class="sd-overlay" @click.self="closeIntersection">
      <div class="sd-dialog sd-dialog-wide">
        <div class="sd-dialog-header">
          <h4>策略交集详情 — {{ intersectResult.strategies.join(' + ') }}</h4>
          <button class="sd-dialog-close" @click="closeIntersection">✕</button>
        </div>
        <div class="sd-summary-bar" style="margin-top:0">
          共 <strong>{{ intersectResult.count }}</strong> 只股票同时满足这些策略
        </div>
        <div v-if="intersectLoading" class="sd-loading">加载中...</div>
        <div v-else-if="!intersectResult.stocks.length" class="sd-empty">暂无交集股票</div>
        <table v-else class="sd-detail-table">
          <thead>
            <tr>
              <th v-for="col in DETAIL_COLUMNS" :key="col.key" :class="{ 'sortable-th': true, 'active-sort': intersectSortBy === col.key }" @click="handleIntersectSort(col.key)">
                {{ col.label }}{{ intersectSortIndicator(col.key) }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="st in intersectPageStocks" :key="String(st.code)" class="clickable-row" @click="handleStockClick(st)">
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
        <div v-if="intersectTotalPages > 1" class="sd-pagination">
          <button :disabled="intersectPage <= 1" @click="intersectPage = intersectPage - 1">上一页</button>
          <span class="sd-page-info">{{ intersectPage }} / {{ intersectTotalPages }}</span>
          <button :disabled="intersectPage >= intersectTotalPages" @click="intersectPage = intersectPage + 1">下一页</button>
        </div>
      </div>
    </div>

    <!-- Strategy Stocks Detail Dialog -->
    <div v-if="detailStocksTitle" class="sd-overlay" @click.self="closeDetailStocks">
      <div class="sd-dialog sd-dialog-wide">
        <div class="sd-dialog-header">
          <h4>{{ detailStocksTitle }} — 匹配股票</h4>
          <button class="sd-dialog-close" @click="closeDetailStocks">✕</button>
        </div>
        <div class="sd-summary-bar" style="margin-top:0">
          共 <strong>{{ detailStocksTotal }}</strong> 只股票
        </div>
        <div v-if="detailStocksLoading" class="sd-loading">加载中...</div>
        <div v-else-if="!detailStocks.length" class="sd-empty">暂无匹配股票</div>
        <table v-else class="sd-detail-table">
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
        <div v-if="detailTotalPages > 1" class="sd-pagination">
          <button :disabled="detailStocksPage <= 1" @click="fetchDetailStocksPage(detailStocksPage - 1)">上一页</button>
          <span class="sd-page-info">{{ detailStocksPage }} / {{ detailTotalPages }}</span>
          <button :disabled="detailStocksPage >= detailTotalPages" @click="fetchDetailStocksPage(detailStocksPage + 1)">下一页</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.strategy-dashboard { padding: 20px 24px; }
.sd-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; }
.sd-title { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.sd-header-right { display: flex; align-items: center; gap: 12px; }
.sd-view-tabs { display: flex; gap: 4px; }
.sd-view-btn {
  padding: 5px 12px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  background: var(--bg-alt); color: var(--text-secondary); font-size: 12px;
  cursor: pointer; font-weight: 500; transition: all var(--transition);
}
.sd-view-btn:hover { border-color: var(--accent); color: var(--text-primary); }
.sd-view-btn.active { background: var(--accent); color: white; border-color: var(--accent); }
.sd-refresh-btn {
  padding: 5px 14px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  background: var(--bg-surface); color: var(--text-secondary); font-size: 12px; font-weight: 500;
  cursor: pointer; transition: all var(--transition);
}
.sd-refresh-btn:hover { background: var(--bg-hover); color: var(--text-primary); border-color: var(--accent); }
.sd-loading, .sd-empty { text-align: center; padding: 40px 0; color: var(--text-muted); font-size: 13px; }
.sd-summary-bar { font-size: 13px; color: var(--text-secondary); margin-bottom: 16px; padding: 10px 14px; background: var(--bg-alt); border-radius: var(--radius); border: 1px solid var(--border); }
.sd-summary-bar strong { color: var(--accent); }

/* Dashboard Cards */
.sd-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }
.sd-card {
  background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 16px; cursor: pointer; transition: all var(--transition);
}
.sd-card:hover { border-color: var(--accent); box-shadow: 0 4px 16px var(--shadow); transform: translateY(-1px); }
.sd-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.sd-card-name { font-size: 15px; font-weight: 700; color: var(--text-primary); }
.sd-card-count { font-size: 14px; font-weight: 700; color: var(--accent); }
.sd-card-desc { font-size: 12px; color: var(--text-muted); margin-bottom: 10px; line-height: 1.5; }
.sd-card-stocks { display: flex; flex-wrap: wrap; gap: 6px; }
.sd-stock-tag {
  padding: 2px 8px; border-radius: 12px; font-size: 12px;
  background: var(--bg-alt); border: 1px solid var(--border);
  color: var(--text-primary); white-space: nowrap;
}
.sd-stock-tag small { color: var(--text-muted); margin-left: 2px; }
.sd-card-empty { font-size: 12px; color: var(--text-muted); padding: 8px 0; }

/* Compare View */
.sd-compare-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; }
.sd-compare-col {
  background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 14px;
}
.sd-compare-title {
  font-size: 14px; font-weight: 700; color: var(--accent); margin: 0 0 4px 0;
  cursor: pointer; transition: color var(--transition);
}
.sd-compare-title:hover { color: var(--text-primary); }
.sd-compare-count { font-size: 12px; color: var(--text-muted); margin-bottom: 10px; }
.sd-compare-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.sd-compare-table th {
  background: var(--bg-alt); color: var(--text-secondary); font-weight: 600;
  padding: 5px 8px; text-align: right; border-bottom: 1px solid var(--border); font-size: 11px;
}
.sd-compare-table th:first-child, .sd-compare-table td:first-child { text-align: left; }
.sd-compare-table td {
  padding: 4px 8px; text-align: right; border-bottom: 1px solid var(--border);
  color: var(--text-primary); white-space: nowrap;
}
.sd-compare-table tbody tr:hover { background: var(--accent-light); }
.sd-card-empty { font-size: 12px; color: var(--text-muted); text-align: center; padding: 16px 0; }

/* Intersect View */
.sd-intersect-list { display: flex; flex-direction: column; gap: 6px; }
.sd-intersect-row {
  display: flex; align-items: center; gap: 14px; padding: 10px 14px;
  background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-sm);
  transition: background var(--transition);
}
.sd-intersect-row { cursor: pointer; }
.sd-intersect-row:hover { background: var(--accent-light); }
.sd-intersect-names { font-weight: 600; font-size: 13px; color: var(--text-primary); min-width: 180px; }
.sd-intersect-count { font-weight: 700; font-size: 14px; color: var(--accent); min-width: 60px; }
.sd-intersect-samples { font-size: 12px; color: var(--text-muted); font-family: monospace; }

/* Intersection detail dialog */
.sd-dialog-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.sd-dialog-header h4 { margin-bottom: 0; }
.sd-dialog-close {
  background: none; border: none; color: var(--text-muted); cursor: pointer;
  font-size: 18px; padding: 2px 6px; border-radius: var(--radius-sm); line-height: 1;
  transition: all var(--transition);
}
.sd-dialog-close:hover { background: var(--bg-hover); color: var(--text-primary); }
.sd-detail-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.sd-detail-table th {
  background: var(--bg-alt); color: var(--text-secondary); font-weight: 600;
  padding: 6px 10px; text-align: right; border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 1; font-size: 11px;
}
.sd-detail-table th:first-child, .sd-detail-table td:first-child { text-align: left; }
.sortable-th { cursor: pointer; user-select: none; transition: color var(--transition); }
.sortable-th:hover { color: var(--accent); }
.active-sort { color: var(--accent); }
.sd-detail-table td {
  padding: 5px 10px; text-align: right; border-bottom: 1px solid var(--border);
  color: var(--text-primary); white-space: nowrap;
}
.sd-detail-table tbody tr:hover { background: var(--accent-light); }
.sd-detail-table .td-code { font-family: monospace; color: var(--accent); }
.clickable-row { cursor: pointer; }

/* Pagination */
.sd-pagination {
  display: flex; align-items: center; justify-content: center; gap: 12px;
  margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border);
}
.sd-pagination button {
  padding: 5px 14px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  background: var(--bg-alt); color: var(--text-secondary); font-size: 12px; font-weight: 500;
  cursor: pointer; transition: all var(--transition);
}
.sd-pagination button:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); background: var(--accent-light); }
.sd-pagination button:disabled { opacity: 0.4; cursor: default; }
.sd-page-info { font-size: 12px; color: var(--text-secondary); font-weight: 500; min-width: 60px; text-align: center; }

/* Color coding */
.num-up { color: var(--red) !important; font-weight: 500; }
.num-down { color: var(--green) !important; font-weight: 500; }

/* Create button */
.sd-create-btn {
  padding: 5px 14px; border: 1px solid var(--accent); border-radius: var(--radius-sm);
  background: var(--accent); color: white; font-size: 12px; font-weight: 500;
  cursor: pointer; transition: all var(--transition); white-space: nowrap;
}
.sd-create-btn:hover { background: var(--accent-hover); box-shadow: 0 2px 8px rgba(59,130,246,0.3); }

/* Delete button on cards */
.sd-card-delete {
  background: none; border: none; color: var(--text-muted); cursor: pointer;
  font-size: 14px; padding: 2px 6px; border-radius: var(--radius-sm); line-height: 1;
  transition: all var(--transition); margin-left: auto;
}
.sd-card-delete:hover { background: var(--red); color: white; }

/* Dialog overlay */
.sd-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 200;
  display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(2px);
}
.sd-dialog {
  background: var(--bg-surface); padding: 24px; border-radius: var(--radius); width: 460px;
  max-height: 85vh; overflow-y: auto;
  box-shadow: 0 16px 48px var(--shadow-lg);
  animation: dialogIn 0.2s ease;
}
.sd-dialog-wide { width: 1100px; max-width: 96vw; }
@keyframes dialogIn {
  from { transform: scale(0.95); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
.sd-dialog h4 { margin-bottom: 14px; color: var(--text-primary); font-size: 15px; font-weight: 700; }
.sd-input {
  width: 100%; padding: 8px 12px; border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm); background: var(--bg-alt); color: var(--text-primary);
  font-size: 13px; margin-bottom: 10px; transition: all var(--transition);
}
.sd-input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(59,130,246,0.1); }
.sd-textarea {
  width: 100%; padding: 8px 12px; border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm); background: var(--bg-alt); color: var(--text-primary);
  font-size: 12px; margin-bottom: 14px; resize: vertical; font-family: inherit; transition: all var(--transition);
}
.sd-textarea:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(59,130,246,0.1); }

/* Filter grid */
.sd-filter-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }
.sd-filter-field { display: flex; flex-direction: column; gap: 3px; }
.sd-filter-field-2col { grid-column: span 2; }
.sd-filter-field label { font-size: 11px; color: var(--text-muted); font-weight: 500; }
.sd-filter-field input, .sd-filter-field select {
  padding: 6px 10px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  background: var(--bg-alt); color: var(--text-primary); font-size: 12px;
  transition: all var(--transition);
}
.sd-filter-field input:focus, .sd-filter-field select:focus { outline: none; border-color: var(--accent); }
.sd-filter-field-check { justify-content: flex-end; }
.sd-filter-field-check label { font-size: 12px; color: var(--text-secondary); cursor: pointer; display: flex; align-items: center; gap: 4px; }
.sd-filter-field-check input[type="checkbox"] { cursor: pointer; accent-color: var(--accent); width: 14px; height: 14px; }
.sd-range-row { display: flex; align-items: center; gap: 6px; }
.sd-range-row input { flex: 1; width: 0; }
.sd-range-sep { color: var(--text-muted); font-size: 11px; }
.sd-dialog-btns { display: flex; gap: 8px; justify-content: flex-end; }
.sd-confirm-btn {
  padding: 7px 18px; background: var(--accent); color: white; border: none;
  border-radius: var(--radius-sm); cursor: pointer; font-size: 13px; font-weight: 500;
  transition: all var(--transition);
}
.sd-confirm-btn:hover { background: var(--accent-hover); box-shadow: 0 4px 12px rgba(59,130,246,0.3); }
.sd-cancel-btn {
  padding: 7px 18px; background: transparent; color: var(--text-secondary);
  border: 1px solid var(--border-strong); border-radius: var(--radius-sm); cursor: pointer;
  font-size: 13px; font-weight: 500; transition: all var(--transition);
}
.sd-cancel-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
</style>
