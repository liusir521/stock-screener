<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ total: number; pageSize: number; modelValue?: number }>()
const emit = defineEmits<{ 'page-change': [page: number]; 'update:modelValue': [page: number] }>()

const currentPage = computed(() => props.modelValue || 1)
const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

const pages = computed(() => {
  const cur = currentPage.value
  const total = totalPages.value
  const result: (number | string)[] = []

  if (total <= 7) {
    for (let i = 1; i <= total; i++) result.push(i)
    return result
  }

  result.push(1)
  if (cur > 3) result.push('...')

  const start = Math.max(2, cur - 1)
  const end = Math.min(total - 1, cur + 1)
  for (let i = start; i <= end; i++) result.push(i)

  if (cur < total - 2) result.push('...')
  result.push(total)

  return result
})

function go(page: number) {
  if (page >= 1 && page <= totalPages.value) {
    emit('page-change', page)
    emit('update:modelValue', page)
  }
}
</script>

<template>
  <div class="pagination" v-if="totalPages > 1">
    <button :disabled="currentPage === 1" @click="go(currentPage - 1)">上一页</button>
    <template v-for="p in pages" :key="p">
      <span v-if="p === '...'" class="ellipsis">...</span>
      <button
        v-else
        :class="{ active: p === currentPage }"
        @click="go(p as number)"
      >{{ p }}</button>
    </template>
    <button :disabled="currentPage === totalPages" @click="go(currentPage + 1)">下一页</button>
  </div>
</template>

<style scoped>
.pagination {
  display: flex; align-items: center; justify-content: center; gap: 4px;
  padding: 12px 0; font-size: 13px;
}
.pagination button {
  min-width: 32px; height: 32px; padding: 0 6px;
  border: 1px solid var(--border-strong); border-radius: 4px;
  background: var(--bg-surface); color: var(--text-secondary); cursor: pointer;
}
.pagination button:hover:not(:disabled):not(.active) { background: var(--bg-hover); }
.pagination button:disabled { opacity: 0.3; cursor: default; }
.pagination button.active {
  background: var(--accent); border-color: var(--accent); color: white;
}
.ellipsis { color: var(--text-muted); padding: 0 4px; }
</style>
