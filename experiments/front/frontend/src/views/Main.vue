<template>
  <div class="main-container">
    <!-- Header -->
    <header class="header-bar">
      <div class="header-left">
        <button class="mobile-menu-btn" @click="sidebarVisible = !sidebarVisible">☰</button>
        <h1>📊 股神的秘密</h1>
      </div>
      <div class="header-right">
        <span class="user-name">{{ userName }}</span>
        <el-button text size="small" style="color:#fff;" @click="handleLogout">退出</el-button>
      </div>
    </header>

    <div class="app-layout">
      <!-- 侧栏 -->
      <aside class="sidebar" :class="{ 'mobile-open': sidebarVisible }">
        <!-- 搜索 -->
        <div class="sidebar-search">
          <div class="search-wrap">
            <span class="search-icon">🔍</span>
            <el-input v-model="searchKeyword" placeholder="搜索股票名称…" clearable size="large" @input="onSearch" />
          </div>
        </div>

        <!-- 收藏夹（可折叠） -->
        <div class="sidebar-section">
          <div class="section-header" @click="favCollapsed = !favCollapsed">
            <span class="label">⭐ 收藏夹 <el-tag size="small" round>{{ favorites.length }}</el-tag></span>
            <span class="collapse-arrow" :class="{ collapsed: favCollapsed }">▼</span>
          </div>
          <div class="collapsible-body" :class="{ hidden: favCollapsed }">
            <div class="fav-list">
              <div v-for="fav in favorites" :key="fav.file_path" class="fav-item" @click="openFile(fav.file_path)">
                <span class="icon">📄</span>
                <span class="name">{{ fav.file_name }}</span>
                <span class="pin">★</span>
              </div>
              <div v-if="favorites.length === 0" class="fav-empty">暂无收藏</div>
            </div>
          </div>
        </div>

        <!-- 文件树 -->
        <div class="sidebar-section tree-section">
          <div class="tree-area-title">
            <span>📁 个人空间</span>
            <div class="sort-controls">
              <el-tooltip content="按名称排序" placement="top">
                <button class="sort-btn" :class="{ active: sortBy === 'name' }" @click="sortBy = 'name'; loadFiles()">📄</button>
              </el-tooltip>
              <el-tooltip content="按时间排序" placement="top">
                <button class="sort-btn" :class="{ active: sortBy === 'mtime' }" @click="sortBy = 'mtime'; loadFiles()">🕐</button>
              </el-tooltip>
              <el-tag size="small" round>{{ userName }}</el-tag>
            </div>
          </div>
          <div class="tree-area">
            <FileTree
              :items="fileTree"
              :selected-files="selectedFiles"
              @toggle-check="toggleFileCheck"
              @open-file="openFile"
              @toggle-fav="toggleFavorite"
              @toggle-dir="toggleDir"
              @delete-file="handleDelete"
            />
          </div>
        </div>

        <!-- 底部操作栏 -->
        <div class="sidebar-footer">
          <el-button size="large" @click="refreshFiles">刷新</el-button>
          <el-button type="danger" size="large" @click="batchDeleteSelected" :disabled="selectedFiles.length === 0">
            🗑 删除
          </el-button>
          <el-button type="primary" size="large" @click="batchDownload" :disabled="selectedFiles.length === 0">
            ⬇ 下载
          </el-button>
        </div>
      </aside>

      <!-- 主区域 -->
      <main class="main-area">
        <div class="tabs-bar">
          <el-tabs v-model="activeTab" @tab-change="onTabChange">
            <el-tab-pane label="📈 股票池" name="pool" />
            <el-tab-pane label="📄 文档" name="doc" />
            <el-tab-pane label="📝 公司分析" name="report" />
          </el-tabs>
        </div>

        <div class="content-area">
          <!-- 股票池标签 -->
          <StockPool v-if="activeTab === 'pool'" />

          <!-- 文档标签 -->
          <DocPreview
            v-if="activeTab === 'doc'"
            :file-path="currentFilePath"
            :file-content="currentFileContent"
          />

          <!-- 公司分析标签(v-show 保持挂载: 切换标签页进度不中断) -->
          <CompanyReport v-show="activeTab === 'report'" />
        </div>

        <!-- 文档页右侧浮动工具栏 -->
        <div v-if="activeTab === 'doc' && currentFilePath" class="doc-float-bar">
          <el-tooltip content="打印文档" placement="left">
            <button class="doc-toolbar-btn" @click="printDocument" title="打印文档">🖨️</button>
          </el-tooltip>
          <div class="doc-toolbar-sep"></div>
          <!-- 预留按钮位（暂空） -->
          <div class="doc-btn-placeholder"></div>
          <div class="doc-btn-placeholder"></div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Marked } from 'marked'
