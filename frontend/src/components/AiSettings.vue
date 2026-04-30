<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'

const emit = defineEmits<{ close: [] }>()

const apiUrl = ref('')
const modelName = ref('')
const apiKey = ref('')
const hasKey = ref(false)
const saving = ref(false)
const error = ref('')

onMounted(async () => {
  try {
    const config = await api.getAiConfig()
    apiUrl.value = config.api_url
    modelName.value = config.model
    hasKey.value = config.has_key
  } catch {
    error.value = '无法加载配置'
  }
})

async function handleSave() {
  error.value = ''
  saving.value = true
  try {
    await api.saveAiConfig({
      api_url: apiUrl.value.trim(),
      model: modelName.value.trim(),
      api_key: apiKey.value,
    })
    emit('close')
  } catch {
    error.value = '保存失败，请检查后端是否运行'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="ai-settings-overlay" @click.self="emit('close')">
    <div class="ai-settings-dialog">
      <h4>AI 配置</h4>

      <label class="ai-field-label">API 地址</label>
      <input
        v-model="apiUrl"
        type="url"
        placeholder="https://api.openai.com/v1"
        class="ai-input"
      />

      <label class="ai-field-label">模型</label>
      <input
        v-model="modelName"
        type="text"
        placeholder="gpt-4o"
        class="ai-input"
      />

      <label class="ai-field-label">
        API Key
        <span v-if="hasKey && !apiKey" class="ai-key-indicator">(已配置)</span>
      </label>
      <input
        v-model="apiKey"
        type="password"
        placeholder="留空则不修改"
        class="ai-input"
      />

      <p v-if="error" class="ai-error">{{ error }}</p>

      <div class="ai-settings-btns">
        <button class="save-confirm-btn" :disabled="saving" @click="handleSave">
          {{ saving ? '保存中...' : '保存' }}
        </button>
        <button class="cancel-btn" @click="emit('close')">取消</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-settings-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 200;
  display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(2px);
}
.ai-settings-dialog {
  background: var(--bg-surface); padding: 24px; border-radius: var(--radius); width: 380px;
  box-shadow: 0 16px 48px var(--shadow-lg);
  animation: aiDialogIn 0.2s ease;
}
@keyframes aiDialogIn {
  from { transform: scale(0.95); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
.ai-settings-dialog h4 {
  margin-bottom: 14px; color: var(--text-primary); font-size: 15px; font-weight: 700;
}
.ai-field-label {
  display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;
  margin-top: 10px; font-weight: 500;
}
.ai-key-indicator { color: var(--green); font-weight: 400; }
.ai-input {
  width: 100%; padding: 8px 12px; border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm); background: var(--bg-alt); color: var(--text-primary);
  font-size: 13px; margin-bottom: 4px; transition: all var(--transition);
}
.ai-input:focus {
  outline: none; border-color: var(--accent); background: var(--bg-surface);
  box-shadow: 0 0 0 3px rgba(59,130,246,0.1);
}
.ai-input::placeholder { color: var(--text-muted); }
.ai-error { color: var(--red); font-size: 12px; margin-top: 8px; }
.ai-settings-btns {
  display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px;
}
.save-confirm-btn {
  padding: 7px 18px; background: var(--accent); color: white; border: none;
  border-radius: var(--radius-sm); cursor: pointer; font-size: 13px; font-weight: 500;
  transition: all var(--transition);
}
.save-confirm-btn:hover { background: var(--accent-hover); box-shadow: 0 4px 12px rgba(59,130,246,0.3); }
.save-confirm-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.cancel-btn {
  padding: 7px 18px; background: transparent; color: var(--text-secondary);
  border: 1px solid var(--border-strong); border-radius: var(--radius-sm); cursor: pointer;
  font-size: 13px; font-weight: 500; transition: all var(--transition);
}
.cancel-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
</style>
