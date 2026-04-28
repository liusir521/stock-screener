<script setup lang="ts">
const props = defineProps<{ total: number; loading: boolean; items: Record<string, unknown>[] }>()

function exportCSV() {
  if (props.items.length === 0) return
  const cols = ['code', 'name', 'pe_ttm', 'pb', 'roe', 'market_cap', 'dividend_yield']
  const header = cols.join(',')
  const rows = props.items.map(item =>
    cols.map(c => item[c] ?? '').join(',')
  )
  const blob = new Blob(['﻿' + header + '\n' + rows.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = 'stocks.csv'; a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="result-header">
    <span class="result-count">共 <strong>{{ total }}</strong> 只股票</span>
    <span v-if="loading" class="loading">加载中...</span>
    <div class="header-actions">
      <button @click="exportCSV" class="export-btn" :disabled="items.length === 0">导出CSV</button>
    </div>
  </div>
</template>

<style scoped>
.result-header {
  display: flex; align-items: center; gap: 16px; padding: 12px 0;
  border-bottom: 1px solid var(--border); margin-bottom: 8px;
}
.result-count { font-size: 14px; color: var(--text-primary); }
.result-count strong { color: var(--accent); }
.loading { font-size: 12px; color: #f59e0b; }
.header-actions { display: flex; gap: 6px; margin-left: auto; }
.export-btn {
  padding: 2px 10px; border: 1px solid #16a34a; border-radius: 4px;
  background: #f0fdf4; color: #16a34a; font-size: 12px; cursor: pointer;
  margin-left: 8px;
}
.export-btn:disabled { opacity: 0.4; cursor: default; }
.export-btn:hover:not(:disabled) { background: #dcfce7; }
</style>
