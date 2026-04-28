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
.strategy-section { margin-top: 10px; border-top: 1px solid var(--border); padding-top: 12px; }
.strategy-btns { display: flex; gap: 6px; margin-bottom: 8px; }
.strategy-btn {
  flex: 1; padding: 6px 8px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  background: var(--bg-surface); color: var(--text-secondary); font-size: 12px;
  cursor: pointer; font-weight: 500; transition: all var(--transition);
}
.strategy-btn:hover { background: var(--bg-hover); color: var(--text-primary); border-color: var(--accent); }
.strategy-list { margin-bottom: 8px; }
.strategy-item {
  padding: 7px 12px; border-radius: var(--radius-sm); font-size: 13px; cursor: pointer;
  border: 1px solid var(--border); margin-bottom: 4px; color: var(--text-primary);
  transition: all var(--transition);
}
.strategy-item:hover {
  background: var(--accent-light); border-color: var(--accent); color: var(--accent);
  box-shadow: 0 2px 6px var(--shadow);
}
.strategy-save-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 200;
  display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(2px);
}
.strategy-save-dialog {
  background: var(--bg-surface); padding: 24px; border-radius: var(--radius); width: 320px;
  box-shadow: 0 16px 48px var(--shadow-lg);
  animation: dialogIn 0.2s ease;
}
@keyframes dialogIn {
  from { transform: scale(0.95); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
.strategy-save-dialog h4 { margin-bottom: 14px; color: var(--text-primary); font-size: 15px; font-weight: 700; }
.strategy-input {
  width: 100%; padding: 8px 12px; border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm); background: var(--bg-alt); color: var(--text-primary);
  font-size: 13px; margin-bottom: 14px; transition: all var(--transition);
}
.strategy-input:focus {
  outline: none; border-color: var(--accent); background: var(--bg-surface);
  box-shadow: 0 0 0 3px rgba(59,130,246,0.1);
}
.strategy-save-btns { display: flex; gap: 8px; justify-content: flex-end; }
.save-confirm-btn {
  padding: 7px 18px; background: var(--accent); color: white; border: none;
  border-radius: var(--radius-sm); cursor: pointer; font-size: 13px; font-weight: 500;
  transition: all var(--transition);
}
.save-confirm-btn:hover { background: var(--accent-hover); box-shadow: 0 4px 12px rgba(59,130,246,0.3); }
.cancel-btn {
  padding: 7px 18px; background: transparent; color: var(--text-secondary);
  border: 1px solid var(--border-strong); border-radius: var(--radius-sm); cursor: pointer;
  font-size: 13px; font-weight: 500; transition: all var(--transition);
}
.cancel-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
</style>
