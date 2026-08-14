<template>
  <div class="file-tree">
    <template v-for="item in items" :key="item.path">
      <!-- 目录 -->
      <div v-if="item.type === 'dir'" class="tree-item" :style="{ paddingLeft: (20 + depth * 28) + 'px' }" @click="$emit('toggle-dir', item)">
        <span style="width:28px;flex-shrink:0;"></span>
        <span class="arrow" :class="{ open: item.expanded }">▶</span>
        <span class="icon">📂</span>
        <span class="name">{{ item.name }}</span>
      </div>
      <!-- 子项（递归渲染任意深度；点击事件逐层透传给父组件） -->
      <FileTree
        v-if="item.type === 'dir' && item.expanded && item.children"
        :items="item.children"
        :depth="depth + 1"
        @toggle-dir="$emit('toggle-dir', $event)"
        @toggle-check="$emit('toggle-check', $event)"
        @open-file="$emit('open-file', $event)"
        @toggle-fav="$emit('toggle-fav', $event)"
        @delete-file="$emit('delete-file', $event)"
      />
      <!-- 文件（叶子） -->
      <div v-if="item.type === 'file'" class="tree-item" :style="{ paddingLeft: (20 + depth * 28) + 'px' }" @click="onClick(item)">
        <span class="ckb" :class="{ checked: item.checked }" @click.stop="$emit('toggle-check', item)"></span>
        <span class="icon">📄</span>
        <span class="name">{{ item.name }}</span>
        <button class="fav-star" :class="{ faved: item.is_favorite }" @click.stop="$emit('toggle-fav', item)">
          {{ item.is_favorite ? '★' : '☆' }}
        </button>
        <button class="del-btn" title="删除" @click.stop="$emit('delete-file', item)">🗑</button>
      </div>
    </template>

    <div v-if="items.length === 0" class="tree-empty">空目录</div>
  </div>
</template>

<script>
// 递归组件必须声明 name
export default { name: 'FileTree' }
</script>

<script setup>
defineProps({
  items: { type: Array, default: () => [] },
  depth: { type: Number, default: 0 },
  selectedFiles: { type: Array, default: () => [] },
})
const emit = defineEmits(['toggle-check', 'open-file', 'toggle-fav', 'toggle-dir', 'delete-file'])

function onClick(item) {
  if (item.type === 'dir') {
    emit('toggle-dir', item)
  } else {
    emit('open-file', item.path || item.name)
  }
}
</script>

<style scoped>
.tree-item {
  display: flex; align-items: center; gap: 6px;
  padding: 7px 20px;
  cursor: pointer; font-size: 1rem;
  color: var(--wood-700);
  transition: background 0.1s;
  user-select: none;
}
.tree-item:hover { background: var(--wood-50); }
.tree-item .icon { flex-shrink: 0; font-size: 1rem; }
.tree-item .name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tree-item .arrow { font-size: 11px; color: var(--wood-400); transition: transform 0.2s; width: 14px; text-align: center; flex-shrink: 0; }
.tree-item .arrow.open { transform: rotate(90deg); }

.ckb {
  width: 22px; height: 22px; flex-shrink: 0;
  border: 2px solid var(--wood-300);
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  transition: all 0.12s;
  font-size: 14px; color: #fff;
}
.ckb:hover { border-color: var(--wood-400); }
.ckb.checked { background: var(--wood-400); border-color: var(--wood-400); }
.ckb.checked::after { content: "✓"; }

.fav-star {
  background: none; border: none;
  font-size: 18px; cursor: pointer;
  color: var(--wood-300); padding: 2px 4px; flex-shrink: 0;
  transition: color 0.15s;
}
.fav-star:hover { color: var(--amber-400); }
.fav-star.faved { color: var(--amber-400); }

.del-btn {
  background: none; border: none;
  font-size: 16px; cursor: pointer;
  padding: 2px 4px; flex-shrink: 0;
  opacity: 0; transition: opacity 0.15s;
  line-height: 1;
}
.tree-item:hover .del-btn { opacity: 0.6; }
.del-btn:hover { opacity: 1 !important; }

.tree-empty { padding: 16px 20px; font-size: 0.85rem; color: var(--wood-400); text-align: center; }
</style>