import { me, listFiles, getFileContent, getFavorites, addFavorite, removeFavorite, downloadFile, downloadBatch, deleteFile } from '../api/index.js'
import FileTree from '../components/FileTree.vue'
import StockPool from '../components/StockPool.vue'
import DocPreview from '../components/DocPreview.vue'
import CompanyReport from '../components/CompanyReport.vue'
import { useDownloadStore } from '../api/downloadStore.js'

const router = useRouter()
const userName = ref('')
const sidebarVisible = ref(false)
const activeTab = ref('pool')
const searchKeyword = ref('')
const favCollapsed = ref(false)
const favorites = ref([])
const fileTree = ref([])
const selectedFiles = ref([])
const currentFilePath = ref('')
const currentFileContent = ref('')
const dirExpanded = ref({})
const sortBy = ref('name')

// ── 初始化 ──
onMounted(async () => {
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  if (!user.id) {
    router.push('/login')
    return
  }
  userName.value = user.name || user.username
  try {
    await me()
    loadFiles()
    loadFavorites()
  } catch {
    router.push('/login')
  }
})

function handleLogout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/login')
}

// ── 文件树 ──
async function loadFiles(path = '') {
  try {
    const data = await listFiles(path)
    fileTree.value = buildTree(sortItems(data.items), path)
  } catch { /* ignore */ }
}

function sortItems(items) {
  const copy = [...items]
  if (sortBy.value === 'name') {
    copy.sort((a, b) => {
      if (a.type !== b.type) return a.type === 'dir' ? -1 : 1
      return a.name.localeCompare(b.name, 'zh-CN')
    })
  } else if (sortBy.value === 'mtime') {
    copy.sort((a, b) => {
      if (a.type !== b.type) return a.type === 'dir' ? -1 : 1
      return (b.mtime || 0) - (a.mtime || 0)
    })
  }
  return copy
}

function buildTree(items, parentPath) {
  return items.map(item => ({
    ...item,
    path: item.path || item.name,
    checked: selectedFiles.value.includes(item.path || item.name),
    expanded: dirExpanded.value[item.path || item.name] === true,
    children: [],
  }))
}

async function toggleDir(item) {
  const path = item.path || item.name
  item.expanded = !item.expanded
  dirExpanded.value[path] = item.expanded
  if (item.expanded && item.children.length === 0 && item.type === 'dir') {
    try {
      const data = await listFiles(path)
      item.children = sortItems(data.items).map(child => ({
        ...child,
        path: child.path || `${path}/${child.name}`,
        checked: selectedFiles.value.includes(child.path || `${path}/${child.name}`),
        expanded: dirExpanded.value[child.path || `${path}/${child.name}`] === true,
        children: [],
      }))
    } catch { /* ignore */ }
  }
}

function toggleFileCheck(item) {
  const path = item.path || item.name
  const idx = selectedFiles.value.indexOf(path)
  if (idx >= 0) {
    selectedFiles.value.splice(idx, 1)
    item.checked = false
  } else {
    selectedFiles.value.push(path)
    item.checked = true
  }
}

// ── 打开文件 ──
async function openFile(path) {
  try {
    const data = await getFileContent(path)
    currentFileContent.value = data.content
    currentFilePath.value = path
    activeTab.value = 'doc'
  } catch (e) {
    ElMessage.error('无法打开文件')
  }
}

// ── 收藏 ──
async function loadFavorites() {
  try {
    const data = await getFavorites()
    favorites.value = data.favorites
  } catch { /* ignore */ }
}

async function toggleFavorite(item) {
  const path = item.path || item.name
  try {
    if (item.is_favorite) {
      await removeFavorite(path)
      item.is_favorite = false
    } else {
      await addFavorite(path, item.name)
      item.is_favorite = true
    }
    loadFavorites()
  } catch { /* ignore */ }
}

