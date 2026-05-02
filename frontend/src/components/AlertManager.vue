<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'
import type { Alert as AlertType } from '../types'

const CONDITION_LABELS: Record<string, string> = {
  pe_max: 'PE ≤', pe_min: 'PE ≥', pb_max: 'PB ≤', pb_min: 'PB ≥',
  roe_min: 'ROE ≥', market_cap_min: '市值 ≥(亿)', market_cap_max: '市值 ≤(亿)',
  change_pct_min: '涨跌幅 ≥(%)', change_pct_max: '涨跌幅 ≤(%)',
  volume_ratio_min: '量比 ≥', dividend_yield_min: '股息率 ≥(%)',
  revenue_growth_min: '营收增长 ≥(%)', turnover_rate_min: '换手率 ≥(%)',
}

const CONDITION_OPTIONS = Object.entries(CONDITION_LABELS).map(([key, label]) => ({ key, label }))

interface ConditionRow {
  key: string
  value: number | null
}

const alerts = ref<AlertType[]>([])
const loading = ref(false)
const showForm = ref(false)
const editingAlert = ref<AlertType | null>(null)
const formName = ref('')
const formConditions = ref<ConditionRow[]>([])
const formError = ref('')
const expandedIds = ref<Set<string>>(new Set<string>())
const actionLoading = ref<Set<string>>(new Set<string>())

onMounted(fetchAlerts)

async function fetchAlerts() {
  loading.value = true
  try {
    const data = await api.getAlerts()
    alerts.value = data.alerts
  } catch {
    // silently fail
  } finally {
    loading.value = false
  }
}

function conditionSummary(item: AlertType): string {
  const parts: string[] = []
  const conds = item.conditions
  if (!conds) return '无'
  for (const [key, label] of Object.entries(CONDITION_LABELS)) {
    const val = (conds as Record<string, number>)[key]
    if (val !== undefined && val !== null) {
      parts.push(`${label}${val}`)
    }
  }
  return parts.length > 0 ? parts.join(', ') : '无'
}

function openCreateForm() {
  editingAlert.value = null
  formName.value = ''
  formConditions.value = [{ key: 'pe_max', value: null }]
  formError.value = ''
  showForm.value = true
}

function openEditForm(item: AlertType) {
  editingAlert.value = item
  formName.value = item.name
  formError.value = ''
  const conds = item.conditions || {}
  const entries = Object.entries(conds as Record<string, number>)
  if (entries.length === 0) {
    formConditions.value = [{ key: 'pe_max', value: null }]
  } else {
    formConditions.value = entries.map(([k, v]) => ({ key: k, value: v }))
  }
  showForm.value = true
}

function addConditionRow() {
  const used = new Set(formConditions.value.map(r => r.key))
  const next = CONDITION_OPTIONS.find(o => !used.has(o.key))
  if (next) {
    formConditions.value.push({ key: next.key, value: null })
  }
}

function removeConditionRow(index: number) {
  if (formConditions.value.length > 1) {
    formConditions.value.splice(index, 1)
  }
}

function buildConditions(): Record<string, number> {
  const result: Record<string, number> = {}
  for (const row of formConditions.value) {
    if (row.value !== null && row.value !== undefined && row.key) {
      result[row.key] = Number(row.value)
    }
  }
  return result
}

async function handleSave() {
  const name = formName.value.trim()
  if (!name) {
    formError.value = '请输入预警名称'
    return
  }
  const conditions = buildConditions()
  if (Object.keys(conditions).length === 0) {
    formError.value = '请至少设置一个条件'
    return
  }
  formError.value = ''
  try {
    if (editingAlert.value) {
      const updated = await api.updateAlert(editingAlert.value.id, { name, conditions })
      const idx = alerts.value.findIndex(a => a.id === editingAlert.value!.id)
      if (idx >= 0) alerts.value[idx] = updated
    } else {
      const created = await api.createAlert(name, conditions)
      alerts.value.push(created)
    }
    showForm.value = false
  } catch {
    formError.value = '保存失败，请检查后端是否运行'
  }
}

