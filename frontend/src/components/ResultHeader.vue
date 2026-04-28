<script setup lang="ts">
const props = defineProps<{ total: number; loading: boolean; items: Record<string, unknown>[]; visibleCols: string[] }>()

function exportCSV() {
  if (props.items.length === 0) return
  const cols = props.visibleCols
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
  display: flex; align-items: center; gap: 16px; padding: 14px 0 10px;
  border-bottom: 1px solid var(--border); margin-bottom: 8px;
}
.result-count { font-size: 14px; color: var(--text-primary); font-weight: 500; }
.result-count strong { color: var(--accent); font-weight: 700; }
.loading { font-size: 13px; color: var(--accent); font-weight: 500; display: flex; align-items: center; gap: 6px; }
.header-actions { display: flex; gap: 6px; margin-left: auto; }
.export-btn {
  padding: 5px 12px; border: 1px solid var(--green); border-radius: var(--radius-sm);
  background: transparent; color: var(--green); font-size: 12px; font-weight: 500;
  cursor: pointer; transition: all var(--transition);
}
.export-btn:disabled { opacity: 0.4; cursor: default; }
.export-btn:hover:not(:disabled) { background: var(--green); color: white; box-shadow: 0 2px 8px rgba(34,197,94,0.3); }
</style>
