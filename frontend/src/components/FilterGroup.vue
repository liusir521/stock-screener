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
  border: 1px solid var(--border); border-radius: 6px; margin-bottom: 10px; overflow: hidden;
}
.filter-group-header {
  display: flex; justify-content: space-between; padding: 8px 10px;
  background: var(--bg-alt); cursor: pointer; user-select: none;
}
.filter-group-title { font-weight: 600; font-size: 13px; color: var(--text-primary); }
.filter-group-arrow { font-size: 10px; color: var(--text-muted); }
.filter-group-body { padding: 8px 10px; }
</style>
