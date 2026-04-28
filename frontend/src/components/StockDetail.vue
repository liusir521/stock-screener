<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount, onMounted } from 'vue'
import { createChart, CandlestickSeries, HistogramSeries, LineSeries, type IChartApi, type ISeriesApi, CrosshairMode } from 'lightweight-charts'
import { api } from '../api'

const props = defineProps<{ code: string | null }>()
const emit = defineEmits<{ close: [] }>()

const detail = ref<{ basic: Record<string, unknown> | null; daily: Record<string, unknown>[] }>({ basic: null, daily: [] })
const loading = ref(false)

let themeObserver: MutationObserver | null = null

onMounted(() => {
  themeObserver = new MutationObserver(() => {
    if (chart) updateChartTheme()
  })
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
})

onBeforeUnmount(() => {
  destroyChart()
  if (themeObserver) { themeObserver.disconnect(); themeObserver = null }
})

watch(() => props.code, async (newCode) => {
  destroyChart()
  if (!newCode) { detail.value = { basic: null, daily: [] }; return }
  loading.value = true
  try {
    const data = await api.getStockDetail(newCode) as { basic: Record<string, unknown> | null; daily: Record<string, unknown>[] }
    // Compute change_pct for each day (API returns chronological order, oldest first)
    for (let i = 0; i < data.daily.length; i++) {
      const todayClose = Number(data.daily[i].close)
      const prevClose = i > 0 ? Number(data.daily[i - 1].close) : Number(data.daily[i].open)
      if (prevClose && prevClose > 0) {
        ;(data.daily[i] as Record<string, unknown>).change_pct = ((todayClose - prevClose) / prevClose) * 100
      } else {
        ;(data.daily[i] as Record<string, unknown>).change_pct = 0
      }
    }
    // Show newest data first in table
    data.daily = data.daily.reverse()
    detail.value = data
  } finally {
    loading.value = false
  }
})

const chartContainer = ref<HTMLDivElement>()
let chart: IChartApi | null = null
const maLastValues = ref<{ ma5: string; ma20: string; ma60: string }>({ ma5: '-', ma20: '-', ma60: '-' })

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

function updateChartTheme() {
  if (!chart) return
  const colors = chartColors()
  chart.applyOptions({
    layout: { background: { color: colors.bg }, textColor: colors.text },
    grid: { vertLines: { color: colors.grid }, horzLines: { color: colors.grid } },
    timeScale: { borderColor: colors.grid },
    leftPriceScale: { borderColor: colors.grid },
  })
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
    height: 360,
    layout: {
      background: { color: colors.bg },
      textColor: colors.text,
    },
    grid: {
      vertLines: { color: colors.grid },
      horzLines: { color: colors.grid },
    },
    crosshair: { mode: CrosshairMode.Normal },
    timeScale: { borderColor: colors.grid, timeVisible: true },
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
    scaleMargins: { top: 0.85, bottom: 0 },
  })
  volumeSeries.setData(chronological.map(d => {
    const open = Number(d.open), close = Number(d.close)
    return {
      time: String(d.date),
      value: Number(d.volume),
      color: close >= open ? colors.up : colors.down,
    }
  }))

  // MA5 / MA20 / MA60 line overlays
  const closes = chronological.map(d => Number(d.close))
  const sma = (data: number[], period: number) => {
    const result: (number | null)[] = []
    let sum = 0
    for (let i = 0; i < data.length; i++) {
      sum += data[i]
      if (i >= period) sum -= data[i - period]
      result.push(i >= period - 1 ? sum / period : null)
    }
    return result
  }
  const ma5 = sma(closes, 5)
  const ma20 = sma(closes, 20)
  const ma60 = sma(closes, 60)

  // Store last values for legend
  const last5 = ma5.filter(v => v !== null).pop()
  const last20 = ma20.filter(v => v !== null).pop()
  const last60 = ma60.filter(v => v !== null).pop()
  maLastValues.value = {
    ma5: last5 !== undefined ? last5.toFixed(2) : '-',
    ma20: last20 !== undefined ? last20.toFixed(2) : '-',
    ma60: last60 !== undefined ? last60.toFixed(2) : '-',
  }

  const maColors = { ma5: '#f59e0b', ma20: '#3b82f6', ma60: '#a855f7' }

  const maSeries5 = chart.addSeries(LineSeries, { color: maColors.ma5, lineWidth: 2, priceScaleId: 'left', lastValueVisible: false })
  maSeries5.setData(ma5.map((v, i) => ({ time: String(chronological[i].date), value: v })).filter(d => d.value !== null))

  const maSeries20 = chart.addSeries(LineSeries, { color: maColors.ma20, lineWidth: 2, priceScaleId: 'left', lastValueVisible: false })
  maSeries20.setData(ma20.map((v, i) => ({ time: String(chronological[i].date), value: v })).filter(d => d.value !== null))

  const maSeries60 = chart.addSeries(LineSeries, { color: maColors.ma60, lineWidth: 2, priceScaleId: 'left', lastValueVisible: false })
  maSeries60.setData(ma60.map((v, i) => ({ time: String(chronological[i].date), value: v })).filter(d => d.value !== null))

  // ResizeObserver for responsive chart
  const ro = new ResizeObserver(() => {
    if (chart && chartContainer.value) {
      chart.applyOptions({ width: chartContainer.value.clientWidth })
    }
  })
  ro.observe(chartContainer.value)
})

function fmt(val: unknown, col?: string): string {
  if (val === null || val === undefined) return '-'
  if (col === 'change_pct') {
    const n = Number(val)
    if (isNaN(n)) return '-'
    return (n > 0 ? '+' : '') + n.toFixed(2) + '%'
  }
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
  { key: 'change_pct', label: '涨跌幅(%)' },
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
          <div class="ma-legend">
            <span class="ma-item" style="color: #f59e0b">MA5: {{ maLastValues.ma5 }}</span>
            <span class="ma-item" style="color: #3b82f6">MA20: {{ maLastValues.ma20 }}</span>
            <span class="ma-item" style="color: #a855f7">MA60: {{ maLastValues.ma60 }}</span>
          </div>
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
                  <td v-for="col in DAILY_COLUMNS" :key="col.key">{{ fmt(row[col.key], col.key) }}</td>
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

.chart-container { width: 100%; height: 360px; border-radius: 6px; overflow: hidden; border: 1px solid var(--border); position: relative; }
.ma-legend {
  display: flex; gap: 14px; justify-content: center; padding: 6px 0 0;
  font-size: 12px; font-weight: 500;
}
.ma-item { display: inline-flex; align-items: center; gap: 2px; }

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
