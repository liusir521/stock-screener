<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount, onMounted } from 'vue'
import { createChart, CandlestickSeries, HistogramSeries, LineSeries, type IChartApi, type ISeriesApi, CrosshairMode, type UTCTimestamp, type Time } from 'lightweight-charts'
import { api } from '../api'

const props = defineProps<{ code: string | null }>()
const emit = defineEmits<{ close: [] }>()

const detail = ref<{ basic: Record<string, unknown> | null; daily: Record<string, unknown>[] }>({ basic: null, daily: [] })
const intradayBars = ref<Record<string, unknown>[]>([])
const intradayPrevClose = ref<number | null>(null)
const klinePeriod = ref<'daily' | 'weekly' | 'monthly'>('daily')
const klineData = ref<Record<string, unknown>[]>([])
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
  if (!newCode) { detail.value = { basic: null, daily: [] }; intradayBars.value = []; return }
  loading.value = true
  try {
    const [data, idata] = await Promise.all([
      api.getStockDetail(newCode) as Promise<{ basic: Record<string, unknown> | null; daily: Record<string, unknown>[] }>,
      api.getStockIntraday(newCode) as Promise<{ bars: Record<string, unknown>[]; prev_close: number | null; float_shares: number; turnover_rate: number | null }>,
    ])
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
    // Merge today's intraday bars into daily K-line data (synthesize daily candle)
    if (idata.bars && idata.bars.length > 0) {
      const bars = idata.bars
      const today = new Date().toISOString().split('T')[0]
      const opens = bars.map(b => Number(b.open ?? b.close)).filter(v => v > 0)
      const highs = bars.map(b => Number(b.high ?? b.close)).filter(v => v > 0)
      const lows = bars.map(b => Number(b.low ?? b.close)).filter(v => v > 0)
      const synth: Record<string, unknown> = {
        date: today,
        open: opens[0] ?? Number(bars[0].close),
        high: Math.max(...highs),
        low: Math.min(...lows),
        close: Number(bars[bars.length - 1].close),
        volume: bars.reduce((s, b) => s + Number(b.volume || 0), 0),
      }
      const lastIdx = data.daily.length - 1
      // If the API already has today's row, compare against the day before; otherwise use last day
      const refIdx = (lastIdx >= 0 && String(data.daily[lastIdx].date) === today) ? lastIdx - 1 : lastIdx
      const prevClose = refIdx >= 0 ? Number(data.daily[refIdx].close) : Number(synth.open)
      synth.change_pct = prevClose > 0 ? ((Number(synth.close) - prevClose) / prevClose) * 100 : 0
      if (idata.turnover_rate !== null && idata.turnover_rate !== undefined) {
        synth.turnover_rate = idata.turnover_rate
      }
      if (lastIdx >= 0 && String(data.daily[lastIdx].date) === today) {
        data.daily[lastIdx] = synth
      } else {
        data.daily.push(synth)
        if (data.daily.length > 120) data.daily.shift()
      }
    }
    // Show newest data first in table
    data.daily = data.daily.reverse()
    detail.value = data
    intradayBars.value = idata.bars || []
    intradayPrevClose.value = idata.prev_close
    loading.value = false
    await nextTick()
    await new Promise(r => setTimeout(r, 300))
    renderCharts()
    renderIntradayChart()
  } finally {
    loading.value = false
  }
})

const chartContainer = ref<HTMLDivElement>()
let chart: IChartApi | null = null
let macdChart: IChartApi | null = null
let intradayChart: IChartApi | null = null
let macdChartEl: HTMLDivElement | null = null
const maLastValues = ref<{ ma5: string; ma20: string; ma60: string }>({ ma5: '-', ma20: '-', ma60: '-' })
const macdLastValues = ref<{ dif: string; dea: string; macd: string }>({ dif: '-', dea: '-', macd: '-' })

