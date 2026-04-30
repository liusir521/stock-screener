<script setup lang="ts">
import { ref, nextTick, watch, onMounted, computed } from 'vue'
import MarkdownIt from 'markdown-it'
import { api } from '../api'
import type { AgentMessage } from '../types'

const emit = defineEmits<{ 'select-stock': [code: string] }>()

const md = new MarkdownIt({ breaks: true })

interface Conversation {
  id: string
  title: string
  messages: { role: string; content: string }[]
  updatedAt: number
}

const STORAGE_KEY = 'agent_conversations'
const ACTIVE_KEY = 'agent_active_conv'
const MAX_MSGS = 60
const WELCOME = '你好！我是 A 股 AI 分析助手。\n\n我可以帮你：\n- **技术分析**："分析贵州茅台的技术形态"\n- **股票筛选**："找 PE 小于 15 且 ROE 大于 20% 的股票"\n- **多股对比**："对比贵州茅台、五粮液和泸州老窖"\n- **市场全景**："今天市场怎么样"\n\n请先点击右上角 ⚙ 配置 AI Key，然后开始提问。'

const messages = ref<{ role: string; content: string }[]>([])
const input = ref('')
const loading = ref(false)
const error = ref('')
const chatBody = ref<HTMLDivElement>()
let abortController: AbortController | null = null

// ── Conversation management ──
const conversations = ref<Conversation[]>([])
const activeId = ref('')
const showSidebar = ref(true)

function loadConversations() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    conversations.value = raw ? JSON.parse(raw) : []
  } catch {
    conversations.value = []
  }
}

function saveConversations() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations.value))
  } catch {
    conversations.value.sort((a, b) => b.updatedAt - a.updatedAt)
    conversations.value = conversations.value.slice(0, 20)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations.value))
  }
}

function saveCurrentConv() {
  const now = Date.now()
  const existing = conversations.value.find(c => c.id === activeId.value)
  if (existing) {
    existing.messages = [...messages.value]
    existing.updatedAt = now
    if (existing.title === '新对话') {
      const firstUser = messages.value.find(m => m.role === 'user')
      if (firstUser) {
        existing.title = firstUser.content.slice(0, 30) + (firstUser.content.length > 30 ? '...' : '')
      }
    }
  } else if (messages.value.length > 1) {
    conversations.value.push({
      id: activeId.value,
      title: '新对话',
      messages: [...messages.value],
      updatedAt: now,
    })
  }
  saveConversations()
}

function newConversation() {
  saveCurrentConv()
  activeId.value = Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
  localStorage.setItem(ACTIVE_KEY, activeId.value)
  messages.value = [{ role: 'assistant', content: WELCOME }]
  error.value = ''
}

function switchConversation(id: string) {
  saveCurrentConv()
  const conv = conversations.value.find(c => c.id === id)
  if (conv) {
    activeId.value = id
    messages.value = [...conv.messages]
    localStorage.setItem(ACTIVE_KEY, activeId.value)
  }
  error.value = ''
  scrollToBottom()
}

function deleteConversation(id: string) {
  conversations.value = conversations.value.filter(c => c.id !== id)
  saveConversations()
  if (id === activeId.value) {
    if (conversations.value.length > 0) {
      switchConversation(conversations.value[0].id)
    } else {
      newConversation()
    }
  }
}

const sortedConvs = computed(() =>
  [...conversations.value].sort((a, b) => b.updatedAt - a.updatedAt)
)

// ── Persistence ──
function saveDebounced() {
  saveCurrentConv()
}

let saveTimer: ReturnType<typeof setTimeout> | null = null
watch(messages, () => {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(saveDebounced, 500)
}, { deep: true })

