<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { createChart, CandlestickSeries, HistogramSeries, type IChartApi } from 'lightweight-charts'
import { api } from '../api'

const props = defineProps<{ code: string | null }>()
const emit = defineEmits<{ close: [] }>()

const detail = ref<{ basic: Record<string, unknown> | null; daily: Record<string, unknown>[] }>({ basic: null, daily: [] })
const loading = ref(false)

watch(() => props.code, async (newCode) => {
  destroyChart()
  if (!newCode) { detail.value = { basic: null, daily: [] }; return }
  loading.value = true
  try {
    const data = await api.getStockDetail(newCode) as { basic: Record<string, unknown> | null; daily: Record<string, unknown>[] }
    // Show newest data first in table (API returns chronological order)
    data.daily = data.daily.reverse()
    detail.value = data
  } finally {
    loading.value = false
  }
})

const chartContainer = ref<HTMLDivElement>()
let chart: IChartApi | null = null

onBeforeUnmount(() => destroyChart())

function destroyChart() {
  if (chart) { chart.remove(); chart = null }
}

function isDark() {
  return document.documentElement.classList.contains('dark')
}

function chartColors() {
  const dark = isDark()
  return {
    bg: dark ? '#0f172a' : '#ffffff',
    text: dark ? '#94a3b8' : '#64748b',
    grid: dark ? '#1e293b' : '#e2e8f0',
    up: '#ef4444',
    down: '#22c55e',
  }
}

watch(() => detail.value.daily, async (daily) => {
  destroyChart()
  if (!daily.length) return
  await nextTick()
  // Wait for the drawer slide-in layout to complete
  await new Promise(r => setTimeout(r, 100))
  if (!chartContainer.value) return

  const hasOHLC = daily[0] && 'open' in daily[0]
  if (!hasOHLC) return

  const colors = chartColors()
  chart = createChart(chartContainer.value, {
    height: 320,
    layout: {
      background: { color: colors.bg },
      textColor: colors.text,
    },
    grid: {
      vertLines: { color: colors.grid },
      horzLines: { color: colors.grid },
    },
    timeScale: { borderColor: colors.grid },
    leftPriceScale: { borderColor: colors.grid, visible: true },
    rightPriceScale: { visible: false },
  })

  // Remove lightweight-charts branding link
  chartContainer.value.querySelectorAll('a').forEach(el => {
    if (el.href && el.href.includes('tradingview')) el.remove()
  })

  // Chart expects chronological order (oldest first)
  const chronological = [...daily].reverse()

  const candleSeries = chart.addSeries(CandlestickSeries, {
    upColor: colors.up, downColor: colors.down,
    borderUpColor: colors.up, borderDownColor: colors.down,
    wickUpColor: colors.up, wickDownColor: colors.down,
    priceScaleId: 'left',
  })
  candleSeries.setData(chronological.map(d => ({
    time: String(d.date),
    open: Number(d.open),
    high: Number(d.high),
    low: Number(d.low),
    close: Number(d.close),
  })))

  const volumeSeries = chart.addSeries(HistogramSeries, {
    priceFormat: { type: 'volume' },
    priceScaleId: '',
  })
  volumeSeries.priceScale().applyOptions({
    scaleMargins: { top: 0.82, bottom: 0 },
  })
  volumeSeries.setData(chronological.map(d => {
    const open = Number(d.open), close = Number(d.close)
    return {
      time: String(d.date),
      value: Number(d.volume),
      color: close >= open ? colors.down : colors.up,
    }
  }))
})

function fmt(val: unknown): string {
  if (val === null || val === undefined) return '-'
  return String(val)
}

const BASIC_LABELS: Record<string, string> = {
  code: '代码', name: '名称', market: '板块', industry: '行业', list_date: '上市日期',
}

const MARKET_NAMES: Record<string, string> = {
  sh_sz: '沪深A股', chinext: '创业板', star: '科创板', bse: '北交所',
}

function marketName(market: string): string {
  return MARKET_NAMES[market] || market
}