function destroyChart() {
  if (chart) { chart.remove(); chart = null }
  if (macdChart) { macdChart.remove(); macdChart = null }
  if (intradayChart) { intradayChart.remove(); intradayChart = null }
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
  const opts = {
    layout: { background: { color: colors.bg }, textColor: colors.text },
    grid: { vertLines: { color: colors.grid }, horzLines: { color: colors.grid } },
    timeScale: { borderColor: colors.grid },
    leftPriceScale: { borderColor: colors.grid },
  }
  chart.applyOptions(opts)
  if (macdChart) macdChart.applyOptions({ ...opts, leftPriceScale: undefined, rightPriceScale: { borderColor: colors.grid } })
  if (intradayChart) intradayChart.applyOptions({ ...opts, leftPriceScale: undefined, rightPriceScale: { borderColor: colors.grid } })
}

function renderCharts() {
  destroyChart()
  const source = klinePeriod.value === 'daily'
    ? detail.value.daily
    : klineData.value
  if (!source.length) return
  if (!chartContainer.value) return

  const hasOHLC = source[0] && 'open' in source[0]
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

  // Chart expects chronological order (oldest first) — daily is newest-first, klineData is oldest-first
  const chronological = klinePeriod.value === 'daily'
    ? [...source].reverse()
    : [...source]

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

  // MACD computation: EMA12, EMA26, DIF, DEA(9), MACD bar
  const ema = (data: number[], period: number) => {
    const k = 2 / (period + 1)
    const result: number[] = []
    let prev = data[0]
    for (let i = 0; i < data.length; i++) {
      prev = data[i] * k + prev * (1 - k)
      result.push(prev)
    }
    return result
  }
  const ema12 = ema(closes, 12)
  const ema26 = ema(closes, 26)
  const dif = ema12.map((v, i) => v - ema26[i])
  const dea = ema(dif, 9)
  const macdBars = dif.map((v, i) => (v - dea[i]) * 2)

  // Store last MACD values for legend
  const lastDif = dif[dif.length - 1]
  const lastDea = dea[dea.length - 1]
  const lastMacd = macdBars[macdBars.length - 1]
  macdLastValues.value = {
    dif: lastDif !== undefined ? lastDif.toFixed(3) : '-',
    dea: lastDea !== undefined ? lastDea.toFixed(3) : '-',
    macd: lastMacd !== undefined ? lastMacd.toFixed(3) : '-',
  }

  // MACD chart (separate pane below price chart)
  macdChartEl = document.getElementById('macd-chart-area') as HTMLDivElement | null
  if (macdChartEl) {
    try {
      macdChart = createChart(macdChartEl, {
        height: 140,
        layout: { background: { color: colors.bg }, textColor: colors.text },
        grid: { vertLines: { color: colors.grid }, horzLines: { color: colors.grid } },
        timeScale: { borderColor: colors.grid, timeVisible: false },
        leftPriceScale: { borderColor: colors.grid, visible: true },
        rightPriceScale: { visible: false },
      })

      const macdColors = { dif: '#f59e0b', dea: '#3b82f6', barUp: '#ef4444', barDown: '#22c55e' }

      const difSeries = macdChart.addSeries(LineSeries, {
        color: macdColors.dif, lineWidth: 1, lastValueVisible: false,
      })
      difSeries.setData(dif.map((v, i) => ({ time: String(chronological[i].date), value: v })))

      const deaSeries = macdChart.addSeries(LineSeries, {
        color: macdColors.dea, lineWidth: 1, lastValueVisible: false,
      })
      deaSeries.setData(dea.map((v, i) => ({ time: String(chronological[i].date), value: v })))

      const macdSeries = macdChart.addSeries(HistogramSeries, {})
      macdSeries.setData(macdBars.map((v, i) => ({
        time: String(chronological[i].date),
        value: v,
        color: v >= 0 ? macdColors.barUp : macdColors.barDown,
      })))

      macdChartEl.querySelectorAll('a').forEach(el => {
        if (el.href && el.href.includes('tradingview')) el.remove()
      })
    } catch (e) {
      console.error('MACD chart creation failed:', e)
      if (macdChart) { macdChart.remove(); macdChart = null }
    }
  }

  // ResizeObserver for responsive chart
  const ro = new ResizeObserver(() => {
    if (chart && chartContainer.value) {
      const w = chartContainer.value.clientWidth
      chart.applyOptions({ width: w })
      if (macdChart) macdChart.applyOptions({ width: w })
    }
  })
  ro.observe(chartContainer.value)
}

