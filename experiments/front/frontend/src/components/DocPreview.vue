<template>
  <div class="doc-preview" v-if="fileContent">
    <div class="md-preview" v-html="renderedHtml"></div>
  </div>
  <div v-else class="doc-empty">
    <p>📄 请在左侧文件树中选择一个 <strong>.md</strong> 文档查看</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'

const props = defineProps({
  filePath: { type: String, default: '' },
  fileContent: { type: String, default: '' },
})

const marked = new Marked({
  gfm: true,
  breaks: true,
  highlight(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value
    }
    return hljs.highlightAuto(code).value
  },
})

const renderedHtml = computed(() => {
  if (!props.fileContent) return ''
  return marked.parse(props.fileContent)
})
</script>

<style scoped>
.doc-preview {
  max-width: 800px;
  margin: 0 auto;
}
.md-preview {
  background: #fff;
  border-radius: 8px;
  padding: 32px 40px;
  box-shadow: 0 1px 4px rgba(74,55,40,0.06);
  font-size: 1rem;
  line-height: 1.8;
}
.md-preview :deep(h1) {
  font-size: 1.6rem; border-bottom: 1px solid var(--wood-200);
  padding-bottom: 8px; margin-bottom: 16px;
}
.md-preview :deep(h2) {
  font-size: 1.3rem; border-bottom: 1px solid var(--wood-100);
  padding-bottom: 6px; margin: 24px 0 12px;
}
.md-preview :deep(h3) { font-size: 1.15rem; margin: 20px 0 8px; }
.md-preview :deep(p) { margin-bottom: 12px; }
.md-preview :deep(code) {
  background: var(--wood-100);
  padding: 2px 8px; border-radius: 4px;
  font-size: 0.9rem;
}
.md-preview :deep(pre) {
  background: #2d2d2d; color: #E8DDD0;
  padding: 16px 20px; border-radius: 8px;
  overflow-x: auto; font-size: 0.9rem;
  margin-bottom: 16px;
}
.md-preview :deep(pre code) { background: none; padding: 0; color: inherit; }
.md-preview :deep(table) { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
.md-preview :deep(th), .md-preview :deep(td) {
  border: 1px solid var(--wood-200);
  padding: 8px 14px; text-align: left;
}
.md-preview :deep(th) { background: var(--wood-50); font-weight: 600; }
.md-preview :deep(ul), .md-preview :deep(ol) { padding-left: 24px; margin-bottom: 12px; }
.md-preview :deep(li) { margin-bottom: 4px; }
.md-preview :deep(blockquote) {
  border-left: 4px solid var(--wood-400);
  padding: 8px 16px; margin: 12px 0;
  background: var(--wood-50);
  color: var(--wood-700);
}
.md-preview :deep(strong) { font-weight: 600; }
.md-preview :deep(a) { color: #0366d6; text-decoration: none; }
.md-preview :deep(a:hover) { text-decoration: underline; }

.doc-empty {
  display: flex; align-items: center; justify-content: center;
  min-height: 300px;
  color: var(--wood-400);
  font-size: 1.1rem;
}
</style>