const DAILY_COLUMNS = [
  { key: 'date', label: '日期' },
  { key: 'open', label: '开盘' },
  { key: 'high', label: '最高' },
  { key: 'low', label: '最低' },
  { key: 'close', label: '收盘' },
  { key: 'volume', label: '成交量(手)' },
  { key: 'turnover_rate', label: '换手率(%)' },
]

function activeDays(count: number) {
  return `最近 ${count} 个交易日`
}
</script>

<template>
  <div v-if="code" class="drawer-overlay" @click.self="emit('close')">
    <div class="drawer">
      <div class="drawer-header">
        <h3>{{ code }} {{ detail.basic?.name || '' }}</h3>
        <button class="close-btn" @click="emit('close')">✕</button>
      </div>
      <div v-if="loading" class="drawer-loading">加载中...</div>
      <div v-else class="drawer-body">
        <section v-if="detail.basic" class="detail-section">
          <h4 class="section-title">基本信息</h4>
          <div class="detail-grid">
            <template v-for="(val, key) in detail.basic" :key="key">
              <div v-if="BASIC_LABELS[key]" class="detail-item">
                <span class="detail-label">{{ BASIC_LABELS[key] }}</span>
                <span class="detail-value">{{ key === 'market' ? marketName(String(val)) : fmt(val) }}</span>
              </div>
            </template>
          </div>
        </section>

        <section v-if="detail.daily.length" class="detail-section">
          <h4 class="section-title">K线图</h4>
          <div ref="chartContainer" class="chart-container"></div>
        </section>

        <section v-if="detail.daily.length" class="detail-section">
          <h4 class="section-title">{{ activeDays(detail.daily.length) }}</h4>
          <div class="daily-table-wrap">
            <table class="daily-table">
              <thead>
                <tr>
                  <th v-for="col in DAILY_COLUMNS" :key="col.key">{{ col.label }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in detail.daily" :key="i">
                  <td v-for="col in DAILY_COLUMNS" :key="col.key">{{ fmt(row[col.key]) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.drawer-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.3); z-index: 100;
  display: flex; justify-content: flex-end;
}
.drawer {
  width: 520px; height: 100%; background: var(--bg-surface); overflow-y: auto;
  padding: 20px; border-left: 1px solid var(--border); box-shadow: -4px 0 20px var(--shadow);
}
.drawer-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.drawer-header h3 { font-size: 18px; margin: 0; color: var(--text-primary); }
.close-btn { background: none; border: none; color: var(--text-muted); font-size: 18px; cursor: pointer; }
.close-btn:hover { color: var(--text-secondary); }
.drawer-loading { color: #f59e0b; text-align: center; padding: 40px 0; }
.drawer-body { font-size: 13px; }
.detail-section { margin-bottom: 20px; }
.section-title { font-size: 13px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.detail-item { background: var(--bg-alt); padding: 8px 10px; border-radius: 6px; border: 1px solid var(--border); }
.detail-label { color: var(--text-muted); font-size: 11px; display: block; margin-bottom: 2px; }
.detail-value { color: var(--text-primary); font-weight: 500; }

.chart-container { width: 100%; height: 320px; border-radius: 6px; overflow: hidden; border: 1px solid var(--border); position: relative; }

.daily-table-wrap { max-height: 300px; overflow: auto; border: 1px solid var(--border); border-radius: 6px; }
.daily-table { width: 100%; border-collapse: collapse; font-size: 11px; }
.daily-table thead { position: sticky; top: 0; z-index: 1; }
.daily-table th {
  background: var(--bg-alt); color: var(--text-secondary); font-weight: 600;
  padding: 5px 6px; text-align: right; border-bottom: 1px solid var(--border); white-space: nowrap;
}
.daily-table th:first-child { text-align: left; }
.daily-table td {
  padding: 4px 6px; text-align: right; border-bottom: 1px solid var(--border);
  color: var(--text-primary); white-space: nowrap;
}
.daily-table td:first-child { text-align: left; color: var(--text-secondary); }
.daily-table tbody tr:hover { background: var(--bg-hover); }
</style>
