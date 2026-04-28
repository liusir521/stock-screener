<script setup lang="ts">
const props = defineProps<{ total: number; loading: boolean; items: Record<string, unknown>[] }>()
const emit = defineEmits<{ 'sort-change': [field: string] }>()

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
    <div class="sort-btns">
      <button @click="emit('sort-change', 'pe_ttm')" class="sort-btn">PE</button>
      <button @click="emit('sort-change', 'roe')" class="sort-btn">ROE</button>
      <button @click="emit('sort-change', 'market_cap')" class="sort-btn">市值</button>
      <button @click="exportCSV" class="export-btn" :disabled="items.length === 0">导出CSV</button>
    </div>
  </div>
</template>

<style scoped>
.result-header {
  display: flex; align-items: center; gap: 16px; padding: 12px 0;
  border-bottom: 1px solid #334155; margin-bottom: 8px;
}
.result-count { font-size: 14px; color: #e2e8f0; }
.result-count strong { color: #60a5fa; }
.loading { font-size: 12px; color: #f59e0b; }
.sort-btns { display: flex; gap: 6px; margin-left: auto; }
.sort-btn {
  padding: 2px 10px; border: 1px solid #475569; border-radius: 4px;
  background: #1e293b; color: #94a3b8; font-size: 12px; cursor: pointer;
}
.sort-btn:hover { border-color: #3b82f6; color: #60a5fa; }
.export-btn {
  padding: 2px 10px; border: 1px solid #16a34a; border-radius: 4px;
  background: #1e293b; color: #4ade80; font-size: 12px; cursor: pointer;
  margin-left: 8px;
}
.export-btn:disabled { opacity: 0.4; cursor: default; }
.export-btn:hover:not(:disabled) { background: #166534; }
</style>
