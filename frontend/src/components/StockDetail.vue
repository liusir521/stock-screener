<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '../api'

const props = defineProps<{ code: string | null }>()
const emit = defineEmits<{ close: [] }>()

const detail = ref<{ basic: Record<string, unknown> | null; daily: Record<string, unknown>[] }>({ basic: null, daily: [] })
const loading = ref(false)

watch(() => props.code, async (newCode) => {
  if (!newCode) { detail.value = { basic: null, daily: [] }; return }
  loading.value = true
  try {
    const data = await api.getStockDetail(newCode)
    detail.value = data as { basic: Record<string, unknown> | null; daily: Record<string, unknown>[] }
  } finally {
    loading.value = false
  }
})

function fmt(val: unknown): string {
  if (val === null || val === undefined) return '-'
  return String(val)
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
        <div v-if="detail.basic" class="detail-grid">
          <div v-for="(val, key) in detail.basic" :key="key" class="detail-item">
            <span class="detail-label">{{ key }}</span>
            <span class="detail-value">{{ fmt(val) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.drawer-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.3); z-index: 100;
  display: flex; justify-content: flex-end;
}
.drawer {
  width: 420px; height: 100%; background: var(--bg-surface); overflow-y: auto;
  padding: 20px; border-left: 1px solid var(--border); box-shadow: -4px 0 20px var(--shadow);
}
.drawer-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.drawer-header h3 { font-size: 18px; margin: 0; color: var(--text-primary); }
.close-btn { background: none; border: none; color: var(--text-muted); font-size: 18px; cursor: pointer; }
.close-btn:hover { color: var(--text-secondary); }
.drawer-loading { color: #f59e0b; text-align: center; padding: 40px 0; }
.drawer-body { font-size: 13px; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.detail-item { background: var(--bg-alt); padding: 8px 10px; border-radius: 6px; border: 1px solid var(--border); }
.detail-label { color: var(--text-muted); font-size: 11px; display: block; margin-bottom: 2px; }
.detail-value { color: var(--text-primary); font-weight: 500; }
</style>
