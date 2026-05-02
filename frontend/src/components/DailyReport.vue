<script setup lang="ts">
import { ref, onMounted } from 'vue'
import MarkdownIt from 'markdown-it'
import { api } from '../api'

const md = new MarkdownIt({ breaks: true })

const report = ref('')
const date = ref('')
const generatedAt = ref('')
const loading = ref(false)
const error = ref('')

function renderMarkdown(text: string): string {
  return md.render(text)
}

async function fetchReport() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.getDailyReport()
    report.value = data.report
    date.value = data.date
    generatedAt.value = data.generated_at
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '获取日报失败，请检查后端是否运行'
  } finally {
    loading.value = false
  }
}

async function copyReport() {
  try {
    await navigator.clipboard.writeText(report.value)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = report.value
    ta.style.position = 'fixed'
    ta.style.left = '-9999px'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
}

onMounted(fetchReport)
</script>

<template>
  <div class="daily-report">
    <div class="report-card">
      <div class="report-header">
        <h2 class="report-title">今日市场日报</h2>
        <div v-if="date" class="report-meta">
          <span class="report-date">{{ date }}</span>
          <span v-if="generatedAt" class="report-time">{{ new Date(generatedAt).toLocaleTimeString('zh-CN') }}</span>
        </div>
      </div>

      <div class="report-actions">
        <button class="action-btn" :disabled="loading" @click="fetchReport">刷新报告</button>
        <button class="action-btn" :disabled="!report" @click="copyReport">导出</button>
      </div>

      <div v-if="loading" class="report-loading">
        <span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>
        <span class="loading-text">AI 正在生成市场日报...</span>
      </div>

      <div v-else-if="error" class="report-error">{{ error }}</div>

      <div v-else-if="report" class="report-content" v-html="renderMarkdown(report)"></div>
    </div>
  </div>
</template>

<style scoped>
.daily-report {
  padding: 16px 24px;
  display: flex;
  justify-content: center;
}

.report-card {
  max-width: 820px;
  width: 100%;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: 0 1px 3px var(--shadow);
  padding: 24px;
}

.report-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.report-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.report-meta {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: var(--text-muted);
}

.report-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}

.action-btn {
  padding: 6px 16px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all var(--transition);
  font-family: inherit;
}

.action-btn:hover:not(:disabled) {
  background: var(--accent-light);
  color: var(--accent);
  border-color: var(--accent);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.report-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 48px 0;
  justify-content: center;
  color: var(--text-muted);
  font-size: 14px;
}

.report-error {
  padding: 16px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid var(--red);
  border-radius: var(--radius-sm);
  color: var(--red);
  font-size: 13px;
}

.report-content {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-primary);
}

.report-content :deep(p) { margin: 0 0 10px 0; }
.report-content :deep(p:last-child) { margin-bottom: 0; }
.report-content :deep(ul), .report-content :deep(ol) { margin: 6px 0; padding-left: 20px; }
.report-content :deep(li) { margin-bottom: 4px; }
.report-content :deep(code) {
  background: var(--border);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 12px;
  font-family: monospace;
}
.report-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 10px 0;
  font-size: 13px;
}
.report-content :deep(th) {
  background: var(--border);
  padding: 6px 10px;
  text-align: left;
  font-weight: 600;
}
.report-content :deep(td) { padding: 5px 10px; border-bottom: 1px solid var(--border); }
.report-content :deep(strong) { color: var(--text-primary); font-weight: 700; }
.report-content :deep(h1), .report-content :deep(h2), .report-content :deep(h3) {
  font-size: 16px;
  margin: 16px 0 8px 0;
  font-weight: 700;
}
.report-content :deep(blockquote) {
  border-left: 3px solid var(--accent);
  padding-left: 12px;
  color: var(--text-secondary);
  margin: 10px 0;
}

.dot {
  display: inline-block;
  font-size: 24px;
  line-height: 12px;
  animation: blink 1.4s infinite both;
  font-weight: bold;
  color: var(--text-muted);
}
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink {
  0%, 80%, 100% { opacity: 0.2; }
  40% { opacity: 1; }
}
</style>
