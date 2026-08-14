<template>
  <div class="report-page">
    <!-- 股票输入工具 -->
    <div class="report-add-tool">
      <div class="row">
        <el-input
          v-model="searchInput"
          placeholder="输入股票名称或代码，逗号分隔多只"
          size="large"
          clearable
          class="stock-input"
          @keyup.enter="handleSearch"
        />
        <el-button type="primary" size="large" @click="handleSearch">🔍 查询</el-button>
      </div>
      <div v-if="searchResults.length > 0" class="row">
        <div class="result-box has-results">
          <span>{{ resultText }}</span>
        </div>
        <el-button type="success" size="large" :disabled="running" @click="handleGenerate">
          🚀 生成报告
        </el-button>
      </div>
    </div>

    <!-- 生成进度(页面内展示, 非悬浮; 切换标签页回来仍可见) -->
    <div v-if="taskId || doneInfo" class="report-progress">
      <div class="table-header">
        <span>📝 报告生成进度</span>
        <span class="table-info">{{ progressText }}</span>
      </div>

      <div v-if="running" class="progress-bar-wrap">
        <div class="progress-bar-fill" :style="{ width: Math.round(percent) + '%' }"></div>
        <span class="progress-percent">{{ Math.round(percent) }}%</span>
      </div>

      <div class="event-list">
        <div v-for="ev in events" :key="ev.seq" class="event-item" :class="evClass(ev)">
          <span class="ev-time">{{ fmtTime(ev.ts) }}</span>
          <span class="ev-text">{{ evText(ev) }}</span>
        </div>
      </div>

      <div v-if="doneInfo" class="done-box" :class="{ ok: doneInfo.ok }">
        {{ doneInfo.ok ? '✅ 分析报告已生成，请在文件中浏览' : '❌ ' + doneInfo.error }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { resolveStocks } from '../api/index.js'

const searchInput = ref('')
const searchResults = ref([])
const resultText = ref('')
const taskId = ref('')
const running = ref(false)
const events = ref([])
const doneInfo = ref(null)
const total = ref(0)
const completed = ref(0)

let es = null

// 报告服务直连(SSE 需无缓冲代理, 文档建议直连 8323)
const REPORT_BASE = `http://${window.location.hostname}:8323`

watch(searchResults, (val) => {
  resultText.value = val.map(r => `${r.name}(${r.ts_code})`).join(' · ')
})

async function handleSearch() {
  const input = searchInput.value.trim()
  if (!input) return
  const names = input.split(/[,，、\s]+/).filter(Boolean)
  try {
    const data = await resolveStocks(names)
    searchResults.value = data.results || []
    if (searchResults.value.length === 0) {
      ElMessage.warning('未找到匹配的股票，请检查名称')
    }
  } catch {
    ElMessage.error('查询失败')
  }
}

async function handleGenerate() {
  if (running.value || searchResults.value.length === 0) return
  const names = searchResults.value.map(r => r.name)
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  try {
    const res = await fetch(`${REPORT_BASE}/api/reports`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stocks: names, username: user.name || user.username || null }),
    })
    if (!res.ok) {
      const msg = await res.text()
      ElMessage.error(`创建任务失败: ${msg}`)
      return
    }
    const data = await res.json()
    taskId.value = data.task_id
    events.value = []
    doneInfo.value = null
    running.value = true
    total.value = names.length
    completed.value = 0
    percent.value = 0
    stageTarget.value = 0
    stageText.value = ''
    stopTicker()
    subscribe(data.task_id)
  } catch {
    ElMessage.error(`无法连接报告服务(${REPORT_BASE})，请确认服务已启动`)
  }
}

// ── 经验进度: 按事件阶段推进(占比依据实测: 登录态复用 12s / 完整登录 70s / 生成 220s 级) ──
// 阶段分布: 排队 0-3%, 登录 3-12%, 生成 12-90%(多只均分), 收尾 90-100%
const percent = ref(0)
const stageTarget = ref(0)
const stageText = ref('')
let ticker = null

