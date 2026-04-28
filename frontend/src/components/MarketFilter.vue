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
.market-filter { margin-bottom: 14px; }
.filter-group-title { font-weight: 600; font-size: 13px; color: var(--text-primary); }
.market-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.market-chip {
  padding: 4px 12px; border: 1px solid var(--border-strong); border-radius: 4px;
  background: var(--bg-surface); color: var(--text-secondary); font-size: 12px; cursor: pointer;
}
.market-chip.active { background: var(--accent-light); border-color: var(--accent); color: var(--accent); }
.market-chip:hover:not(.active) { background: var(--bg-hover); }
</style>
