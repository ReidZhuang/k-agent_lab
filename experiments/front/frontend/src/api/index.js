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
