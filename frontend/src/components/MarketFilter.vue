<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { api } from '../api'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const markets = ref<{ key: string; label: string }[]>([])

onMounted(async () => {
  const data = await api.getMarkets()
  markets.value = data.markets
})

const selected = computed({
  get: () => {
    if (!props.modelValue) return []
    return props.modelValue.split(',').filter(Boolean)
  },
  set: (vals: string[]) => {
    emit('update:modelValue', vals.join(','))
  },
})

function toggle(marketKey: string) {
  const current = [...selected.value]
  const idx = current.indexOf(marketKey)
  if (idx >= 0) current.splice(idx, 1)
  else current.push(marketKey)
  selected.value = current
}

function selectAll() {
  emit('update:modelValue', markets.value.map(m => m.key).join(','))
}

function clearAll() {
  emit('update:modelValue', '')
}
</script>

<template>
  <div class="market-filter">
    <div class="filter-group-header">
      <span class="filter-group-title">市场板块</span>
      <span class="filter-group-actions">
        <button class="market-action" @click="selectAll">全选</button>
        <button class="market-action" @click="clearAll">清除</button>
      </span>
    </div>
    <div class="market-chips">
      <label
        v-for="m in markets" :key="m.key"
        :class="['market-chip', { active: selected.includes(m.key) }]"
      >
        <input
          type="checkbox"
          :checked="selected.includes(m.key)"
          class="market-checkbox"
          @change="toggle(m.key)"
        />
        {{ m.label }}
      </label>
    </div>
  </div>
</template>

<style scoped>
.market-filter { margin-bottom: 16px; }
.filter-group-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;
}
.filter-group-title { font-weight: 700; font-size: 13px; color: var(--text-primary); }
.filter-group-actions { display: flex; gap: 4px; }
.market-action {
  background: none; border: none; color: var(--accent); font-size: 11px; cursor: pointer; padding: 0 4px;
}
.market-action:hover { text-decoration: underline; }
.market-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.market-chip {
  padding: 5px 12px; border: 1px solid var(--border-strong); border-radius: 20px;
  background: var(--bg-surface); color: var(--text-secondary); font-size: 12px;
  cursor: pointer; font-weight: 500; transition: all var(--transition);
  display: flex; align-items: center; gap: 4px; user-select: none;
}
.market-chip.active {
  background: var(--accent-light); border-color: var(--accent); color: var(--accent);
  box-shadow: 0 2px 6px rgba(59,130,246,0.2);
}
.market-chip:hover:not(.active) { background: var(--bg-hover); color: var(--text-primary); }
.market-checkbox { display: none; }
</style>
