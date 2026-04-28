<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const markets = ref<{ key: string; label: string }[]>([])

onMounted(async () => {
  const data = await api.getMarkets()
  markets.value = data.markets
})
</script>

<template>
  <div class="market-filter">
    <div class="filter-group-title" style="margin-bottom: 6px;">市场板块</div>
    <div class="market-chips">
      <button
        v-for="m in markets" :key="m.key"
        :class="['market-chip', { active: modelValue === m.key }]"
        @click="emit('update:modelValue', m.key)"
      >{{ m.label }}</button>
    </div>
  </div>
</template>

<style scoped>
.market-filter { margin-bottom: 16px; }
.filter-group-title { font-weight: 700; font-size: 13px; color: var(--text-primary); margin-bottom: 6px; }
.market-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.market-chip {
  padding: 5px 14px; border: 1px solid var(--border-strong); border-radius: 20px;
  background: var(--bg-surface); color: var(--text-secondary); font-size: 12px;
  cursor: pointer; font-weight: 500; transition: all var(--transition);
}
.market-chip.active {
  background: var(--accent); border-color: var(--accent); color: white;
  box-shadow: 0 2px 8px rgba(59,130,246,0.3);
}
.market-chip:hover:not(.active) { background: var(--bg-hover); color: var(--text-primary); }
</style>