function cancelForm() {
  showForm.value = false
  formError.value = ''
}

function toggleExpand(id: string) {
  const next = new Set(expandedIds.value)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  expandedIds.value = next
}

async function handleDelete(item: AlertType) {
  if (!confirm(`确定要删除预警 "${item.name}" 吗？`)) return
  try {
    await api.deleteAlert(item.id)
    alerts.value = alerts.value.filter(a => a.id !== item.id)
  } catch {
    alert('删除失败')
  }
}

async function handleToggle(item: AlertType) {
  const newEnabled = !item.enabled
  setActionLoading(item.id, true)
  try {
    const updated = await api.updateAlert(item.id, { enabled: newEnabled })
    const idx = alerts.value.findIndex(a => a.id === item.id)
    if (idx >= 0) alerts.value[idx] = updated
  } catch {
    alert('操作失败')
  } finally {
    setActionLoading(item.id, false)
  }
}

async function handleCheck(item: AlertType) {
  setActionLoading(item.id, true)
  try {
    await api.checkAlerts()
    await fetchAlerts()
  } catch {
    alert('检查失败')
  } finally {
    setActionLoading(item.id, false)
  }
}

function setActionLoading(id: string, val: boolean) {
  const next = new Set(actionLoading.value)
  if (val) {
    next.add(id)
  } else {
    next.delete(id)
  }
  actionLoading.value = next
}

function formatValue(val: unknown, decimals = 2): string {
  if (val === null || val === undefined) return '-'
  const n = Number(val)
  if (isNaN(n)) return String(val)
  return n.toFixed(decimals)
}

function changePctClass(pct: unknown): string {
  const n = Number(pct)
  if (n > 0) return 'am-up'
  if (n < 0) return 'am-down'
  return ''
}
</script>