function renderIntradayChart() {
  if (intradayChart) { intradayChart.remove(); intradayChart = null }
  const bars = intradayBars.value
  if (!bars.length) return

  const el = document.getElementById('intraday-chart-area') as HTMLDivElement | null
  if (!el) return

  // Convert datetime strings to Unix timestamps (seconds)
  const toTs = (s: unknown) => Math.floor(new Date(String(s)).getTime() / 1000) as UTCTimestamp

  // Full trading day boundaries (9:30 - 15:00)
  const now = new Date()
  const dayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 9, 30, 0)
  const dayEnd   = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 15, 0, 0)
  const fullFrom = Math.floor(dayStart.getTime() / 1000) as UTCTimestamp
  const fullTo   = Math.floor(dayEnd.getTime() / 1000) as UTCTimestamp

  const fmtTime = (ts: Time) => {
    const unix = ts as number
    const d = new Date(unix * 1000)
    return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0')
  }

  const colors = chartColors()
  intradayChart = createChart(el, {
    height: 320,
    layout: { background: { color: colors.bg }, textColor: colors.text },
    grid: { vertLines: { color: colors.grid }, horzLines: { color: colors.grid } },
    timeScale: {
      borderColor: colors.grid,
      timeVisible: true,
      tickMarkFormatter: fmtTime,
    },
    localization: { timeFormatter: fmtTime },
    leftPriceScale: { borderColor: colors.grid, visible: true },
    rightPriceScale: { visible: false },
  })

  // Remove branding link
  el.querySelectorAll('a').forEach(a => {
    if (a.href && a.href.includes('tradingview')) a.remove()
  })

  // Compute average price: cumulative (vol * price) / cumulative vol
  const avgPrices: number[] = []
  let cumVolPrice = 0, cumVol = 0
  for (const b of bars) {
    const c = Number(b.close), v = Number(b.volume)
    if (c && v) {
      cumVolPrice += c * v
      cumVol += v
    }
    avgPrices.push(cumVol > 0 ? cumVolPrice / cumVol : c)
  }

  // Price line (white in dark, dark blue in light)
  const priceSeries = intradayChart.addSeries(LineSeries, {
    color: isDark() ? '#ffffff' : '#1e40af',
    lineWidth: 2,
    lastValueVisible: false,
  })
  priceSeries.setData(bars.map(d => ({ time: toTs(d.date), value: Number(d.close) })))

  // Average price line (yellow, dashed)
  const avgSeries = intradayChart.addSeries(LineSeries, {
    color: '#f59e0b',
    lineWidth: 1,
    lineStyle: 2, // dashed
    lastValueVisible: false,
  })
  avgSeries.setData(bars.map((d, i) => ({ time: toTs(d.date), value: avgPrices[i] })))

  // 0-axis line (yesterday's close) via price line — thinner, dashed, like 同花顺
  if (intradayPrevClose.value && intradayPrevClose.value > 0) {
    priceSeries.createPriceLine({
      price: intradayPrevClose.value,
      color: isDark() ? '#94a3b8' : '#64748b',
      lineWidth: 1,
      lineStyle: 2, // dashed
      axisLabelVisible: false,
    })
  }

  // Volume bars
  const volumeSeries = intradayChart.addSeries(HistogramSeries, {
    priceFormat: { type: 'volume' },
    priceScaleId: '',
  })
  volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } })
  volumeSeries.setData(bars.map((d, i) => {
    const curClose = Number(d.close)
    const prevClose = i > 0 ? Number(bars[i - 1].close) : curClose
    return {
      time: toTs(d.date),
      value: Number(d.volume),
      color: curClose >= prevClose ? colors.up : colors.down,
    }
  }))

  // Force full trading day width (9:30–15:00)
  intradayChart.timeScale().setVisibleRange({ from: fullFrom, to: fullTo })

  // ResizeObserver
  const ro = new ResizeObserver(() => {
    if (intradayChart && el) {
      intradayChart.applyOptions({ width: el.clientWidth })
    }
  })
  ro.observe(el)
}

