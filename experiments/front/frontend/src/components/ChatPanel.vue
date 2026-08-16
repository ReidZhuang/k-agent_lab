<template>
  <div class="chat-panel">
    <!-- 顶部会话选择条：最左大加号 + 横向可拖动标签 -->
    <div class="session-bar">
      <button class="new-chat-btn" title="开启新的聊天" @click="newChat">＋</button>
      <div
        ref="sessionTabsRef"
        class="session-tabs"
        @mousedown="onTabsMouseDown"
      >
        <div
          v-for="s in sessions"
          :key="s.conv_id"
          class="session-tab"
          :class="{ active: s.conv_id === currentConvId }"
          @click="switchSession(s.conv_id)"
        >
          <span class="session-title">{{ s.title }}</span>
          <span class="session-del" title="删除会话" @click.stop="removeSession(s.conv_id)">×</span>
        </div>
      </div>
    </div>

    <!-- 主体 -->
    <div class="chat-body">
      <!-- 空态：DeepSeek 首页风格 -->
      <div v-if="!currentConvId || messages.length === 0" class="chat-hero">
        <h1 class="hero-title">🤖 股小神</h1>
        <p class="hero-sub">懂股票的 AI 助手 · 行情 / 财报 / 公告 / 板块分析</p>
        <div class="hero-input-wrap">
          <textarea
            ref="heroInputRef"
            v-model="input"
            class="chat-input"
            rows="1"
            placeholder="问点什么…（Enter 发送，Shift+Enter 换行）"
            @keydown.enter.exact.prevent="send"
            @keydown.shift.enter.stop
            @input="autoGrow($event)"
          ></textarea>
          <button class="send-btn" :disabled="!input.trim() || streaming" @click="send">发送</button>
        </div>
        <div class="hero-hints">
          <button
            v-for="h in hints"
            :key="h"
            class="hint-chip"
            @click="input = h; $nextTick(() => $refs.heroInputRef && autoGrow({ target: $refs.heroInputRef }))"
          >{{ h }}</button>
        </div>
      </div>

      <!-- 聊天视图 -->
      <template v-else>
        <div ref="listRef" class="chat-list">
          <div v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.role">
            <div class="avatar">{{ m.role === 'user' ? '🧑' : '🤖' }}</div>
            <div class="bubble" v-html="renderMd(m.content)"></div>
          </div>
          <div v-if="streaming" class="msg-row assistant">
            <div class="avatar">🤖</div>
            <div class="bubble streaming" v-html="renderMd(streamingText)"></div>
          </div>
        </div>

        <div class="chat-input-bar">
          <textarea
            ref="chatInputRef"
            v-model="input"
            class="chat-input"
            rows="1"
            placeholder="问点什么…（Enter 发送，Shift+Enter 换行）"
            :disabled="streaming"
            @keydown.enter.exact.prevent="send"
            @keydown.shift.enter.stop
            @input="autoGrow($event)"
          ></textarea>
          <button v-if="!streaming" class="send-btn" :disabled="!input.trim()" @click="send">发送</button>
          <button v-else class="stop-btn" @click="stopGenerate">■ 停止</button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Marked } from 'marked'
import {
  listChatSessions, createChatSession, deleteChatSession,
  listChatMessages, appendChatMessage, chatStream,
} from '../api/index.js'

const marked = new Marked({ gfm: true, breaks: true })

// ── 状态 ──
const sessions = ref([])
const currentConvId = ref('')
const messages = ref([])
const input = ref('')
const streaming = ref(false)
const streamingText = ref('')
// 模板 ref(须在 setup 声明变量, 模板 ref="xxx" 才会绑定; 缺失曾导致引用预填/自动滚动/focus 静默失效)
const heroInputRef = ref(null)
const chatInputRef = ref(null)
const listRef = ref(null)
let abortCtrl = null

const hints = [
  '今天哪些板块涨幅靠前？',
  '帮我分析一下贵州茅台的最新财务数据',
  '创业板今天有什么值得关注的公告？',
]

// 生成会话 ID（非安全上下文不可用 crypto.randomUUID，手动拼接）
function genConvId() {
  return 'c' + Date.now().toString(36) + Math.random().toString(36).slice(2, 10)
}

