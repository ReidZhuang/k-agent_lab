/**
 * API 封装
 */
const BASE = '/api'

function getToken() {
  return localStorage.getItem('token') || ''
}

async function request(method, url, data = null) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = token

  const opts = { method, headers }
  if (data) opts.body = JSON.stringify(data)

  const resp = await fetch(`${BASE}${url}`, opts)
  if (resp.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    window.location.hash = '#/login'
    throw new Error('未登录')
  }
  if (resp.headers.get('content-type')?.includes('application/json')) {
    return resp.json()
  }
  // 文件下载
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp
}

// ── 认证 ──
export const login = (username, password) =>
  request('POST', '/auth/login', { username, password })

export const me = () => request('GET', '/auth/me')

// ── 股票搜索 ──
export const searchStock = (q) =>
  request('GET', `/stock/search?q=${encodeURIComponent(q)}`)

export const resolveStocks = (names) =>
  request('POST', '/stock/resolve', { stock_names: names })

// ── 股票池 ──
export const getStockPool = () => request('GET', '/stock/pool')

export const addToPool = (names) =>
  request('POST', '/stock/pool', { stock_names: names })

export const removeFromPool = (tsCode) =>
  request('DELETE', `/stock/pool/${tsCode}`)

// ── 文件浏览 ──
export const listFiles = (path = '') =>
  request('GET', `/explorer/list?path=${encodeURIComponent(path)}`)

export const getFileContent = (path) =>
  request('GET', `/explorer/content?path=${encodeURIComponent(path)}`)

export function downloadFile(path) {
  const token = getToken()
  const url = `${BASE}/explorer/download?path=${encodeURIComponent(path)}`
  return fetch(url, { headers: { Authorization: token } })
}

export function downloadBatch(paths) {
  const token = getToken()
  return fetch(`${BASE}/explorer/download-batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: token },
    body: JSON.stringify({ paths }),
  })
}

// ── 收藏 ──
export const getFavorites = () => request('GET', '/explorer/favorites')

export const addFavorite = (filePath, fileName) =>
  request('POST', '/explorer/favorites', { file_path: filePath, file_name: fileName })

export const removeFavorite = (path) =>
  request('DELETE', `/explorer/favorites?path=${encodeURIComponent(path)}`)

// ── 文件删除 ──
export const deleteFile = (path) =>
  request('DELETE', `/explorer/delete?path=${encodeURIComponent(path)}`)

// ── 股小神聊天 ──
export const listChatSessions = () => request('GET', '/chat/sessions')

export const createChatSession = (convId, title = '') =>
  request('POST', '/chat/sessions', { conv_id: convId, title })

export const deleteChatSession = (convId) =>
  request('DELETE', `/chat/sessions/${convId}`)

export const listChatMessages = (convId) =>
  request('GET', `/chat/sessions/${convId}/messages`)

export const appendChatMessage = (convId, role, content) =>
  request('POST', `/chat/sessions/${convId}/messages`, { role, content })

// 重新生成：删除会话最后一条 assistant 回复（保留触发它的 user 问句）
export const deleteLastAssistant = (convId) =>
  request('DELETE', `/chat/sessions/${convId}/assistant`)

// 记录 喜欢/不喜欢 反馈（dislike 时后端抓 skill 快照）
export const sendFeedback = (convId, messageId, feedback) =>
  request('POST', '/chat/feedback', { conv_id: convId, message_id: messageId, feedback })

// 保存成文档（写 .md 到用户空间；query 用于 TextRank 生成文件名）
export const writeDocument = (filename, content, dirPath, query) =>
  request('POST', '/explorer/write', { filename, content: content || '', dir_path: dirPath || '', query: query || '' })

/**
 * 流式对话（走后端代理，token 不进浏览器）
 * @param {string} convId 会话 ID
 * @param {Array<{role:string,content:string}>} messages 完整历史
 * @param {(delta:string)=>void} onDelta 每块内容回调（打字机效果）
 * @param {AbortSignal} signal 停止生成时 abort
 * @param {boolean} persistLastUser 重新生成重放历史时传 false，避免末条 user query 重复落库
 */
export async function chatStream(convId, messages, onDelta, signal, persistLastUser = true) {
  const token = getToken()
  const resp = await fetch(`${BASE}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: token },
    body: JSON.stringify({ conv_id: convId, messages, persist_last_user: persistLastUser }),
    signal,
  })
  if (resp.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    window.location.hash = '#/login'
    throw new Error('未登录')
  }
  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`
    try {
      const d = await resp.json()
      if (d.detail) msg = d.detail
    } catch { /* 非 JSON 错误体 */ }
    throw new Error(msg)
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop() // 保留不完整行
    for (const line of lines) {
      if (!line.startsWith('data:')) continue
      const data = line.slice(5).trim()
      if (data === '[DONE]') return
      try {
        const json = JSON.parse(data)
        // 代理透传的 SSE 错误帧
        if (json.error) throw new Error(json.error.message || '对话服务异常')
        const delta = json.choices?.[0]?.delta?.content
        if (delta) onDelta(delta)
      } catch (e) {
        if (e.message === '对话服务异常') throw e
      }
    }
  }
}