// 设定当前阶段的经验百分比上限; 进度条缓慢爬升, 到上限即停, 事件到达后跳到下一段
function setStage(target, label) {
  stageTarget.value = Math.max(stageTarget.value, target)
  if (label) stageText.value = label
  if (!ticker) {
    ticker = setInterval(() => {
      const diff = stageTarget.value - percent.value
      if (diff > 0.5) {
        percent.value = Math.min(stageTarget.value, percent.value + diff / 8 + 0.3)
      }
    }, 800)
  }
}
function stopTicker() {
  if (ticker) { clearInterval(ticker); ticker = null }
}

// 每只股票的生成区间(在 12%-90% 之间均分)
const genStart = (i, n) => 12 + 78 * (i / n)
const genEnd = (i, n) => 12 + 78 * ((i + 1) / n)

function handleSseEvent(data) {
  switch (data.type) {
    case 'task_queued':
      setStage(3, `任务已入队，队列位置 ${data.position}…`)
      break
    case 'login_started':
      setStage(6, data.reason === 'quota_switch' ? '积分不足，正在登录备用账号…' : '正在登录妙想账号…')
      break
    case 'login_ok':
      setStage(12, `账号登录成功（Key ${data.key_prefix}…）`)
      break
    case 'login_failed':
      stopTicker()
      break
    case 'generating':
      // 进入该股生成区间: 进度条缓慢爬向该股区间末端(经验上限), 到达即停
      setStage(genEnd(data.index, data.total), `正在生成「${data.stock}」分析报告（${data.index + 1}/${data.total}）…`)
      break
    case 'stock_done':
      setStage(genEnd(data.index, data.total), `「${data.stock}」报告生成完成`)
      break
    case 'stock_failed':
      setStage(genEnd(data.index, data.total), `「${data.stock}」生成失败`)
      break
    case 'quota_switching':
      setStage(stageTarget.value, '检测到积分不足，正在切换备用账号…')
      break
    case 'retrying':
      setStage(stageTarget.value, `正在使用备用账号重试「${data.stock}」…`)
      break
    case 'all_quota_exhausted':
      setStage(92, '今日全部账号积分已用尽')
      break
    case 'task_done':
      setStage(100, `全部完成：${data.files?.length ?? 0} 份成功`)
      stopTicker()
      break
    case 'task_failed':
      stopTicker()
      break
  }
}

// 服务端 SSE 所有事件都带 event: 字段, 必须逐类型注册
// (onmessage 只收无 event 字段的消息, 收不到任何服务端事件)
const SSE_EVENT_TYPES = [
  'task_queued', 'login_started', 'login_ok', 'login_failed',
  'generating', 'stock_done', 'stock_failed',
  'quota_switching', 'retrying', 'all_quota_exhausted',
  'task_done', 'task_failed',
]

function onSseEvent(type, e) {
  const data = JSON.parse(e.data)
  events.value.push({ seq: data.seq, ts: data.ts, type: data.type, ...data })
  if (events.value.length > 50) events.value.splice(0, events.value.length - 50)
  if (type === 'stock_done') completed.value = data.index + 1
  if (type === 'task_done') {
    running.value = false
    doneInfo.value = { ok: true }
  }
  if (type === 'task_failed') {
    running.value = false
    doneInfo.value = { ok: false, error: data.error }
  }
  handleSseEvent(data)
  if (type === 'task_done' || type === 'task_failed') es.close()
}

function subscribe(id) {
  es = new EventSource(`${REPORT_BASE}/api/reports/${id}/events`)
  for (const t of SSE_EVENT_TYPES) {
    es.addEventListener(t, (e) => onSseEvent(t, e))
  }
  es.onerror = () => {
    // 连接断开: EventSource 自动重连(服务端会重放事件)
  }
}

const progressText = ref('')
watch([running, doneInfo, stageText, completed, total], () => {
  if (doneInfo.value) {
    progressText.value = `完成 ${completed.value}/${total.value}`
  } else if (running.value) {
    progressText.value = stageText.value || `进行中 ${completed.value}/${total.value}`
  } else {
    progressText.value = ''
  }
})