function renderMd(text) {
  return marked.parse(text || '')
}

// ── 会话管理 ──
async function loadSessions() {
  try {
    const data = await listChatSessions()
    sessions.value = data.sessions || []
  } catch (e) {
    ElMessage.error('加载会话失败：' + (e.message || ''))
  }
}

async function loadMessages(convId) {
  const data = await listChatMessages(convId)
  messages.value = data.messages || []
}

function newChat() {
  stopGenerate(true) // 停止当前流（保留已生成部分），再开新会话
  currentConvId.value = ''
  messages.value = []
  input.value = ''
  streaming.value = false
  nextTick(() => {
    const el = heroInputRef.value || chatInputRef.value
    if (el) el.focus()
  })
}

async function switchSession(convId) {
  if (convId === currentConvId.value) return
  stopGenerate(true)
  currentConvId.value = convId
  messages.value = []
  try {
    await loadMessages(convId)
  } catch (e) {
    ElMessage.error('加载消息失败：' + (e.message || ''))
  }
  scrollToBottom()
}

// ── 文档页「询问股小神」：开新会话并把选中文本作为引用预填进输入框 ──
// 不自动发送：引用内容 + 分隔线后另起一行，等用户输入问题再发送
function newChatWithReference(text, docName = '') {
  newChat() // 复位到首页态(新会话, 不触碰已有会话记录)
  if (!text) return
  const head = docName ? `📎 文档引用：${docName}\n` : '📎 文档引用：\n'
  input.value = `${head}${text}\n━━━━━━━━━━━━━━━━━━━━\n`
  nextTick(() => {
    const el = heroInputRef.value || chatInputRef.value
    if (!el) return
    el.focus()
    const len = el.value.length
    el.setSelectionRange(len, len) // 光标落在分隔线下方新行, 等待输入问题
    el.scrollTop = 0 // 显示引用开头(长引用时框内能看到引用内容, 输入时自动滚到光标)
    autoGrow({ target: el })
  })
}

defineExpose({ newChatWithReference })

async function removeSession(convId) {
  try {
    await ElMessageBox.confirm('确定删除这个聊天吗？', '删除会话', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
  } catch { return }
  try {
    await deleteChatSession(convId)
    sessions.value = sessions.value.filter(s => s.conv_id !== convId)
    if (currentConvId.value === convId) {
      currentConvId.value = ''
      messages.value = []
    }
  } catch (e) {
    ElMessage.error('删除失败：' + (e.message || ''))
  }
}

// ── 发送 / 流式 ──
async function send() {
  const text = input.value.trim()
  if (!text || streaming.value) return
  input.value = ''

  let convId = currentConvId.value
  try {
    // 首页态直接发第一条 → 自动建会话
    if (!convId) {
      convId = genConvId()
      await createChatSession(convId)
      currentConvId.value = convId
    }
  } catch (e) {
    ElMessage.error('创建会话失败：' + (e.message || ''))
    return
  }

  messages.value.push({ role: 'user', content: text })
  streaming.value = true
  streamingText.value = ''
  abortCtrl = new AbortController()
  scrollToBottom()

  const history = messages.value.map(m => ({ role: m.role, content: m.content }))
  try {
    await chatStream(convId, history, delta => {
      streamingText.value += delta
      scrollToBottom()
    }, abortCtrl.signal)
    // 完整回复 → 回存
    if (streamingText.value.trim()) {
      await appendChatMessage(convId, 'assistant', streamingText.value)
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      ElMessage.error('对话失败：' + (e.message || ''))
    }
    // 中断/失败时保留已生成部分到历史，下次继续可接上
    if (streamingText.value.trim()) {
      try { await appendChatMessage(convId, 'assistant', streamingText.value) } catch { /* 忽略 */ }
    }
  } finally {
    streaming.value = false
    // 仅在仍停留在本会话时把回复渲染进列表（切换会话后 abort 的收尾不污染新会话）
    if (currentConvId.value === convId && streamingText.value.trim()) {
      messages.value.push({ role: 'assistant', content: streamingText.value })
    }
    // 刷新会话列表（标题由后端自动生成、updated_at 更新）
    loadSessions()
    scrollToBottom()
  }
}

function stopGenerate(silent = false) {
  if (abortCtrl) {
    abortCtrl.abort()
    abortCtrl = null
  }
  if (!silent) {
    // 点击停止按钮：流已 abort，等待 send() 的 catch/finally 收尾
    streaming.value = false
  }
}

// ── 输入框自适应高度 ──
function autoGrow(e) {
  const el = e.target
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 240) + 'px' // 240px ≈ 8.5 行, 保证输入后可看 ≥5 行
}