<template>
  <div class="alert-manager">
    <div class="am-header">
      <h3 class="am-title">条件预警</h3>
      <button class="am-create-btn" @click="openCreateForm" v-if="!showForm">+ 新建预警</button>
    </div>

    <!-- Inline form -->
    <div v-if="showForm" class="am-form-card">
      <h4 class="am-form-title">{{ editingAlert ? '编辑预警' : '新建预警' }}</h4>

      <div class="am-form-row">
        <label class="am-form-label">名称</label>
        <input
          v-model="formName"
          type="text"
          placeholder="如：低PE高ROE"
          class="am-input"
          maxlength="100"
        />
      </div>

      <div class="am-conditions-section">
        <div class="am-conditions-header">
          <span class="am-form-label">条件</span>
          <button class="am-add-cond-btn" @click="addConditionRow"
            :disabled="formConditions.length >= CONDITION_OPTIONS.length">
            + 添加条件
          </button>
        </div>
        <div v-for="(row, idx) in formConditions" :key="idx" class="am-condition-row">
          <select v-model="row.key" class="am-select">
            <option v-for="opt in CONDITION_OPTIONS" :key="opt.key" :value="opt.key">{{ opt.label }}</option>
          </select>
          <input
            v-model.number="row.value"
            type="number"
            step="any"
            placeholder="数值"
            class="am-cond-input"
          />
          <button
            v-if="formConditions.length > 1"
            class="am-remove-cond-btn"
            @click="removeConditionRow(idx)"
            title="移除此条件"
          >✕</button>
        </div>
      </div>

      <p v-if="formError" class="am-form-error">{{ formError }}</p>

      <div class="am-form-actions">
        <button class="am-save-btn" @click="handleSave">保存</button>
        <button class="am-cancel-btn" @click="cancelForm">取消</button>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="!loading && !showForm && alerts.length === 0" class="am-empty">
      <p>暂无预警条件，点击"新建预警"开始</p>
    </div>

    <!-- Alert list -->
    <div v-if="alerts.length > 0" class="am-list">
      <div
        v-for="a in alerts"
        :key="a.id"
        class="am-item"
        :class="{ 'am-item-triggered': a.triggered }"
      >
        <div class="am-item-main" @click="toggleExpand(a.id)">
          <div class="am-item-left">
            <div class="am-item-name-row">
              <span class="am-item-name">{{ a.name }}</span>
              <!-- Toggle switch -->
              <label class="am-toggle" @click.stop>
                <input
                  type="checkbox"
                  :checked="a.enabled"
                  @change="handleToggle(a)"
                  :disabled="actionLoading.has(a.id)"
                />
                <span class="am-toggle-slider"></span>
              </label>
            </div>
            <span class="am-item-summary">{{ conditionSummary(a) }}</span>
          </div>
          <div class="am-item-right">
            <!-- Triggered indicator -->
            <span v-if="a.triggered" class="am-triggered on" title="已触发">
              🔔 {{ a.triggered_stocks?.length || 0 }}
            </span>
            <span v-else class="am-triggered off" title="未触发">✓</span>
            <span class="am-expand-arrow">{{ expandedIds.has(a.id) ? '▾' : '▸' }}</span>
          </div>
        </div>

        <!-- Actions bar -->
        <div class="am-item-actions">
          <button class="am-action-btn" @click="handleCheck(a)" :disabled="actionLoading.has(a.id)">
            {{ actionLoading.has(a.id) ? '检查中...' : '检查' }}
          </button>
          <button class="am-action-btn" @click="openEditForm(a)">编辑</button>
          <button class="am-action-btn am-delete-btn" @click="handleDelete(a)">删除</button>
        </div>

        <!-- Expanded triggered stocks -->
        <div v-if="expandedIds.has(a.id) && a.triggered && a.triggered_stocks?.length > 0" class="am-stocks">
          <table class="am-stocks-table">
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th>收盘价</th>
                <th>PE(TTM)</th>
                <th>涨跌幅</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(stock, si) in a.triggered_stocks" :key="si">
                <td class="am-stock-code">{{ stock.code }}</td>
                <td>{{ stock.name }}</td>
                <td class="am-num">{{ formatValue(stock.close) }}</td>
                <td class="am-num">{{ formatValue(stock.pe_ttm, 1) }}</td>
                <td class="am-num" :class="changePctClass(stock.change_pct)">
                  {{ formatValue(stock.change_pct, 1) }}%
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else-if="expandedIds.has(a.id)" class="am-no-stocks">
          暂无触发股票
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.alert-manager {
  padding: 16px 24px;
  max-width: 860px;
}

.am-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.am-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.am-create-btn {
  padding: 7px 16px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition);
}
.am-create-btn:hover {
  background: var(--accent-hover);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

/* Form card */
.am-form-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px var(--shadow);
}
.am-form-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 14px;
}
.am-form-row {
  margin-bottom: 14px;
}
.am-form-label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 4px;
}
.am-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  background: var(--bg-alt);
  color: var(--text-primary);
  font-size: 13px;
  font-family: inherit;
  transition: all var(--transition);
}
.am-input:focus {
  outline: none;
  border-color: var(--accent);
  background: var(--bg-surface);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}
.am-input::placeholder {
  color: var(--text-muted);
}

.am-conditions-section {
  margin-bottom: 14px;
}
.am-conditions-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.am-add-cond-btn {
  padding: 3px 10px;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: 11px;
  cursor: pointer;
  transition: all var(--transition);
}
.am-add-cond-btn:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-light);
}
.am-add-cond-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.am-condition-row {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-bottom: 6px;
}
.am-select {
  padding: 6px 8px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  background: var(--bg-alt);
  color: var(--text-primary);
  font-size: 12px;
  font-family: inherit;
  min-width: 130px;
  cursor: pointer;
  transition: all var(--transition);
}
.am-select:focus {
  outline: none;
  border-color: var(--accent);
}
.am-cond-input {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  background: var(--bg-alt);
  color: var(--text-primary);
  font-size: 13px;
  font-family: inherit;
  transition: all var(--transition);
}
.am-cond-input:focus {
  outline: none;
  border-color: var(--accent);
  background: var(--bg-surface);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}
