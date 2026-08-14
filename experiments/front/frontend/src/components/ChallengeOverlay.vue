<template>
  <Teleport to="body">
    <div v-if="chal" class="cap-overlay">
      <div class="cap-card">
        <div class="cap-head">
          <span class="cap-warn">⚠️</span>
          <span>妙想登录需要完成拼图验证</span>
          <span class="cap-timer" :class="{ urgent: left <= 20 }">{{ left }}s</span>
        </div>
        <div
          ref="stageEl"
          class="cap-stage"
          :style="{ width: bgW + 'px', height: bgH + 'px' }"
          @pointerdown="onDown"
          @pointermove="onMove"
          @pointerup="onUp"
          @pointercancel="onUp"
        >
          <img :src="bgSrc" class="cap-bg" alt="" draggable="false" />
          <div
            class="cap-slice"
            :style="{
              left: posX + 'px',
              top: sliderY + 'px',
              width: sliceW + 'px',
              height: sliceH + 'px',
              backgroundImage: 'url(' + sliceSrc + ')',
            }"
          ></div>
        </div>
        <p class="cap-tip" :class="{ ok: done }">{{ tip }}</p>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const chal = ref(null)
const posX = ref(0)
const tip = ref('')
const left = ref(120)
const done = ref(false)
const stageEl = ref(null)

const bgW = computed(() => chal.value?.bg_w ?? 260)
const bgH = computed(() => chal.value?.bg_h ?? 160)
const sliceW = computed(() => chal.value?.slice_w ?? 54)
const sliceH = computed(() => chal.value?.slice_h ?? 54)
const sliderY = computed(() => chal.value?.slider_y ?? 0)
const bgSrc = computed(() => (chal.value ? 'data:image/png;base64,' + chal.value.bg : ''))
const sliceSrc = computed(() => (chal.value ? 'data:image/png;base64,' + chal.value.slice : ''))

let pollTimer = null
let countdownTimer = null
let dragging = false
let downX = 0
let downAt = 0
let track = []
let submittedId = null

async function poll() {
  let c = null
  try {
    const res = await fetch('/login-exp/challenge')
    if (res.ok) c = await res.json()
  } catch {
    /* 挑战服务未启动, 忽略 */
  }
  if (c) {
    if (!chal.value || chal.value.id !== c.id) {
      // 新拼图(首次出现或失败/超时后重试)
      chal.value = c
      posX.value = c.slider_x
      submittedId = null
      track = []
      dragging = false
      done.value = false
      tip.value = '请按住滑块向右拖到缺口位置'
      startCountdown(c.expires_at)
    }
  } else if (chal.value && submittedId) {
    // 挑战消失且已提交 → 验证通过
    done.value = true
    tip.value = '✅ 验证通过，登录继续…'
    stopCountdown()
    setTimeout(() => {
      chal.value = null
    }, 1800)
  }
}

function startCountdown(expiresAt) {
  stopCountdown()
  left.value = Math.max(0, Math.round(expiresAt - Date.now() / 1000))
  countdownTimer = setInterval(() => {
    left.value = Math.max(0, Math.round(expiresAt - Date.now() / 1000))
    if (left.value <= 0 && !submittedId) tip.value = '拼图已过期，等待新拼图…'
  }, 1000)
}

function stopCountdown() {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

function onDown(e) {
  if (!chal.value || submittedId) return
  dragging = true
  downX = posX.value
  downAt = performance.now()
  track = []
  tip.value = '拖动中…'
  stageEl.value.setPointerCapture(e.pointerId)
  e.preventDefault()
}

function onMove(e) {
  if (!dragging) return
  const rect = stageEl.value.getBoundingClientRect()
  let x = e.clientX - rect.left - sliceW.value / 2
  x = Math.max(0, Math.min(x, bgW.value - sliceW.value))
  posX.value = x
  const t = Math.round(performance.now() - downAt)
  // 采样节流: 至少 16ms 一个点, 避免轨迹文件过大
  if (!track.length || t - track[track.length - 1].t >= 16) {
    track.push({
      x: Math.round(x * 10) / 10,
      y: Math.round((e.clientY - rect.top) * 10) / 10,
      t,
    })
  }
}

async function onUp() {
  if (!dragging) return
  dragging = false
  const duration = Math.round(performance.now() - downAt)
  const distance = Math.round((posX.value - downX) * 10) / 10
  submittedId = chal.value.id
  tip.value = '已提交，等待验证…'
  try {
    const res = await fetch('/login-exp/result', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: chal.value.id, distance, track, duration }),
    })
    if (!res.ok) tip.value = '提交被拒(拼图可能已过期)，等待新拼图…'
  } catch {
    tip.value = '提交失败，请检查服务后重新拖动'
  }
}

onMounted(() => {
  pollTimer = setInterval(poll, 1500)
  poll()
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
  stopCountdown()
})
</script>

<style scoped>
.cap-overlay {
  position: fixed;
  inset: 0;
  z-index: 10000;
  background: rgba(20, 30, 50, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(2px);
}
.cap-card {
  background: #fff;
  border-radius: 12px;
  padding: 22px 26px 20px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
  user-select: none;
}
.cap-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 14px;
}
.cap-warn {
  font-size: 18px;
}
.cap-timer {
  margin-left: auto;
  font-weight: 700;
  color: #b0782e;
  font-variant-numeric: tabular-nums;
}
.cap-timer.urgent {
  color: #e64545;
  animation: cap-blink 1s infinite;
}
@keyframes cap-blink {
  50% {
    opacity: 0.4;
  }
}
.cap-stage {
  position: relative;
  border-radius: 6px;
  overflow: hidden;
  cursor: grab;
  touch-action: none;
  border: 1px solid #e2e2e2;
}
.cap-stage:active {
  cursor: grabbing;
}
.cap-bg {
  display: block;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.cap-slice {
  position: absolute;
  background-repeat: no-repeat;
  background-size: contain;
  pointer-events: none;
}
.cap-tip {
  margin-top: 12px;
  text-align: center;
  font-size: 13px;
  color: #7a5f45;
  min-height: 18px;
}
.cap-tip.ok {
  color: #2f9e44;
  font-weight: 600;
}
</style>