function fmtTime(ts) {
  const d = new Date(ts * 1000)
  const p = (n) => String(n).padStart(2, '0')
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

function evClass(ev) {
  if (['task_done', 'stock_done'].includes(ev.type)) return 'ok'
  if (['task_failed', 'stock_failed', 'login_failed'].includes(ev.type)) return 'err'
  if (['generating', 'login_started', 'quota_switching', 'retrying'].includes(ev.type)) return 'busy'
  return ''
}

function evText(ev) {
  switch (ev.type) {
    case 'task_queued': return `任务已入队，队列位置 ${ev.position}`
    case 'login_started': return ev.reason === 'quota_switch' ? '积分不足，正在登录备用账号…' : '正在登录妙想账号…'
    case 'login_ok': return `账号登录成功（Key ${ev.key_prefix}…）`
    case 'login_failed': return `账号登录失败：${ev.reason}`
    case 'generating': return `正在生成「${ev.stock}」分析报告（${ev.index + 1}/${ev.total}）…`
    case 'stock_done': return `「${ev.stock}」报告生成完成`
    case 'stock_failed': return `「${ev.stock}」生成失败：${ev.error}`
    case 'quota_switching': return '检测到积分不足，正在切换备用账号…'
    case 'retrying': return `正在使用备用账号重试「${ev.stock}」…`
    case 'all_quota_exhausted': return '今日全部账号积分已用尽'
    case 'task_done': return `全部完成：${ev.files?.length ?? 0} 份成功`
    case 'task_failed': return `任务失败：${ev.error}`
    default: return ev.type
  }
}

onBeforeUnmount(() => {
  if (es) es.close()
  stopTicker()
})
</script>

<style scoped>
.report-add-tool {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 4px rgba(74, 55, 40, 0.06);
  margin-bottom: 20px;
}
.row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.row + .row { margin-top: 16px; }
.stock-input { flex: 1; min-width: 180px; }
.result-box {
  flex: 1; min-width: 200px;
  height: 44px; padding: 0 16px;
  background: var(--wood-50);
  border: 1.5px dashed var(--wood-300);
  border-radius: 8px;
  display: flex; align-items: center;
  font-size: 1rem; color: var(--wood-600);
}
.result-box.has-results { border-style: solid; border-color: var(--green-400); color: var(--wood-800); }

.report-progress {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(74, 55, 40, 0.06);
}
.table-header {
  padding: 14px 20px;
  font-size: 0.9rem; font-weight: 600;
  color: var(--wood-600);
  border-bottom: 1px solid var(--wood-100);
  display: flex; align-items: center; justify-content: space-between;
}
.table-info { font-weight: 400; font-size: 0.85rem; color: var(--wood-400); }
.progress-bar-wrap {
  margin: 16px 20px 0;
  background: var(--wood-100);
  border-radius: 6px; height: 10px; overflow: hidden;
  position: relative;
}
.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--wood-400), var(--wood-500));
  border-radius: 6px;
  transition: width 0.3s ease;
}
.progress-percent {
  position: absolute; right: 6px; top: -14px;
  font-size: 0.75rem; color: var(--wood-500);
  font-variant-numeric: tabular-nums;
}
.event-list { padding: 12px 20px 8px; max-height: 320px; overflow-y: auto; }
.event-item {
  display: flex; gap: 12px; align-items: baseline;
  padding: 5px 0;
  font-size: 0.88rem; color: var(--wood-600);
  border-bottom: 1px dashed var(--wood-50);
}
.event-item:last-child { border-bottom: none; }
.event-item.ok { color: var(--green-500); }
.event-item.err { color: var(--red-400); }
.event-item.busy { color: #b0782e; }
.ev-time { font-variant-numeric: tabular-nums; color: var(--wood-400); font-size: 0.8rem; white-space: nowrap; }
.ev-text { flex: 1; }
.done-box {
  margin: 0 20px 18px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 0.95rem; font-weight: 600;
  color: var(--red-400);
  background: #fdf0ef;
}
.done-box.ok {
  color: var(--green-500);
  background: #eef8ee;
}
</style>