// ── 滚动到底部 ──
function scrollToBottom() {
  nextTick(() => {
    const el = listRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

// ── 顶部会话条横向拖拽滚动 ──
const sessionTabsRef = ref(null)
let dragState = null
function onTabsMouseDown(e) {
  // 点击标签/删除按钮时不启动拖拽
  if (e.target.closest('.session-tab')) return
  const el = sessionTabsRef.value
  if (!el || e.button !== 0) return
  dragState = { startX: e.clientX, startLeft: el.scrollLeft, moved: false }
  const onMove = ev => {
    const dx = ev.clientX - dragState.startX
    if (Math.abs(dx) > 3) dragState.moved = true
    el.scrollLeft = dragState.startLeft - dx
  }
  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    dragState = null
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

// ── 初始化 ──
onMounted(async () => {
  await loadSessions()
  // 进入标签页恢复最近会话；没有会话则停留在首页态
  if (sessions.value.length > 0) {
    currentConvId.value = sessions.value[0].conv_id
    await loadMessages(currentConvId.value)
    scrollToBottom()
  }
})

onBeforeUnmount(() => {
  stopGenerate(true)
})

watch([messages, streamingText], () => scrollToBottom())
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 110px);
  min-height: 480px;
  background: #fff;
  border: 1px solid var(--wood-200);
  border-radius: 12px;
  overflow: hidden;
}

/* ═══ 顶部会话选择条 ═══ */
.session-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--wood-100);
  background: var(--wood-50);
  flex-shrink: 0;
}
.new-chat-btn {
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border: 1px dashed var(--wood-300);
  border-radius: 10px;
  background: #fff;
  color: var(--wood-500);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  transition: all 0.15s;
}
.new-chat-btn:hover {
  border-color: var(--wood-400);
  border-style: solid;
  color: var(--wood-700);
  background: #fff;
}
.session-tabs {
  flex: 1;
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 2px;
  cursor: grab;
  scrollbar-width: thin;
}
.session-tabs:active { cursor: grabbing; }
.session-tabs::-webkit-scrollbar { height: 4px; }
.session-tabs::-webkit-scrollbar-thumb { background: var(--wood-200); border-radius: 2px; }
.session-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  max-width: 200px;
  min-width: 110px;
  height: 36px;
  padding: 0 8px 0 12px;
  border: 1px solid var(--wood-200);
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  transition: all 0.15s;
}
.session-tab:hover { border-color: var(--wood-300); }
.session-tab.active {
  border-color: var(--wood-500);
  background: linear-gradient(135deg, var(--wood-400), var(--wood-500));
  color: #fff;
}
.session-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 0.85rem;
}
.session-del {
  flex-shrink: 0;
  font-size: 15px;
  line-height: 1;
  opacity: 0.5;
  border-radius: 4px;
  padding: 1px 4px;
}
.session-tab:hover .session-del { opacity: 1; }
.session-del:hover { background: rgba(255, 255, 255, 0.25); }

/* ═══ 主体 ═══ */
.chat-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  position: relative;
}

/* 空态（DeepSeek 首页风格） */
.chat-hero {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start; /* 空态整体上提(不再垂直居中) */
  padding: 20px 24px;
  padding-top: 7vh;
  gap: 12px;
}
.hero-title {
  font-size: 2.2rem;
  font-weight: 600;
  color: var(--wood-700);
  margin: 0;
}
.hero-sub { font-size: 0.95rem; color: var(--wood-400); margin: 0; }
.hero-input-wrap {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  width: 100%;
  max-width: 960px; /* 空态更宽 */
  margin-top: 12px;
}
.hero-hints {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  max-width: 720px;
}
.hint-chip {
  border: 1px solid var(--wood-200);
  background: #fff;
  border-radius: 14px;
  padding: 5px 12px;
  font-size: 0.8rem;
  color: var(--wood-600);
  cursor: pointer;
  transition: all 0.15s;
}
.hint-chip:hover { border-color: var(--wood-400); color: var(--wood-700); background: var(--wood-50); }

