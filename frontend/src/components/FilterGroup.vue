<script setup lang="ts">
import { ref } from 'vue'
import RangeSlider from './RangeSlider.vue'

const props = defineProps<{
  title: string
  filters: { key: string; label: string; min: number; max: number; step?: number }[]
  modelValue: Record<string, [number, number]>
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, [number, number]>]
}>()

const collapsed = ref(false)

function update(key: string, val: [number, number]) {
  emit('update:modelValue', { ...props.modelValue, [key]: val })
}
</script>

<template>
  <div class="filter-group">
    <div class="filter-group-header" @click="collapsed = !collapsed">
      <span class="filter-group-title">{{ title }}</span>
      <span class="filter-group-arrow">{{ collapsed ? '▶' : '▼' }}</span>
    </div>
    <div v-if="!collapsed" class="filter-group-body">
      <RangeSlider
        v-for="f in filters" :key="f.key"
        :label="f.label" :min="f.min" :max="f.max" :step="f.step"
        :model-value="modelValue[f.key] || [f.min, f.max]"
        @update:model-value="(val: [number, number]) => update(f.key, val)"
      />
    </div>
  </div>
</template>

<style scoped>
.filter-group {
  border: 1px solid var(--border); border-radius: var(--radius); margin-bottom: 10px;
  overflow: hidden; box-shadow: 0 1px 3px var(--shadow);
}
.filter-group-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 9px 12px; background: var(--bg-alt); cursor: pointer;
  user-select: none; transition: background var(--transition);
}
.filter-group-header:hover { background: var(--bg-hover); }
.filter-group-title { font-weight: 700; font-size: 13px; color: var(--text-primary); }
.filter-group-arrow { font-size: 10px; color: var(--text-muted); transition: transform var(--transition); }
.filter-group-body { padding: 10px 12px; }
</style>