async function switchKlinePeriod(period: 'daily' | 'weekly' | 'monthly') {
  if (period === klinePeriod.value) return
  klinePeriod.value = period
  if (period === 'daily') {
    klineData.value = []
    await nextTick()
    renderCharts()
    return
  }
  try {
    const data = await api.getStockKline(props.code!, period)
    klineData.value = data.kline
    await nextTick()
    renderCharts()
  } catch (e) {
    console.error('Failed to fetch kline:', e)
  }
}

function fmt(val: unknown, col?: string): string {
  if (val === null || val === undefined) return '-'
  if (col === 'change_pct') {
    const n = Number(val)
    if (isNaN(n)) return '-'
    return (n > 0 ? '+' : '') + n.toFixed(2) + '%'
  }
  return String(val)
}

function changeClass(val: unknown): string {
  const n = Number(val)
  if (isNaN(n) || n === 0) return ''
  return n > 0 ? 'num-up' : 'num-down'
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

        <section v-if="intradayBars.length && klinePeriod === 'daily'" class="detail-section">
          <h4 class="section-title">分时图</h4>
          <div class="intraday-chart-container" id="intraday-chart-area"></div>
          <div class="ma-legend">
            <span class="ma-item">现价 {{ intradayBars.length ? Number(intradayBars[intradayBars.length-1].close).toFixed(2) : '-' }}</span>
            <span class="ma-item" style="color: #f59e0b">均价 {{ (() => { let cvp = 0, cv = 0; for (const b of intradayBars) { const c = Number(b.close), v = Number(b.volume); if (c && v) { cvp += c * v; cv += v } } return cv > 0 ? (cvp / cv).toFixed(2) : '-'; })() }}</span>
            <span class="ma-item">昨收 {{ intradayPrevClose?.toFixed(2) || '-' }}</span>
            <span class="ma-item" :class="intradayBars.length && intradayPrevClose ? (Number(intradayBars[intradayBars.length-1].close) >= intradayPrevClose ? 'num-up' : 'num-down') : ''">
              涨跌 {{ intradayBars.length && intradayPrevClose ? (Number(intradayBars[intradayBars.length-1].close) - intradayPrevClose).toFixed(2) : '-' }}
            </span>
            <span class="ma-item" :class="intradayBars.length && intradayPrevClose && intradayPrevClose > 0 ? (Number(intradayBars[intradayBars.length-1].close) >= intradayPrevClose ? 'num-up' : 'num-down') : ''">
              涨幅 {{ intradayBars.length && intradayPrevClose && intradayPrevClose > 0 ? ((Number(intradayBars[intradayBars.length-1].close) - intradayPrevClose) / intradayPrevClose * 100).toFixed(2) + '%' : '-' }}
            </span>
          </div>
        </section>

        <section v-if="detail.daily.length" class="detail-section">
          <div class="kline-header">
            <h4 class="section-title">K线图</h4>
            <div class="period-selector">
              <button
                v-for="p in (['daily', 'weekly', 'monthly'] as const)"
                :key="p"
                :class="['period-btn', { active: klinePeriod === p }]"
                @click="switchKlinePeriod(p)"
              >{{ { daily: '日K', weekly: '周K', monthly: '月K' }[p] }}</button>
            </div>
          </div>
          <div ref="chartContainer" class="chart-container"></div>
          <div class="ma-legend">
            <span class="ma-item" style="color: #f59e0b">MA5: {{ maLastValues.ma5 }}</span>
            <span class="ma-item" style="color: #3b82f6">MA20: {{ maLastValues.ma20 }}</span>
            <span class="ma-item" style="color: #a855f7">MA60: {{ maLastValues.ma60 }}</span>
          </div>
          <h4 class="section-title" style="margin-top: 16px;">MACD</h4>
          <div class="macd-chart-container" id="macd-chart-area"></div>
          <div class="ma-legend">
            <span class="ma-item" style="color: #f59e0b">DIF: {{ macdLastValues.dif }}</span>
            <span class="ma-item" style="color: #3b82f6">DEA: {{ macdLastValues.dea }}</span>
            <span class="ma-item" style="color: #ef4444">MACD: {{ macdLastValues.macd }}</span>
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
                  <td v-for="col in DAILY_COLUMNS" :key="col.key" :class="col.key === 'change_pct' ? changeClass(row[col.key]) : ''">{{ fmt(row[col.key], col.key) }}</td>
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
  position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 100;
  display: flex; justify-content: flex-end;
  backdrop-filter: blur(2px);
}
.drawer {
  width: 540px; height: 100%; background: var(--bg-surface); overflow-y: auto;
  padding: 24px; border-left: 1px solid var(--border);
  box-shadow: -8px 0 40px var(--shadow-lg);
  animation: slideIn 0.25s ease;
}
@keyframes slideIn {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}
.drawer-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid var(--border);
}
.drawer-header h3 { font-size: 18px; margin: 0; color: var(--text-primary); font-weight: 700; }
.close-btn {
  background: none; border: none; color: var(--text-muted); font-size: 20px;
  cursor: pointer; padding: 4px 8px; border-radius: var(--radius-sm);
  transition: all var(--transition);
}
.close-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.drawer-loading {
  color: var(--accent); text-align: center; padding: 60px 0; font-size: 14px;
  display: flex; align-items: center; justify-content: center; gap: 8px;
}
.drawer-body { font-size: 13px; }
.detail-section { margin-bottom: 24px; }
.section-title {
  font-size: 14px; font-weight: 700; color: var(--text-primary);
  margin-bottom: 10px;
}
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.detail-item {
  background: var(--bg-alt); padding: 10px 12px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); transition: all var(--transition);
}
.detail-item:hover { border-color: var(--border-strong); box-shadow: 0 2px 6px var(--shadow); }
.detail-label { color: var(--text-muted); font-size: 11px; display: block; margin-bottom: 4px; font-weight: 500; }
.detail-value { color: var(--text-primary); font-weight: 600; font-size: 14px; }

