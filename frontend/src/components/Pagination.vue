<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ total: number; pageSize: number; modelValue?: number }>()
const emit = defineEmits<{ 'page-change': [page: number]; 'update:modelValue': [page: number] }>()

const currentPage = computed(() => props.modelValue || 1)
const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

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
    <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
    <button :disabled="currentPage === totalPages" @click="go(currentPage + 1)">下一页</button>
  </div>
</template>

<style scoped>
.pagination {
  display: flex; align-items: center; justify-content: center; gap: 12px;
  padding: 12px 0; font-size: 13px;
}
.pagination button {
  padding: 4px 14px; border: 1px solid #475569; border-radius: 4px;
  background: #1e293b; color: #e2e8f0; cursor: pointer;
}
.pagination button:disabled { opacity: 0.4; cursor: default; }
.page-info { color: #94a3b8; }
</style>
