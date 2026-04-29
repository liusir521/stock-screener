export interface StockItem {
  code: string
  name: string
  market: string
  industry: string
  is_st: number
  close: number
  volume: number
  turnover_rate: number
  pe_ttm: number
  pb: number
  roe: number
  revenue_growth_3y: number
  ma5: number
  ma20: number
  ma60: number
  macd_signal: string
  market_cap: number
  dividend_yield: number
  change_pct: number
  volume_ratio: number
}

export interface StockListResponse {
  total: number
  page: number
  page_size: number
  items: StockItem[]
}

export interface MarketOption {
  key: string
  label: string
}

export interface Strategy {
  name: string
  filters: Record<string, string | number | boolean>
  description?: string
}

export interface StockDetail {
  basic: StockItem | null
  daily: StockItem[]
}
