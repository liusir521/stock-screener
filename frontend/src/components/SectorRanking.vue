<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'

const emit = defineEmits<{ 'select-sector': [name: string] }>()

const sectors = ref<Record<string, unknown>[]>([])
const loading = ref(false)

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

function handleRowClick(row: Record<string, unknown>) {
  const name = String(row.name || '')
  if (name) emit('select-sector', name)
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
  { key: 'change_pct', label: '涨跌幅(%)' },
  { key: 'turnover_rate', label: '换手率(%)' },
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
          <tr v-for="(row, i) in sectors" :key="i" @click="handleRowClick(row)">
            <td v-for="col in COLUMNS" :key="col.key" :class="col.key === 'change_pct' || col.key === 'lead_stock_change' ? changeClass(row[col.key]) : ''">
              {{ fmt(row[col.key]) }}
            </td>
          </tr>
        </tbody>
      </table>
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
.num-up { color: var(--red); font-weight: 500; }
.num-down { color: var(--green); font-weight: 500; }
</style>
