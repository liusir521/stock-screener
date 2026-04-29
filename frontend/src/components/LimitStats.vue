<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'

const emit = defineEmits<{ 'select-stock': [code: string] }>()

const stats = ref<{ zt_count: number; dt_count: number; zt_list: Record<string, unknown>[]; dt_list: Record<string, unknown>[] }>({ zt_count: 0, dt_count: 0, zt_list: [], dt_list: [] })
const loading = ref(false)

onMounted(async () => {
  await load()
})

async function load() {
  loading.value = true
  try {
    const data = await api.getLimitStats()
    stats.value = data
  } finally {
    loading.value = false
  }
}

function handleStockClick(code: string) {
  if (code) emit('select-stock', code)
}

function fmt(val: unknown): string {
  if (val === null || val === undefined) return '-'
  return String(val)
}

const ZT_COLUMNS = [
  { key: 'code', label: '代码' },
  { key: 'name', label: '名称' },
  { key: 'change_pct', label: '涨跌幅(%)' },
  { key: 'board_count', label: '连板数' },
  { key: 'first_seal_time', label: '首次封板' },
  { key: 'industry', label: '所属行业' },
]

const DT_COLUMNS = [
  { key: 'code', label: '代码' },
  { key: 'name', label: '名称' },
  { key: 'change_pct', label: '涨跌幅(%)' },
  { key: 'industry', label: '所属行业' },
]
</script>

<template>
  <div class="limit-stats">
    <div class="ls-header">
      <span class="ls-title">涨跌停板</span>
      <button class="ls-refresh-btn" :disabled="loading" @click="load">
        {{ loading ? '加载中...' : '刷新' }}
      </button>
    </div>
    <div v-if="loading && !stats.zt_list.length && !stats.dt_list.length" class="ls-loading">加载中...</div>
    <template v-else>
      <div class="ls-summary">
        <div class="ls-card zt-card">
          <span class="ls-card-label">涨停</span>
          <span class="ls-card-value num-up">{{ stats.zt_count }} 家</span>
        </div>
        <div class="ls-card dt-card">
          <span class="ls-card-label">跌停</span>
          <span class="ls-card-value num-down">{{ stats.dt_count }} 家</span>
        </div>
      </div>

      <section v-if="stats.zt_list.length" class="ls-section">
        <h4 class="ls-section-title">涨停板列表</h4>
        <div class="ls-table-wrap">
          <table class="ls-table">
            <thead>
              <tr>
                <th v-for="col in ZT_COLUMNS" :key="col.key">{{ col.label }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in stats.zt_list" :key="i" @click="handleStockClick(String(row.code))">
                <td v-for="col in ZT_COLUMNS" :key="col.key">{{ fmt(row[col.key]) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="stats.dt_list.length" class="ls-section">
        <h4 class="ls-section-title">跌停板列表</h4>
        <div class="ls-table-wrap">
          <table class="ls-table">
            <thead>
              <tr>
                <th v-for="col in DT_COLUMNS" :key="col.key">{{ col.label }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in stats.dt_list" :key="i" @click="handleStockClick(String(row.code))">
                <td v-for="col in DT_COLUMNS" :key="col.key">{{ fmt(row[col.key]) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <div v-if="!stats.zt_list.length && !stats.dt_list.length && !loading" class="ls-empty">暂无数据</div>
    </template>
  </div>
</template>

<style scoped>
.limit-stats { padding: 20px 24px; }
.ls-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.ls-title { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.ls-refresh-btn {
  padding: 5px 14px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  background: var(--bg-surface); color: var(--text-secondary); font-size: 12px; font-weight: 500;
  cursor: pointer; transition: all var(--transition);
}
.ls-refresh-btn:hover { background: var(--bg-hover); color: var(--text-primary); border-color: var(--accent); }
.ls-loading, .ls-empty { text-align: center; padding: 40px 0; color: var(--text-muted); font-size: 13px; }
.ls-summary { display: flex; gap: 16px; margin-bottom: 20px; }
.ls-card {
  flex: 1; padding: 16px 20px; border-radius: var(--radius); text-align: center;
  border: 1px solid var(--border); background: var(--bg-surface);
  transition: all var(--transition);
}
.ls-card-label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 6px; font-weight: 500; }
.ls-card-value { font-size: 24px; font-weight: 700; }
.zt-card { border-left: 3px solid var(--red); }
.dt-card { border-left: 3px solid var(--green); }
.ls-section { margin-bottom: 20px; }
.ls-section-title { font-size: 14px; font-weight: 600; color: var(--text-primary); margin-bottom: 8px; }
.ls-table-wrap { max-height: 400px; overflow: auto; border: 1px solid var(--border); border-radius: var(--radius); }
.ls-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.ls-table thead { position: sticky; top: 0; z-index: 1; }
.ls-table th {
  background: var(--bg-alt); color: var(--text-secondary); font-weight: 600;
  padding: 7px 10px; text-align: right; border-bottom: 2px solid var(--border);
  white-space: nowrap; font-size: 12px;
}
.ls-table th:first-child { text-align: left; }
.ls-table td {
  padding: 6px 10px; text-align: right; border-bottom: 1px solid var(--border);
  color: var(--text-primary); white-space: nowrap;
}
.ls-table td:first-child { text-align: left; color: var(--accent); font-weight: 500; }
.ls-table tbody tr { transition: background var(--transition); cursor: pointer; }
.ls-table tbody tr:hover { background: var(--accent-light); }
.num-up { color: var(--red); font-weight: 600; }
.num-down { color: var(--green); font-weight: 600; }
</style>