// ── Init ──
onMounted(() => {
  loadConversations()
  const saved = localStorage.getItem(ACTIVE_KEY)
  if (saved && conversations.value.find(c => c.id === saved)) {
    activeId.value = saved
    const conv = conversations.value.find(c => c.id === saved)!
    messages.value = [...conv.messages]
  } else if (conversations.value.length > 0) {
    activeId.value = conversations.value[0].id
    messages.value = [...conversations.value[0].messages]
  } else {
    activeId.value = Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
    localStorage.setItem(ACTIVE_KEY, activeId.value)
    messages.value = [{ role: 'assistant', content: WELCOME }]
  }
  messages.value = messages.value.slice(-MAX_MSGS)
})

function scrollToBottom() {
  nextTick(() => {
    if (chatBody.value) {
      chatBody.value.scrollTop = chatBody.value.scrollHeight
    }
  })
}

function renderMarkdown(text: string): string {
  return md.render(text)
}

function handleStockClick(event: MouseEvent) {
  const target = event.target as HTMLElement
  if (target.tagName === 'CODE' && target.textContent) {
    const code = target.textContent.trim()
    if (/^\d{6}$/.test(code)) {
      emit('select-stock', code)
    }
  }
}

// ── Context menu ──
const ctxMenu = ref({ show: false, x: 0, y: 0, index: -1 })
const ctxMenuRef = ref<HTMLDivElement>()

function onContextMenu(event: MouseEvent, index: number) {
  event.preventDefault()
  ctxMenu.value = { show: true, x: event.clientX, y: event.clientY, index }
  nextTick(() => {
    if (ctxMenuRef.value) {
      const r = ctxMenuRef.value.getBoundingClientRect()
      if (r.right > window.innerWidth) ctxMenu.value.x -= r.width
      if (r.bottom > window.innerHeight) ctxMenu.value.y -= r.height
    }
  })
}

function hideContextMenu() {
  ctxMenu.value.show = false
}

async function copyMessage(index: number) {
  const raw = messages.value[index]?.content || ''
  try {
    await navigator.clipboard.writeText(raw)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = raw
    ta.style.position = 'fixed'; ta.style.left = '-9999px'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
  hideContextMenu()
}

// ── Send ──
async function send() {
  const text = input.value.trim()
  if (!text || loading.value) return
  input.value = ''
  error.value = ''

  messages.value.push({ role: 'user', content: text })
  const placeholderIdx = messages.value.length
  messages.value.push({ role: 'assistant', content: '' })
  if (messages.value.length > MAX_MSGS) {
    messages.value.splice(0, messages.value.length - MAX_MSGS)
  }
  scrollToBottom()

  loading.value = true
  abortController = new AbortController()
  try {
    const recent = messages.value.filter(m => m.content).slice(0, -1).slice(-24)
    const history: { role: string; content: string }[] = recent.map(m => ({ role: m.role, content: m.content }))

    const resp = await api.agentChatStream(text, history, abortController.signal)
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
      throw new Error(err.detail || `HTTP ${resp.status}`)
    }

    const reader = resp.body!.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    let toolEl: HTMLDivElement | null = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })

      const parts = buf.split('\n\n')
      buf = parts.pop() || ''

      for (const part of parts) {
        if (!part.trim()) continue
        const lines = part.split('\n')
        let eventType = ''
        let data = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) eventType = line.slice(7).trim()
          else if (line.startsWith('data: ')) data = line.slice(6)
        }

        if (eventType === 'token') {
          messages.value[placeholderIdx].content += JSON.parse(data)
        } else if (eventType === 'tool_start') {
          const info = JSON.parse(data)
          const nameMap: Record<string, string> = {
            analyze_stock: '正在分析股票...',
            search_stocks: '正在筛选股票...',
            compare_stocks: '正在对比股票...',
            get_market_breadth: '正在获取市场全景...',
          }
          const label = nameMap[info.name] || `正在执行 ${info.name}...`
          if (chatBody.value) {
            toolEl = document.createElement('div')
            toolEl.className = 'tool-status'
            toolEl.textContent = label
            chatBody.value.appendChild(toolEl)
            scrollToBottom()
          }
        } else if (eventType === 'tool_done') {
          if (toolEl) { toolEl.remove(); toolEl = null }
        } else if (eventType === 'error') {
          throw new Error(JSON.parse(data))
        }
      }
    }
    scrollToBottom()
  } catch (e: unknown) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      if (!messages.value[placeholderIdx].content.trim()) {
        messages.value.splice(placeholderIdx, 1)
      }
    } else {
      const errMsg = e instanceof Error ? e.message : String(e)
      if (!messages.value[placeholderIdx].content) {
        messages.value.splice(placeholderIdx, 1)
      }
      error.value = errMsg || '请求失败，请检查后端是否运行'
    }
  } finally {
    loading.value = false
    abortController = null
  }
}

