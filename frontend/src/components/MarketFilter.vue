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
.filter-group-title { font-weight: 600; font-size: 13px; }
.market-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.market-chip {
  padding: 4px 12px; border: 1px solid #475569; border-radius: 4px;
  background: #1e293b; color: #94a3b8; font-size: 12px; cursor: pointer;
}
.market-chip.active { background: #1e3a5f; border-color: #3b82f6; color: #60a5fa; }
</style>