/* 输入框（共用） */
.chat-input {
  flex: 1;
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--wood-200);
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 0.95rem;
  font-family: inherit;
  line-height: 1.5;
  resize: none;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  background: #fff;
}
.chat-input:focus { border-color: var(--wood-400); box-shadow: 0 0 0 2px var(--wood-100); }
.chat-input:disabled { background: var(--wood-50); color: var(--wood-400); }

.send-btn {
  flex-shrink: 0;
  height: 40px;
  padding: 0 22px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--wood-400), var(--wood-500));
  color: #fff;
  font-size: 0.9rem;
  cursor: pointer;
  transition: opacity 0.15s;
}
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.send-btn:not(:disabled):hover { opacity: 0.9; }
.stop-btn {
  flex-shrink: 0;
  height: 40px;
  padding: 0 22px;
  border: 1px solid #e0a0a0;
  border-radius: 10px;
  background: #fff;
  color: #c05656;
  font-size: 0.9rem;
  cursor: pointer;
}
.stop-btn:hover { background: #fdf2f2; }

/* 聊天视图 */
.chat-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.msg-row { display: flex; gap: 10px; max-width: 90%; }
.msg-row.user { align-self: flex-end; flex-direction: row-reverse; }
.avatar {
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  background: var(--wood-100);
}
.msg-row.user .avatar { background: var(--wood-200); }
.bubble {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 0.92rem;
  line-height: 1.7;
  word-break: break-word;
  background: #f7f7f8;
  color: #333;
}
.msg-row.user .bubble {
  background: linear-gradient(135deg, var(--wood-400), var(--wood-500));
  color: #fff;
}
.bubble.streaming { min-height: 28px; }
.bubble.streaming:empty::after {
  content: '▍';
  animation: blink 1s steps(1) infinite;
}
.bubble.streaming:not(:empty)::after {
  content: '▍';
  display: inline-block;
  margin-left: 2px;
  animation: blink 1s steps(1) infinite;
}
@keyframes blink { 50% { opacity: 0; } }

/* 气泡内 markdown */
.bubble :deep(h1) { font-size: 1.3rem; margin: 12px 0 8px; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; }
.bubble :deep(h2) { font-size: 1.15rem; margin: 12px 0 8px; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; }
.bubble :deep(h3) { font-size: 1.05rem; margin: 12px 0 6px; }
.bubble :deep(p) { margin: 6px 0; }
.bubble :deep(code) {
  background: rgba(175, 184, 193, 0.2);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 0.85em;
}
.bubble :deep(pre) {
  background: #f6f8fa;
  border: 1px solid #e5e7eb;
  padding: 10px 14px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 0.85rem;
}
.bubble :deep(pre code) { background: none; padding: 0; }
.bubble :deep(table) { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 0.85rem; }
.bubble :deep(th), .bubble :deep(td) { border: 1px solid #e5e7eb; padding: 6px 10px; text-align: left; }
.bubble :deep(th) { background: var(--wood-50); font-weight: 600; }
.bubble :deep(ul), .bubble :deep(ol) { padding-left: 22px; margin: 6px 0; }
.bubble :deep(li) { margin: 3px 0; }
.bubble :deep(blockquote) {
  border-left: 3px solid var(--wood-300);
  padding: 4px 12px;
  margin: 8px 0;
  color: var(--wood-600);
  background: var(--wood-50);
}
.bubble :deep(a) { color: #0366d6; text-decoration: none; }
.bubble :deep(strong) { font-weight: 600; }
.msg-row.user .bubble :deep(a) { color: #cfe3ff; }

/* 底部输入栏 */
.chat-input-bar {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 14px 24px;
  border-top: 1px solid var(--wood-100);
  background: #fff;
}
.chat-input-bar .chat-input { max-width: none; }

@media (max-width: 768px) {
  .chat-panel { height: calc(100vh - 150px); }
  .msg-row { max-width: 100%; }
}
</style>