function stop() {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
}

watch(messages, () => scrollToBottom(), { deep: true })
</script>

<template>
  <div class="agent-chat">
    <!-- Sidebar -->
    <div class="chat-sidebar" :class="{ collapsed: !showSidebar }">
      <div class="sidebar-header">
        <span class="sidebar-title">对话列表</span>
        <button class="sidebar-toggle" @click="showSidebar = !showSidebar" title="收起侧栏">◀</button>
      </div>
      <button class="new-chat-btn" @click="newConversation">+ 新对话</button>
      <div class="conv-list">
        <div
          v-for="conv in sortedConvs" :key="conv.id"
          :class="['conv-item', { active: conv.id === activeId }]"
          @click="switchConversation(conv.id)"
        >
          <div class="conv-item-main">
            <span class="conv-item-title">{{ conv.title }}</span>
            <span class="conv-item-time">{{ new Date(conv.updatedAt).toLocaleDateString('zh-CN', { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' }) }}</span>
          </div>
          <button class="conv-del-btn" @click.stop="deleteConversation(conv.id)" title="删除">✕</button>
        </div>
        <div v-if="conversations.length === 0" class="conv-empty">暂无历史对话</div>
      </div>
    </div>

    <!-- Collapsed toggle -->
    <div v-if="!showSidebar" class="sidebar-collapsed-toggle" @click="showSidebar = true" title="展开侧栏">
      <span>▶</span>
    </div>

    <!-- Main chat area -->
    <div class="chat-main">
      <!-- Messages -->
      <div class="chat-body" ref="chatBody" @click="handleStockClick" @click.capture="hideContextMenu">
        <div
          v-for="(msg, i) in messages"
          :key="i"
          :class="['chat-message', msg.role === 'user' ? 'chat-user' : 'chat-ai']"
        >
          <div class="chat-bubble" @contextmenu="onContextMenu($event, i)" v-if="msg.content">
            <div v-if="msg.role === 'assistant'" class="chat-content" v-html="renderMarkdown(msg.content)"></div>
            <div v-else class="chat-content">{{ msg.content }}</div>
          </div>
          <div v-else class="chat-bubble">
            <div class="chat-loading">
              <span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>
            </div>
          </div>
        </div>
        <div v-if="error" class="chat-error">{{ error }}</div>
      </div>

      <!-- Input -->
      <div class="chat-input-area">
        <input
          v-model="input"
          type="text"
          placeholder="输入问题，如'分析一下贵州茅台'..."
          class="chat-input"
          :disabled="loading"
          @keydown.enter.prevent="send"
        />
        <button v-if="loading" class="chat-stop-btn" @click="stop">停止</button>
        <button v-else class="chat-send-btn" :disabled="!input.trim()" @click="send">发送</button>
      </div>
    </div>

    <!-- Context menu -->
    <Teleport to="body">
      <div
        v-if="ctxMenu.show"
        ref="ctxMenuRef"
        class="ctx-menu"
        :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }"
        @click.stop
      >
        <button class="ctx-menu-item" @click="copyMessage(ctxMenu.index)">
          <span class="ctx-icon">📋</span> 复制
        </button>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.agent-chat {
  display: flex; height: calc(100vh - 140px);
  background: var(--bg-surface); border-radius: var(--radius);
  margin: 12px 24px; overflow: hidden; border: 1px solid var(--border);
}

/* ── Sidebar ── */
.chat-sidebar {
  display: flex; flex-direction: column;
  width: 220px; flex-shrink: 0;
  border-right: 1px solid var(--border);
  background: var(--bg-alt);
  transition: width 0.2s ease;
}
.chat-sidebar.collapsed {
  width: 0; overflow: hidden; border-right: none;
}
.sidebar-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 12px; border-bottom: 1px solid var(--border);
}
.sidebar-title {
  font-size: 12px; font-weight: 600; color: var(--text-secondary);
  white-space: nowrap;
}
.sidebar-toggle {
  border: none; background: transparent; color: var(--text-muted);
  font-size: 10px; cursor: pointer; padding: 2px 4px; border-radius: 3px;
  transition: all var(--transition);
}
.sidebar-toggle:hover { background: var(--bg-hover); color: var(--text-primary); }

.sidebar-collapsed-toggle {
  flex-shrink: 0; width: 24px;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-alt); border-right: 1px solid var(--border);
  cursor: pointer; color: var(--text-muted); font-size: 10px;
  transition: all var(--transition);
}
.sidebar-collapsed-toggle:hover { background: var(--bg-hover); color: var(--text-primary); }

.new-chat-btn {
  margin: 8px; padding: 6px 0;
  border: 1px solid var(--accent); border-radius: var(--radius-sm);
  background: var(--accent-light); color: var(--accent);
  font-size: 12px; font-weight: 500;
  cursor: pointer; font-family: inherit; flex-shrink: 0;
  transition: all var(--transition);
}
.new-chat-btn:hover { background: var(--accent); color: white; }

.conv-list {
  flex: 1; overflow-y: auto; padding: 0 4px 8px;
}
.conv-item {
  display: flex; align-items: center; gap: 4px;
  padding: 8px 10px; margin: 2px 4px;
  border-radius: var(--radius-sm); cursor: pointer;
  transition: background var(--transition);
}
.conv-item:hover { background: var(--bg-hover); }
.conv-item.active { background: var(--accent-light); }
.conv-item-main {
  flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px;
}
.conv-item-title {
  font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  color: var(--text-primary);
}
.conv-item.active .conv-item-title { color: var(--accent); font-weight: 600; }
.conv-item-time {
  font-size: 10px; color: var(--text-muted); white-space: nowrap;
}
.conv-del-btn {
  border: none; background: transparent; color: var(--text-muted);
  font-size: 11px; cursor: pointer; padding: 2px 4px; border-radius: 3px;
  flex-shrink: 0; line-height: 1; opacity: 0;
  transition: all var(--transition);
}
.conv-item:hover .conv-del-btn { opacity: 1; }
.conv-del-btn:hover { background: var(--red); color: white; }
.conv-empty {
  padding: 16px; text-align: center; color: var(--text-muted); font-size: 12px;
}

/* ── Main chat area ── */
.chat-main {
  flex: 1; display: flex; flex-direction: column; min-width: 0;
}

/* Body */
.chat-body {
  flex: 1; overflow-y: auto; padding: 20px 24px;
  display: flex; flex-direction: column; gap: 16px;
}
.chat-message { display: flex; }
.chat-user { justify-content: flex-end; }
.chat-ai { justify-content: flex-start; }
.chat-bubble {
  max-width: 75%; padding: 10px 16px; border-radius: 12px;
  font-size: 13px; line-height: 1.7;
  overflow-wrap: break-word; word-break: break-word;
}
.chat-user .chat-bubble {
  background: var(--accent); color: white;
  border-bottom-right-radius: 4px;
}
.chat-ai .chat-bubble {
  background: var(--bg-alt); color: var(--text-primary);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
}
.chat-content :deep(p) { margin: 0 0 8px 0; }
.chat-content :deep(p:last-child) { margin-bottom: 0; }
.chat-content :deep(ul), .chat-content :deep(ol) { margin: 4px 0; padding-left: 20px; }
.chat-content :deep(li) { margin-bottom: 2px; }
.chat-content :deep(code) {
  background: var(--border); padding: 1px 5px; border-radius: 3px;
  font-size: 12px; font-family: monospace; cursor: pointer;
}
.chat-content :deep(code:hover) { background: var(--accent); color: white; }
.chat-content :deep(table) {
  border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 12px;
  display: block; overflow-x: auto;
}
.chat-content :deep(pre) {
  overflow-x: auto; white-space: pre-wrap; word-break: break-all;
}
.chat-content :deep(th) {
  background: var(--border); padding: 5px 8px; text-align: left; font-weight: 600;
}
.chat-content :deep(td) { padding: 4px 8px; border-bottom: 1px solid var(--border); }
.chat-content :deep(strong) { color: var(--text-primary); font-weight: 700; }
.chat-content :deep(h1), .chat-content :deep(h2), .chat-content :deep(h3) {
  font-size: 15px; margin: 12px 0 6px 0; font-weight: 700;
}
.chat-content :deep(blockquote) {
  border-left: 3px solid var(--accent); padding-left: 12px;
  color: var(--text-secondary); margin: 8px 0;
}

.chat-loading { padding: 8px 0; }
.dot {
  display: inline-block; font-size: 24px; line-height: 12px;
  animation: blink 1.4s infinite both; font-weight: bold; color: var(--text-muted);
}
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink {
  0%, 80%, 100% { opacity: 0.2; }
  40% { opacity: 1; }
}

.chat-error {
  padding: 8px 16px; background: rgba(239,68,68,0.1); border: 1px solid var(--red);
  border-radius: var(--radius-sm); color: var(--red); font-size: 12px;
}

/* Input */
.chat-input-area {
  display: flex; gap: 8px; padding: 12px 16px;
  border-top: 1px solid var(--border); background: var(--bg-alt);
}
.chat-input {
  flex: 1; padding: 9px 14px; border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm); background: var(--bg-surface);
  color: var(--text-primary); font-size: 13px; outline: none;
  transition: all var(--transition);
}
.chat-input:focus {
  border-color: var(--accent); box-shadow: 0 0 0 3px rgba(59,130,246,0.1);
}
.chat-input::placeholder { color: var(--text-muted); }
.chat-send-btn {
  padding: 9px 22px; background: var(--accent); color: white; border: none;
  border-radius: var(--radius-sm); font-size: 13px; font-weight: 600;
  cursor: pointer; white-space: nowrap; transition: all var(--transition);
}
.chat-send-btn:hover { background: var(--accent-hover); box-shadow: 0 4px 12px rgba(59,130,246,0.3); }
.chat-send-btn:disabled { opacity: 0.5; cursor: not-allowed; box-shadow: none; }
.chat-stop-btn {
  padding: 9px 22px; background: var(--red); color: white; border: none;
  border-radius: var(--radius-sm); font-size: 13px; font-weight: 600;
  cursor: pointer; white-space: nowrap; transition: all var(--transition);
}
.chat-stop-btn:hover { background: #dc2626; box-shadow: 0 4px 12px rgba(239,68,68,0.3); }

.tool-status {
  padding: 6px 16px; font-size: 12px; color: var(--accent);
  background: var(--accent-light); border-radius: var(--radius-sm);
  align-self: flex-start; animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Context menu */
.ctx-menu {
  position: fixed; z-index: 9999;
  background: var(--bg-surface); border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm); box-shadow: 0 4px 16px var(--shadow-lg);
  padding: 4px; min-width: 100px;
}
.ctx-menu-item {
  display: flex; align-items: center; gap: 6px;
  width: 100%; padding: 6px 10px; border: none; border-radius: 4px;
  background: transparent; color: var(--text-primary); font-size: 12px;
  cursor: pointer; font-family: inherit; text-align: left;
}
.ctx-menu-item:hover { background: var(--accent-light); color: var(--accent); }
.ctx-icon { font-size: 12px; width: 16px; text-align: center; }
</style>