.chart-container {
  width: 100%; height: 360px; border-radius: var(--radius);
  overflow: hidden; border: 1px solid var(--border); position: relative;
  background: var(--bg-surface);
}
.intraday-chart-container {
  width: 100%; height: 320px; border-radius: var(--radius);
  overflow: hidden; border: 1px solid var(--border); position: relative;
  background: var(--bg-surface);
}
.macd-chart-container {
  width: 100%; height: 140px; border-radius: var(--radius);
  overflow: hidden; border: 1px solid var(--border); position: relative;
  background: var(--bg-surface);
}
.ma-legend {
  display: flex; gap: 20px; justify-content: center; padding: 10px 0 0;
  font-size: 12px; font-weight: 500;
}
.ma-item {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 4px; background: var(--bg-alt);
  border: 1px solid var(--border);
}

.daily-table-wrap {
  max-height: 320px; overflow: auto; border: 1px solid var(--border);
  border-radius: var(--radius);
}
.daily-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.daily-table thead { position: sticky; top: 0; z-index: 1; }
.daily-table th {
  background: var(--bg-alt); color: var(--text-secondary); font-weight: 600;
  padding: 7px 8px; text-align: right; border-bottom: 2px solid var(--border);
  white-space: nowrap; font-size: 11px; letter-spacing: 0.02em;
}
.daily-table th:first-child { text-align: left; padding-left: 12px; }
.daily-table td {
  padding: 6px 8px; text-align: right; border-bottom: 1px solid var(--border);
  color: var(--text-primary); white-space: nowrap;
}
.daily-table td:first-child { text-align: left; padding-left: 12px; color: var(--text-secondary); }
.daily-table tbody tr { transition: background var(--transition); }
.daily-table tbody tr:hover { background: var(--accent-light); }

.kline-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 10px;
}
.period-selector { display: flex; gap: 4px; }
.period-btn {
  padding: 4px 10px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  background: var(--bg-alt); color: var(--text-secondary); font-size: 11px;
  cursor: pointer; font-weight: 500; transition: all var(--transition);
}
.period-btn:hover { border-color: var(--accent); color: var(--text-primary); }
.period-btn.active {
  background: var(--accent); color: white; border-color: var(--accent);
}

/* Color coding */
.num-up { color: var(--red) !important; font-weight: 500; }
.num-down { color: var(--green) !important; font-weight: 500; }
</style>
