<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'

const emit = defineEmits<{ 'apply-strategy': [filters: Record<string, unknown>] }>()

interface StrategyResult {
  name: string
  description: string
  filters: Record<string, unknown>
  match_count: number
  top_stocks: Record<string, unknown>[]
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

onMounted(async () => { await load() })

async function load() {
  loading.value = true
  try {
    dashboard.value = await api.getStrategyDashboard()
  } finally {
    loading.value = false
  }
}

function applyStrategy(strategy: StrategyResult) {
  emit('apply-strategy', { ...strategy.filters })
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
          @click="applyStrategy(s)"
        >
          <div class="sd-card-header">
            <span class="sd-card-name">{{ s.name }}</span>
            <span class="sd-card-count">{{ s.match_count }} 只</span>
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
          <h4 class="sd-compare-title" @click="applyStrategy(s)">{{ s.name }}</h4>
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
              <tr v-for="st in s.top_stocks" :key="String(st.code)">
                <td>{{ fmt(st.code) }}</td>
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
        <div v-for="(x, i) in dashboard.intersections" :key="i" class="sd-intersect-row">
          <span class="sd-intersect-names">{{ x.strategies.join(' + ') }}</span>
          <span class="sd-intersect-count">{{ x.count }} 只</span>
          <span class="sd-intersect-samples">{{ x.sample_codes.join(', ') }}</span>
        </div>
      </div>
    </template>
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
.sd-intersect-row:hover { background: var(--accent-light); }
.sd-intersect-names { font-weight: 600; font-size: 13px; color: var(--text-primary); min-width: 180px; }
.sd-intersect-count { font-weight: 700; font-size: 14px; color: var(--accent); min-width: 60px; }
.sd-intersect-samples { font-size: 12px; color: var(--text-muted); font-family: monospace; }

/* Color coding */
.num-up { color: var(--red) !important; font-weight: 500; }
.num-down { color: var(--green) !important; font-weight: 500; }
</style>
