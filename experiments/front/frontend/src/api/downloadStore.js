/**
 * 下载进度状态管理
 */
import { ref, provide, inject } from 'vue'

const STORE_KEY = Symbol('downloadStore')

// 全局状态
const visible = ref(false)
const title = ref('正在转换文档')
const fileName = ref('')
const fileCount = ref(0)
const progress = ref(0)
const status = ref('progress') // progress | done | error
const errorMsg = ref('')
let progressTimer = null

export function createDownloadStore() {
  return { show, done, error, hide, status, visible, title, fileName, fileCount, progress, errorMsg }
}

export function provideDownloadStore() {
  const store = createDownloadStore()
  provide(STORE_KEY, store)
  return store
}

export function useDownloadStore() {
  return inject(STORE_KEY, createDownloadStore())
}

function show(t, files) {
  title.value = t || '正在转换文档'
  status.value = 'progress'
  progress.value = 0
  visible.value = true

  if (files && files.length === 1) {
    fileName.value = files[0].split('/').pop() || files[0]
    fileCount.value = 0
  } else {
    fileName.value = ''
    fileCount.value = files ? files.length : 0
  }

  let p = 0
  clearInterval(progressTimer)
  progressTimer = setInterval(() => {
    p += Math.random() * 15
    if (p >= 90) {
      p = 90
      clearInterval(progressTimer)
    }
    progress.value = Math.min(p, 90)
  }, 500)
}

function done() {
  clearInterval(progressTimer)
  progress.value = 100
  status.value = 'done'
}

function error(msg) {
  clearInterval(progressTimer)
  status.value = 'error'
  errorMsg.value = msg || '转换失败'
}

function hide() {
  visible.value = false
  clearInterval(progressTimer)
}
