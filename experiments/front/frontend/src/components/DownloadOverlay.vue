<template>
  <Teleport to="body">
    <div v-if="store.visible.value" class="dl-overlay" @click.self="store.hide">
      <div class="dl-card">
        <div class="dl-icon">📄<span class="arrow-icon">→</span>📝</div>
        <h3>{{ store.title.value }}</h3>
        <p class="dl-desc">Markdown 转 Word 格式</p>
        <div v-if="store.fileName.value" class="dl-file">
          {{ store.fileName.value }} <span>→</span> {{ store.fileName.value.replace('.md', '.docx') }}
        </div>
        <div v-else class="dl-file">{{ store.fileCount.value }} 个文件</div>

        <div class="progress-bar-wrap">
          <div class="progress-bar-fill" :style="{ width: store.progress.value + '%' }"></div>
        </div>

        <div class="dl-status" :class="{ error: store.status.value === 'error', done: store.status.value === 'done' }">
          <template v-if="store.status.value === 'progress'">
            <span>⏳</span><span>渲染中…</span>
          </template>
          <template v-else-if="store.status.value === 'done'">
            <span>✅</span><span>转换完成！正在下载…</span>
          </template>
          <template v-else-if="store.status.value === 'error'">
            <span>❌</span><span>{{ store.errorMsg.value }}</span>
          </template>
        </div>

        <div v-if="store.status.value !== 'progress'" class="dl-close">
          <el-button size="large" @click="store.hide()">✕ 关闭</el-button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { useDownloadStore } from '../api/downloadStore.js'
const store = useDownloadStore()
</script>

<style scoped>
.dl-overlay {
  position: fixed; inset: 0; z-index: 9999;
  background: rgba(74,55,40,0.30);
  display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(2px);
}
.dl-card {
  background: #fff;
  border-radius: 12px;
  padding: 36px 40px 32px;
  max-width: 420px; width: 90%;
  box-shadow: 0 8px 32px rgba(74,55,40,0.18);
  text-align: center;
}
.dl-icon { font-size: 42px; margin-bottom: 12px; }
.dl-icon .arrow-icon { color: var(--wood-400); margin: 0 4px; }
.dl-card h3 { margin-bottom: 4px; }
.dl-desc { font-size: 0.9rem; color: var(--wood-600); margin-bottom: 16px; }
.dl-file { font-size: 1rem; font-weight: 500; margin-bottom: 16px; }
.dl-file span { color: var(--wood-400); margin: 0 6px; }
.progress-bar-wrap {
  background: var(--wood-100);
  border-radius: 6px; height: 10px; overflow: hidden;
  margin-bottom: 12px;
}
.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--wood-400), var(--wood-500));
  border-radius: 6px;
  transition: width 0.3s ease;
}
.dl-status {
  font-size: 0.9rem; color: var(--wood-600);
  display: flex; align-items: center; justify-content: center; gap: 8px;
}
.dl-status.done { color: var(--green-500); font-weight: 500; }
.dl-status.error { color: var(--red-400); }
.dl-close { margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--wood-100); }
</style>
