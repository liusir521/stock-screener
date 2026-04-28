const BASE = '/api'

async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== '') url.searchParams.set(k, v)
    })
  }
  const res = await fetch(url.toString())
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  return res.json()
}

export const api = {
  getMarkets: () => get<{ markets: { key: string; label: string }[] }>(`${BASE}/markets`),
  getStocks: (params: Record<string, string>) =>
    get<{ total: number; page: number; page_size: number; items: Record<string, unknown>[] }>(`${BASE}/stocks`, params),
  getStockDetail: (code: string) => get<{ basic: unknown; daily: unknown[] }>(`${BASE}/stocks/${code}`),
  getStrategies: () => get<{ strategies: { name: string; filters: Record<string, string> }[] }>(`${BASE}/strategies`),
  saveStrategy: (name: string, filters: Record<string, string>) =>
    post<{ status: string }>(`${BASE}/strategies`, { name, filters }),
}
