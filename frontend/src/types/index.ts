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

export interface AiConfig {
  api_url: string
  model: string
  has_key: boolean
}

export interface AgentMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface AgentChatResponse {
  reply: string
  data?: Record<string, unknown>
}

export interface AlertCondition {
  pe_max?: number; pe_min?: number; pb_max?: number; pb_min?: number
  roe_min?: number; market_cap_max?: number; market_cap_min?: number
  change_pct_min?: number; change_pct_max?: number; volume_ratio_min?: number
  dividend_yield_min?: number; revenue_growth_min?: number; turnover_rate_min?: number
}

export interface Alert {
  id: string; name: string; enabled: boolean
  conditions: AlertCondition
  triggered: boolean; triggered_stocks: StockItem[]
  last_triggered_at: string | null; created_at: string
}