.am-cond-input::placeholder {
  color: var(--text-muted);
}
.am-remove-cond-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 14px;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  line-height: 1;
  flex-shrink: 0;
  transition: all var(--transition);
}
.am-remove-cond-btn:hover {
  background: var(--red);
  color: white;
}

.am-form-error {
  color: var(--red);
  font-size: 12px;
  margin-bottom: 8px;
}

.am-form-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.am-save-btn {
  padding: 7px 18px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition);
}
.am-save-btn:hover {
  background: var(--accent-hover);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}
.am-cancel-btn {
  padding: 7px 18px;
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition);
}
.am-cancel-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

/* Empty */
.am-empty {
  text-align: center;
  padding: 48px 16px;
  color: var(--text-muted);
  font-size: 14px;
}

/* Alert list */
.am-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.am-item {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  transition: all var(--transition);
}
.am-item:hover {
  box-shadow: 0 2px 8px var(--shadow);
}
.am-item-triggered {
  border-left: 3px solid var(--red);
}

.am-item-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  cursor: pointer;
  user-select: none;
  transition: background var(--transition);
}
.am-item-main:hover {
  background: var(--bg-hover);
}

.am-item-left {
  flex: 1;
  min-width: 0;
}
.am-item-name-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 3px;
}
.am-item-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

/* Toggle switch */
.am-toggle {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
  flex-shrink: 0;
}
.am-toggle input {
  opacity: 0;
  width: 0;
  height: 0;
}
.am-toggle-slider {
  position: absolute;
  inset: 0;
  background: var(--border-strong);
  border-radius: 10px;
  cursor: pointer;
  transition: all var(--transition);
}
.am-toggle-slider::before {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  left: 2px;
  bottom: 2px;
  background: white;
  border-radius: 50%;
  transition: all var(--transition);
}
.am-toggle input:checked + .am-toggle-slider {
  background: var(--accent);
}
.am-toggle input:checked + .am-toggle-slider::before {
  transform: translateX(16px);
}
.am-toggle input:disabled + .am-toggle-slider {
  opacity: 0.5;
  cursor: not-allowed;
}

.am-item-summary {
  font-size: 12px;
  color: var(--text-muted);
}

.am-item-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  margin-left: 12px;
}
.am-triggered {
  font-size: 12px;
  font-weight: 600;
}
.am-triggered.on {
  color: var(--red);
}
.am-triggered.off {
  color: var(--green);
}
.am-expand-arrow {
  color: var(--text-muted);
  font-size: 14px;
  width: 16px;
  text-align: center;
}

/* Actions */
.am-item-actions {
  display: flex;
  gap: 6px;
  padding: 0 16px 10px 16px;
}
.am-action-btn {
  padding: 4px 12px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  background: var(--bg-alt);
  color: var(--text-secondary);
  font-size: 11px;
  cursor: pointer;
  font-weight: 500;
  font-family: inherit;
  transition: all var(--transition);
}
.am-action-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-color: var(--accent);
}
.am-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.am-delete-btn:hover:not(:disabled) {
  color: var(--red);
  border-color: var(--red);
  background: rgba(239, 68, 68, 0.08);
}

/* Triggered stocks table */
.am-stocks {
  padding: 0 16px 12px 16px;
}
.am-stocks-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.am-stocks-table th {
  text-align: left;
  padding: 6px 8px;
  background: var(--bg-alt);
  color: var(--text-muted);
  font-weight: 600;
  font-size: 11px;
  border-bottom: 1px solid var(--border);
}
.am-stocks-table td {
  padding: 5px 8px;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
}
.am-stock-code {
  font-family: monospace;
  color: var(--text-secondary);
}
.am-num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.am-up {
  color: var(--red);
}
.am-down {
  color: var(--green);
}
.am-no-stocks {
  padding: 8px 16px 12px 16px;
  color: var(--text-muted);
  font-size: 12px;
}
</style>