// ── 删除 ──
async function handleDelete(item) {
  const path = item.path || item.name
  try {
    await ElMessageBox.confirm(`确定删除「${item.name}」吗？`, '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await deleteFile(path)
    ElMessage.success('已删除')
    loadFiles()
    loadFavorites()
    // 如果当前打开的文档被删了，清除预览
    if (currentFilePath.value === path) {
      currentFilePath.value = ''
      currentFileContent.value = ''
    }
    // 从选中列表中移除
    const idx = selectedFiles.value.indexOf(path)
    if (idx >= 0) selectedFiles.value.splice(idx, 1)
  } catch { /* 用户取消或删除失败 */ }
}

// ── 刷新 ──
async function refreshFiles() {
  selectedFiles.value = []
  dirExpanded.value = {}
  fileTree.value = []
  await loadFiles()
  await loadFavorites()
  ElMessage.success('已刷新')
}

// ── 批量删除 ──
async function batchDeleteSelected() {
  if (selectedFiles.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedFiles.value.length} 个文件吗？`,
      '批量删除', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    for (const p of [...selectedFiles.value]) {
      try { await deleteFile(p) } catch { /* 跳过单个失败 */ }
    }
    ElMessage.success('已删除')
    selectedFiles.value = []
    loadFiles()
    loadFavorites()
    if (currentFilePath.value && !selectedFiles.value.includes(currentFilePath.value)) {
      currentFilePath.value = ''
      currentFileContent.value = ''
    }
  } catch { /* 取消 */ }
}

// ── 下载 ──
const dlStore = useDownloadStore()

async function batchDownload() {
  if (selectedFiles.value.length === 0) return
  dlStore.show('正在转换文档', selectedFiles.value)

  try {
    if (selectedFiles.value.length === 1) {
      // 单个文件 → 直接下载 docx
      const resp = await downloadFile(selectedFiles.value[0])
      const blob = await resp.blob()
      const filename = selectedFiles.value[0].split('/').pop().replace('.md', '.docx')
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } else {
      // 多个文件 → 打包 zip
      const resp = await downloadBatch(selectedFiles.value)
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `documents_${new Date().toISOString().slice(0,10)}.zip`
      a.click()
      URL.revokeObjectURL(url)
    }
    dlStore.done()
  } catch {
    dlStore.error('下载失败')
  }
}

// ── 搜索 ──
let searchTimer = null
function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    // 搜索功能：后续实现后端搜索文件夹
  }, 300)
}

function onTabChange() {
  // 标签切换时关闭手机端侧栏
  sidebarVisible.value = false
}

// ── 打印当前文档 ──
const printMarked = new Marked({ gfm: true, breaks: true })

function printDocument() {
  if (!currentFileContent.value) return

  const renderedHtml = printMarked.parse(currentFileContent.value)
  const fileName = currentFilePath.value.split('/').pop() || '文档'

  const printWin = window.open('', '_blank')
  if (!printWin) {
    ElMessage.error('打印窗口被浏览器拦截，请允许弹出窗口')
    return
  }

  printWin.document.write(`<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>打印 - ${fileName}</title>
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', 'PingFang SC', sans-serif;
    max-width: 800px;
    margin: 0 auto;
    padding: 40px;
    font-size: 1rem;
    line-height: 1.8;
    color: #333;
  }
  h1 { font-size: 1.6rem; border-bottom: 1px solid #d0d7de; padding-bottom: 8px; margin-bottom: 16px; }
  h2 { font-size: 1.3rem; border-bottom: 1px solid #d0d7de; padding-bottom: 6px; margin: 24px 0 12px; }
  h3 { font-size: 1.15rem; margin: 20px 0 8px; }
  h4 { font-size: 1.05rem; margin: 16px 0 6px; }
  p { margin-bottom: 12px; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
  th, td { border: 1px solid #d0d7de; padding: 8px 14px; text-align: left; }
  th { background: #f6f8fa; font-weight: 600; }
  pre { background: #f6f8fa; border: 1px solid #d0d7de; padding: 16px 20px; border-radius: 6px; overflow-x: auto; font-size: 0.9rem; }
  code { background: rgba(175,184,193,0.2); padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }
  pre code { background: none; padding: 0; }
  blockquote { border-left: 4px solid #d0d7de; padding: 8px 16px; margin: 12px 0; color: #656d76; background: #f9f9f9; }
  ul, ol { padding-left: 24px; margin-bottom: 12px; }
  li { margin-bottom: 4px; }
  img { max-width: 100%; }
  hr { border: none; border-top: 1px solid #d0d7de; margin: 24px 0; }
  @media print {
    body { padding: 0; }
    @page { margin: 2cm; }
  }
</style>
</head>
<body>${renderedHtml}</body>
</html>`)
  printWin.document.close()
  printWin.focus()

  // 等待内容渲染后弹出打印对话框
  setTimeout(() => printWin.print(), 400)
}
</script>

<style scoped>
.main-container { min-height: 100vh; display: flex; flex-direction: column; }

.header-bar {
  background: linear-gradient(135deg, var(--wood-400), var(--wood-500));
  padding: 12px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #fff;
}
.header-left { display: flex; align-items: center; gap: 12px; }
.header-left h1 { font-size: 1.2rem; font-weight: 500; }
.header-right { display: flex; align-items: center; gap: 12px; }
.user-name { font-size: 0.9rem; }

.app-layout { display: flex; flex: 1; height: calc(100vh - 56px); }

.sidebar {
  width: 30%; max-width: 340px; min-width: 260px;
  background: #fff;
  border-right: 1px solid var(--wood-200);
  display: flex; flex-direction: column;
  min-height: 0;
  /* 不设 overflow:hidden，让 sticky footer 能固定在底部 */
}

.sidebar-search { padding: 12px 16px; border-bottom: 1px solid var(--wood-100); }
.search-wrap { position: relative; }
.search-icon { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); z-index: 1; font-size: 16px; }
.search-wrap :deep(.el-input__wrapper) { padding-left: 36px !important; border-radius: 20px !important; }

.sidebar-section { border-bottom: 1px solid var(--wood-100); }
.tree-section { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-height: 0; }

.section-header {
  padding: 10px 16px;
  display: flex; align-items: center; justify-content: space-between;
  cursor: pointer; user-select: none;
}
.section-header:hover { background: var(--wood-50); }
.section-header .label { font-size: 0.9rem; font-weight: 600; color: var(--wood-600); display: flex; align-items: center; gap: 8px; }
.collapse-arrow { font-size: 12px; color: var(--wood-400); transition: transform 0.2s; }
.collapse-arrow.collapsed { transform: rotate(-90deg); }
.collapsible-body { overflow: hidden; transition: max-height 0.25s ease; max-height: 300px; }
.collapsible-body.hidden { max-height: 0 !important; }

.fav-list { padding: 2px 0 6px; }
.fav-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 20px; cursor: pointer;
  font-size: 1rem; color: var(--wood-700);
}
.fav-item:hover { background: var(--wood-50); }
.fav-item .icon { flex-shrink: 0; }
.fav-item .name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fav-item .pin { font-size: 12px; color: var(--amber-400); }
.fav-empty { padding: 12px 20px; font-size: 0.85rem; color: var(--wood-400); }

.tree-area-title {
  padding: 10px 16px 6px;
  font-size: 0.9rem; font-weight: 600;
  color: var(--wood-600);
  display: flex; align-items: center; justify-content: space-between;
}
.sort-controls { display: flex; align-items: center; gap: 4px; }
.sort-btn {
  background: none; border: 1px solid transparent;
  font-size: 14px; cursor: pointer;
  padding: 2px 6px; border-radius: 4px;
  line-height: 1; opacity: 0.5;
  transition: all 0.15s;
}
.sort-btn:hover { opacity: 0.8; background: var(--wood-100); }
.sort-btn.active { opacity: 1; border-color: var(--wood-300); background: var(--wood-50); }
.tree-area { flex: 1; overflow-y: auto; padding: 2px 0; }

.sidebar-footer {
  position: sticky;
  bottom: 0;
  background: #fff;
  z-index: 10;
  border-top: 1px solid var(--wood-100);
  padding: 8px 12px;
  display: flex;
  gap: 6px;
  justify-content: stretch;
  flex-shrink: 0;
  box-shadow: 0 -2px 8px rgba(0,0,0,0.06);
}
.sidebar-footer .el-button { flex: 1; }

.main-area { flex: 1; display: flex; flex-direction: column; min-width: 0; position: relative; }
.tabs-bar {
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid var(--wood-200);
}
.content-area { flex: 1; overflow-y: auto; padding: 20px 24px; }
.content-area:empty { display: flex; align-items: center; justify-content: center; color: var(--wood-400); }

.mobile-menu-btn { display: none; background: none; border: none; font-size: 24px; cursor: pointer; color: #fff; padding: 0; }
@media (max-width: 768px) {
  .mobile-menu-btn { display: block; }
  .sidebar { display: none; }
  .sidebar.mobile-open { display: flex; position: fixed; inset: 0; z-index: 100; width: 100%; max-width: 100%; }
  .content-area { padding: 16px; }
  .doc-float-bar { display: none; }
}

/* ════════════════════════════════════════════════════════════════
   文档页右侧浮动工具栏（竖排）
   ════════════════════════════════════════════════════════════════ */
.doc-float-bar {
  position: absolute;
  right: 8px;
  top: 60px;
  z-index: 20;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 8px 6px;
  background: rgba(255, 255, 255, 0.25);
  border: 1px solid transparent;
  border-radius: 10px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  opacity: 0.35;
  transition: opacity 0.25s ease, background 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
}
.doc-float-bar:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.95);
  border-color: var(--wood-200);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.doc-toolbar-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  color: var(--wood-600);
  transition: background 0.15s;
}
.doc-toolbar-btn:hover { background: var(--wood-100); }

.doc-toolbar-sep {
  width: 20px;
  height: 1px;
  background: var(--wood-200);
  margin: 4px 0;
  flex-shrink: 0;
}

/* 预留按钮位：虚线空槽，暂不可点 */
.doc-btn-placeholder {
  width: 36px;
  height: 36px;
  box-sizing: border-box;
  border: 1px dashed var(--wood-300);
  border-radius: 6px;
  opacity: 0.15;
  pointer-events: none;
  flex-shrink: 0;
}
</style>
