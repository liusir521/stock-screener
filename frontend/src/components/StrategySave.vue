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
.strategy-section { margin-top: 8px; border-top: 1px solid var(--border); padding-top: 10px; }
.strategy-btns { display: flex; gap: 6px; margin-bottom: 8px; }
.strategy-btn {
  flex: 1; padding: 5px; border: 1px solid var(--border-strong); border-radius: 4px;
  background: var(--bg-surface); color: var(--text-secondary); font-size: 11px; cursor: pointer;
}
.strategy-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.strategy-list { margin-bottom: 8px; }
.strategy-item {
  padding: 6px 10px; border-radius: 4px; font-size: 12px; cursor: pointer;
  border: 1px solid var(--border); margin-bottom: 4px; color: var(--text-primary);
}
.strategy-item:hover { background: var(--accent-light); border-color: var(--accent); color: var(--accent); }
.strategy-save-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.3); z-index: 200;
  display: flex; align-items: center; justify-content: center;
}
.strategy-save-dialog {
  background: var(--bg-surface); padding: 20px; border-radius: 8px; width: 300px;
  box-shadow: 0 4px 20px var(--shadow);
}
.strategy-save-dialog h4 { margin-bottom: 12px; color: var(--text-primary); }
.strategy-input {
  width: 100%; padding: 6px 10px; border: 1px solid var(--border-strong); border-radius: 4px;
  background: var(--bg-surface); color: var(--text-primary); font-size: 13px; margin-bottom: 12px;
}
.strategy-input:focus { outline: none; border-color: var(--accent); }
.strategy-save-btns { display: flex; gap: 8px; justify-content: flex-end; }
.save-confirm-btn {
  padding: 5px 16px; background: var(--accent); color: white; border: none;
  border-radius: 4px; cursor: pointer; font-size: 13px;
}
.save-confirm-btn:hover { background: var(--accent-hover); }
.cancel-btn {
  padding: 5px 16px; background: transparent; color: var(--text-secondary);
  border: 1px solid var(--border-strong); border-radius: 4px; cursor: pointer; font-size: 13px;
}
.cancel-btn:hover { background: var(--bg-hover); }
</style>
