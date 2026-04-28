import { ref, computed } from 'vue'

const STORAGE_KEY = 'stockScreenerWatchlist'

function load(): Set<string> {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) return new Set(JSON.parse(stored))
  } catch { /* ignore */ }
  return new Set()
}

const codes = ref<Set<string>>(load())

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...codes.value]))
}

export function useWatchlist() {
  function toggle(code: string) {
    const next = new Set(codes.value)
    if (next.has(code)) next.delete(code)
    else next.add(code)
    codes.value = next
    persist()
  }

  function isFavorite(code: string): boolean {
    return codes.value.has(code)
  }

  const count = computed(() => codes.value.size)

  function filter(items: Record<string, unknown>[]): Record<string, unknown>[] {
    if (codes.value.size === 0) return items
    return items.filter(item => {
      const c = item.code as string | undefined
      return c && codes.value.has(c)
    })
  }

  return { codes, toggle, isFavorite, count, filter }
}
