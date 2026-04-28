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
      <span class="range-label">{{ label }}</span>
      <span class="range-value">{{ modelValue[0] }} ~ {{ modelValue[1] }}</span>
    </div>
    <div class="range-inputs">
      <input type="number" :min="min" :max="max" :step="step || 1"
        :value="modelValue[0]" @input="onMinChange" class="range-input" />
      <span class="range-sep">—</span>
      <input type="number" :min="min" :max="max" :step="step || 1"
        :value="modelValue[1]" @input="onMaxChange" class="range-input" />
    </div>
  </div>
</template>

<style scoped>
.range-slider { margin-bottom: 12px; }
.range-header { display: flex; justify-content: space-between; margin-bottom: 4px; }
.range-label { font-size: 13px; color: #94a3b8; }
.range-value { font-size: 12px; color: #60a5fa; }
.range-inputs { display: flex; align-items: center; gap: 8px; }
.range-input {
  width: 80px; padding: 4px 8px; border: 1px solid #475569;
  border-radius: 4px; background: #1e293b; color: #e2e8f0; font-size: 13px;
}
.range-sep { color: #64748b; }
</style>
