<script setup lang="ts">
const props = defineProps<{
  label: string
  min: number
  max: number
  step?: number
  modelValue: [number, number]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: [number, number]]
}>()

function onMinChange(e: Event) {
  const val = Number((e.target as HTMLInputElement).value)
  emit('update:modelValue', [val, props.modelValue[1]])
}

function onMaxChange(e: Event) {
  const val = Number((e.target as HTMLInputElement).value)
  emit('update:modelValue', [props.modelValue[0], val])
}
</script>

<template>
  <div class="range-slider">
    <div class="range-header">
      <div class="range-label-group">
        <span class="range-label">{{ label }}</span>
        <span class="range-hint">范围 {{ min }} ~ {{ max }}</span>
      </div>
      <span class="range-value">{{ modelValue[0] }} ~ {{ modelValue[1] }}</span>
    </div>
    <div class="range-inputs">
      <input type="number" :min="min" :max="max" :step="step || 1"
        :value="modelValue[0]" @input="onMinChange" class="range-input"
        :placeholder="String(min)" />
      <span class="range-sep">—</span>
      <input type="number" :min="min" :max="max" :step="step || 1"
        :value="modelValue[1]" @input="onMaxChange" class="range-input"
        :placeholder="String(max)" />
    </div>
  </div>
</template>

<style scoped>
.range-slider { margin-bottom: 12px; }
.range-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px; }
.range-label-group { display: flex; flex-direction: column; }
.range-label { font-size: 13px; color: var(--text-secondary); font-weight: 500; }
.range-hint { font-size: 10px; color: var(--text-muted); margin-top: 1px; }
.range-value { font-size: 12px; color: var(--accent); white-space: nowrap; }
.range-inputs { display: flex; align-items: center; gap: 6px; }
.range-input {
  flex: 1; min-width: 0; padding: 4px 8px; border: 1px solid var(--border-strong);
  border-radius: 4px; background: var(--bg-surface); color: var(--text-primary); font-size: 13px;
}
.range-input:focus { outline: none; border-color: var(--accent); }
.range-sep { color: var(--text-muted); font-size: 12px; flex-shrink: 0; }
</style>
