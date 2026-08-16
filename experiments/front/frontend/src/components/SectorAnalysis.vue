<template>
  <div ref="rootRef" class="sector-page">
    <!-- 板块搜索工具 -->
    <div class="sector-add-tool">
      <div class="row">
        <el-input
          v-model="searchInput"
          placeholder="输入 THS 板块名称，如：白酒概念"
          size="large"
          clearable
          class="sector-input"
          @keyup.enter="handleSearch"
        />
        <el-button type="primary" size="large" @click="handleSearch">🔍 搜索</el-button>
      </div>

      <!-- 候选板块确认(点击某候选才拉排名) -->
      <div v-if="candidates.length > 0 && !currentSector" class="row">
        <div class="candidate-box">
          <div class="candidate-tip">请确认板块名称：</div>
          <div class="candidate-list">
            <button
              v-for="c in candidates"
              :key="c.ts_code"
              class="candidate-chip"
              @click="handlePick(c)"
            >
              {{ c.name }}
              <span class="cand-count">{{ c.ts_code }} · {{ c.member_count }} 只</span>
            </button>
          </div>
        </div>
      </div>

      <!-- 当前已确认板块 -->
      <div v-if="currentSector" class="row">
        <div class="result-box has-results">
          <span>{{ currentSector.name }}（{{ currentSector.ts_code }}，{{ currentSector.member_count }} 只成分股）</span>
        </div>
        <el-button text @click="resetSector">↩ 重新选择</el-button>
      </div>
    </div>

    <!-- 涨幅排名表格 -->
    <div v-if="stocks.length > 0" class="rank-card">
      <div class="table-header">
        <span>📈 {{ currentSector?.name }} 涨幅排名 TOP{{ stocks.length }}</span>
        <span class="table-info">{{ rankInfo }}</span>
      </div>
      <el-table
        ref="tableRef"
        :data="stocks"
        row-key="ts_code"
        class="rank-table"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="42" />
        <el-table-column prop="rank" label="排名" width="64" align="center">
          <template #default="{ row }">
            <span class="rank-no" :class="{ 'rank-top3': row.rank <= 3 }">{{ row.rank }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="股票名称" width="110" />
        <el-table-column prop="ts_code" label="代码" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.ts_code }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="涨幅" width="95" align="right">
          <template #default="{ row }">
            <span :class="chgClass(row.chg_pct)">{{ fmtPct(row.chg_pct) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="涨停" width="60" align="center">
          <template #default="{ row }">
            <span v-if="row.is_limit_up" class="limit-up-mark">⚡</span>
          </template>
        </el-table-column>
        <el-table-column label="主力增量" width="115" align="right">
          <template #default="{ row }">
            <span :class="flowClass(row.main_inflow_wan)">{{ fmtWan(row.main_inflow_wan) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="主力金额" width="115" align="right">
          <template #default="{ row }">
            <span :class="flowClass(row.main_inflow_pct)">{{ fmtFlowPct(row.main_inflow_pct) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="成交额" width="115" align="right">
          <template #default="{ row }">
            {{ fmtWan(row.amount_wan) }}
          </template>
        </el-table-column>
        <el-table-column label="换手率" width="95" align="right">
          <template #default="{ row }">
            {{ row.turnover_rate != null ? row.turnover_rate.toFixed(2) + '%' : '-' }}
          </template>
        </el-table-column>
      </el-table>

      <!-- 生成对比分析报告 -->
      <div class="gen-bar">
        <el-button
          type="success"
          size="large"
          :disabled="selectedCount === 0 || running"
          @click="handleGenerate"
        >
          🚀 生成对比分析报告（已选 {{ selectedCount }} 只）
        </el-button>
        <span v-if="stocks.length > 0" class="gen-tip">
          默认勾选前 11 只，可自行调整；生成后到【文档】标签页查看报告
        </span>
      </div>
    </div>

    <!-- 生成进度(页面内展示, v-show 挂载下切换标签页不中断) -->
    <div v-if="taskId || doneInfo" class="sector-progress">
      <div class="table-header">
        <span>📝 对比分析报告生成进度</span>
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
        {{ doneInfo.ok ? '✅ 对比分析报告已生成，请到【文档】标签页查看' : '❌ ' + doneInfo.error }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'

const rootRef = ref(null)
const searchInput = ref('')
const candidates = ref([])
const currentSector = ref(null)     // {ts_code, name, member_count}
const stocks = ref([])
const tableRef = ref(null)
const selectedCount = ref(0)
const rankInfo = ref('')
const taskId = ref('')
const running = ref(false)
const events = ref([])
const doneInfo = ref(null)

let es = null

// 板块服务直连(SSE 需无缓冲直连, 不走 8320 代理; 与公司分析直连 8323 同款)
const SECTOR_BASE = `http://${window.location.hostname}:8324`
const REPORT_BASE = `http://${window.location.hostname}:8326`

// ── 搜索 → 候选确认 ──
async function handleSearch() {
  const name = searchInput.value.trim()
  if (!name) return
  try {
    const res = await fetch(`${SECTOR_BASE}/api/sector/search?name=${encodeURIComponent(name)}`)
    if (res.status === 404) {
      candidates.value = []
      ElMessage.warning(`未找到包含「${name}」的板块`)
      return
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    candidates.value = data.items || []
    if (candidates.value.length === 0) {
      ElMessage.warning('未找到匹配的板块，请检查名称')
    }
  } catch {
    ElMessage.error(`无法连接板块服务(${SECTOR_BASE})，请确认服务已启动`)
  }
}

async function handlePick(c) {
  currentSector.value = { ...c }
  candidates.value = []
  try {
    const res = await fetch(`${SECTOR_BASE}/api/sector/rank?ts_code=${encodeURIComponent(c.ts_code)}`)
    if (!res.ok) {
      const msg = await res.text()
      ElMessage.error(`获取排名失败: ${msg}`)
      return
    }
    const data = await res.json()
    stocks.value = data.stocks || []
    rankInfo.value = data.trade_date
      ? `数据日期 ${data.trade_date}（${data.data_time || ''}）· ${data.member_with_snapshot ?? 0} 只成分有快照`
      : ''
    if (stocks.value.length === 0) {
      ElMessage.warning('该板块暂无快照数据')
      return
    }
    // 默认勾选前 11 只
    await nextTick()
    stocks.value.forEach((row, i) => {
      if (i < 11) tableRef.value?.toggleRowSelection(row, true)
    })
    relayout()
  } catch {
    ElMessage.error(`无法连接板块服务(${SECTOR_BASE})，请确认服务已启动`)
  }
}

function resetSector() {
  currentSector.value = null
  stocks.value = []
  rankInfo.value = ''
}

// ── 表格布局重算 ──
// 本组件在 Main.vue 中 v-show 挂载(保 SSE 进度), 初始挂载时 display:none,
// el-table 宽度测量为 0 → scrollX/列宽计算错误 → 横向滚动时表头不同步。
// doLayout() 重算列宽并 rAF 同步一次表头位置, 修复此问题。
let relayoutTimer = null
function relayout() {
  clearTimeout(relayoutTimer)
  relayoutTimer = setTimeout(() => {
    tableRef.value?.doLayout?.()
  }, 60)
}
let ro = null
onMounted(() => {
  // 切回标签页(v-show 显示)时尺寸从 0 恢复, ResizeObserver 触发 → 强制重算
  if (typeof ResizeObserver !== 'undefined' && rootRef.value) {
    ro = new ResizeObserver(() => { relayout() })
    ro.observe(rootRef.value)
  }
})

function onSelectionChange(rows) {
  selectedCount.value = rows.length
}

// ── 生成对比分析报告(提交 8326) ──
async function handleGenerate() {
  if (running.value || selectedCount.value === 0) return
  const selected = tableRef.value?.getSelectionRows?.() || []
  const names = selected.map(r => r.name)
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  try {
    const res = await fetch(`${REPORT_BASE}/api/compare/reports`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sector_name: currentSector.value.name,
        stocks: names,
        username: user.name || user.username || null,
      }),
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
    percent.value = 0
    stageTarget.value = 0
    stageText.value = ''
    stopTicker()
    subscribe(data.task_id)
  } catch {
    ElMessage.error(`无法连接报告服务(${REPORT_BASE})，请确认服务已启动`)
  }
}

// ── 经验进度(仿公司分析: 排队 0-3%, 登录 3-12%, 生成 12-90%, 收尾 90-100%) ──
// 板块报告整份一次生成(无逐股区间): generating 直接进 90%
const percent = ref(0)
const stageTarget = ref(0)
const stageText = ref('')
let ticker = null

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
      // 整份报告一次生成: 进度条缓慢爬向 90%(经验上限), 到达即停
      setStage(90, `正在生成「${data.sector_name}」${data.count} 只股票的合并分析报告…`)
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
      setStage(100, `全部完成：${data.files?.length ?? 0} 份报告`)
      stopTicker()
      break
    case 'task_failed':
      stopTicker()
      break
  }
}

// 服务端 SSE 事件都带 event: 字段, 必须逐类型注册
const SSE_EVENT_TYPES = [
  'task_queued', 'login_started', 'login_ok', 'login_failed',
  'generating', 'quota_switching', 'retrying', 'all_quota_exhausted',
  'task_done', 'task_failed',
]

function onSseEvent(type, e) {
  const data = JSON.parse(e.data)
  events.value.push({ seq: data.seq, ts: data.ts, type: data.type, ...data })
  if (events.value.length > 50) events.value.splice(0, events.value.length - 50)
  if (type === 'task_done') {
    running.value = false
    // 整份报告粒度: failed 非空即整体失败, 展示失败原因(如积分耗尽)
    doneInfo.value = (data.failed?.length ?? 0) > 0
      ? { ok: false, error: data.failed[0].error }
      : { ok: true }
  }
  if (type === 'task_failed') {
    running.value = false
    doneInfo.value = { ok: false, error: data.error }
  }
  handleSseEvent(data)
  if (type === 'task_done' || type === 'task_failed') es.close()
}

function subscribe(id) {
  es = new EventSource(`${REPORT_BASE}/api/compare/reports/${id}/events`)
  for (const t of SSE_EVENT_TYPES) {
    es.addEventListener(t, (e) => onSseEvent(t, e))
  }
  es.onerror = () => {
    // 连接断开: EventSource 自动重连(服务端会重放事件)
  }
}

const progressText = ref('')
watch([running, doneInfo, stageText], () => {
  if (running.value) {
    progressText.value = stageText.value || '生成中…'
  } else {
    progressText.value = ''
  }
})

// ── 展示格式化 ──
function chgClass(v) {
  if (v == null || v === 0) return 'num-flat'
  return v > 0 ? 'num-up' : 'num-down'
}
function flowClass(v) {
  if (v == null || v === 0) return 'num-flat'
  return v > 0 ? 'num-up' : 'num-down'
}
function fmtPct(v) {
  if (v == null) return '-'
  return `${v > 0 ? '+' : ''}${v.toFixed(2)}%`
}
function fmtFlowPct(v) {
  if (v == null) return '-'
  return `${v > 0 ? '+' : ''}${v.toFixed(2)}%`
}
function fmtWan(v) {
  if (v == null) return '-'
  if (Math.abs(v) >= 10000) return `${(v / 10000).toFixed(2)}亿`
  return `${Math.round(v).toLocaleString()}万`
}
function fmtTime(ts) {
  const d = new Date(ts * 1000)
  const p = (n) => String(n).padStart(2, '0')
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

function evClass(ev) {
  if (ev.type === 'task_done') return 'ok'
  if (['task_failed', 'login_failed'].includes(ev.type)) return 'err'
  if (['generating', 'login_started', 'quota_switching', 'retrying'].includes(ev.type)) return 'busy'
  return ''
}

function evText(ev) {
  switch (ev.type) {
    case 'task_queued': return `任务已入队，队列位置 ${ev.position}`
    case 'login_started': return ev.reason === 'quota_switch' ? '积分不足，正在登录备用账号…' : '正在登录妙想账号…'
    case 'login_ok': return `账号登录成功（Key ${ev.key_prefix}…）`
    case 'login_failed': return `账号登录失败：${ev.reason}`
    case 'generating': return `正在生成「${ev.sector_name}」${ev.count} 只股票的合并分析报告…`
    case 'quota_switching': return '检测到积分不足，正在切换备用账号…'
    case 'retrying': return `正在使用备用账号重试「${ev.stock}」…`
    case 'all_quota_exhausted': return '今日全部账号积分已用尽'
    case 'task_done': return (ev.failed?.length ?? 0) > 0
      ? `生成失败：${ev.failed[0].error}`
      : `全部完成：${ev.files?.length ?? 0} 份报告`
    case 'task_failed': return `任务失败：${ev.error}`
    default: return ev.type
  }
}

onBeforeUnmount(() => {
  if (es) es.close()
  stopTicker()
  ro?.disconnect()
  clearTimeout(relayoutTimer)
})
</script>

<style scoped>
.sector-add-tool {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 4px rgba(74, 55, 40, 0.06);
  margin-bottom: 20px;
}
.row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.row + .row { margin-top: 16px; }
.sector-input { flex: 1; min-width: 180px; }

.candidate-box { flex: 1; min-width: 260px; }
.candidate-tip { font-size: 0.85rem; color: var(--wood-400); margin-bottom: 8px; }
.candidate-list { display: flex; flex-wrap: wrap; gap: 8px; }
.candidate-chip {
  border: 1.5px solid var(--wood-300);
  background: var(--wood-50);
  border-radius: 16px;
  padding: 6px 14px;
  font-size: 0.95rem;
  color: var(--wood-700);
  cursor: pointer;
  transition: all 0.15s;
}
.candidate-chip:hover {
  border-color: var(--green-400);
  background: #eef8ee;
  color: var(--green-500);
}
.cand-count { font-size: 0.75rem; color: var(--wood-400); margin-left: 4px; }

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

.rank-card, .sector-progress {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(74, 55, 40, 0.06);
  margin-bottom: 20px;
  overflow: hidden;
}
.table-header {
  padding: 14px 20px;
  font-size: 0.9rem; font-weight: 600;
  color: var(--wood-600);
  border-bottom: 1px solid var(--wood-100);
  display: flex; align-items: center; justify-content: space-between;
}
.table-info { font-weight: 400; font-size: 0.85rem; color: var(--wood-400); }

.rank-table { padding: 0 4px 4px; }
/* 数值列禁换行: 列宽足够时一行显示, 避免数字折行占两行 */
.rank-table :deep(.cell) { white-space: nowrap; }
.rank-no { font-weight: 600; color: var(--wood-500); }
.rank-top3 { color: var(--red-400); }

.num-up { color: #c62828; font-variant-numeric: tabular-nums; }
.num-down { color: #2e7d32; font-variant-numeric: tabular-nums; }
.num-flat { color: var(--wood-600); font-variant-numeric: tabular-nums; }
.limit-up-mark { font-size: 14px; }

.gen-bar {
  padding: 14px 20px;
  border-top: 1px solid var(--wood-100);
  display: flex; align-items: center; gap: 14px;
  flex-wrap: wrap;
}
.gen-tip { font-size: 0.82rem; color: var(--wood-400); }

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
