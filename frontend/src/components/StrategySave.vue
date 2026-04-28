<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

const props = defineProps<{ activeFilters: Record<string, string> }>()
const emit = defineEmits<{ 'load': [filters: Record<string, string>] }>()

const strategies = ref<{ name: string; filters: Record<string, string> }[]>([])
const showSave = ref(false)
const saveName = ref('')
const showList = ref(false)

onMounted(async () => {
  const data = await api.getStrategies()
  strategies.value = data.strategies
})

async function handleSave() {
  if (!saveName.value.trim()) return
  await api.saveStrategy(saveName.value.trim(), props.activeFilters)
  strategies.value = strategies.value.filter(s => s.name !== saveName.value.trim())
  strategies.value.push({ name: saveName.value.trim(), filters: { ...props.activeFilters } })
  saveName.value = ''
  showSave.value = false
}

function handleLoad(name: string) {
  const s = strategies.value.find(s => s.name === name)
  if (s) emit('load', s.filters)
  showList.value = false
}
</script>

<template>
  <div class="strategy-section">
    <div class="strategy-btns">
      <button class="strategy-btn" @click="showList = !showList">加载策略</button>
      <button class="strategy-btn" @click="showSave = true">保存策略</button>
    </div>

    <div v-if="showList" class="strategy-list">
      <div v-for="s in strategies" :key="s.name" class="strategy-item" @click="handleLoad(s.name)">
        {{ s.name }}
      </div>
    </div>

    <div v-if="showSave" class="strategy-save-overlay" @click.self="showSave = false">
      <div class="strategy-save-dialog">
        <h4>保存筛选策略</h4>
        <input v-model="saveName" placeholder="策略名称" class="strategy-input" />
        <div class="strategy-save-btns">
          <button @click="handleSave" class="save-confirm-btn">保存</button>
          <button @click="showSave = false" class="cancel-btn">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.strategy-section { margin-top: 8px; border-top: 1px solid #334155; padding-top: 10px; }
.strategy-btns { display: flex; gap: 6px; margin-bottom: 8px; }
.strategy-btn {
  flex: 1; padding: 5px; border: 1px solid #475569; border-radius: 4px;
  background: #1e293b; color: #94a3b8; font-size: 11px; cursor: pointer;
}
.strategy-list { margin-bottom: 8px; }
.strategy-item {
  padding: 6px 10px; border-radius: 4px; font-size: 12px; cursor: pointer;
  border: 1px solid #334155; margin-bottom: 4px;
}
.strategy-item:hover { background: #1e3a5f; border-color: #3b82f6; color: #60a5fa; }
.strategy-save-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 200;
  display: flex; align-items: center; justify-content: center;
}
.strategy-save-dialog {
  background: #1e293b; padding: 20px; border-radius: 8px; width: 300px;
}
.strategy-save-dialog h4 { margin-bottom: 12px; }
.strategy-input {
  width: 100%; padding: 6px 10px; border: 1px solid #475569; border-radius: 4px;
  background: #0f172a; color: #e2e8f0; font-size: 13px; margin-bottom: 12px;
}
.strategy-save-btns { display: flex; gap: 8px; justify-content: flex-end; }
.save-confirm-btn {
  padding: 5px 16px; background: #3b82f6; color: white; border: none;
  border-radius: 4px; cursor: pointer; font-size: 13px;
}
.cancel-btn {
  padding: 5px 16px; background: transparent; color: #94a3b8;
  border: 1px solid #475569; border-radius: 4px; cursor: pointer; font-size: 13px;
}
</style>
