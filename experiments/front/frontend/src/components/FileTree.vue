<template>
  <div class="file-tree">
    <template v-for="item in items" :key="item.path">
      <!-- 目录 -->
      <div v-if="item.type === 'dir'" class="tree-item" @click="$emit('toggle-dir', item)">
        <span style="width:28px;flex-shrink:0;"></span>
        <span class="arrow" :class="{ open: item.expanded }">▶</span>
        <span class="icon">📂</span>
        <span class="name">{{ item.name }}</span>
      </div>
      <!-- 子文件/目录（非递归，由父组件控制 children 展开） -->
      <template v-if="item.type === 'dir' && item.expanded && item.children">
        <div v-for="child in item.children" :key="child.path" class="tree-item tree-child" @click="onClick(child)">
          <span v-if="child.type === 'file'" class="ckb" :class="{ checked: child.checked }" @click.stop="$emit('toggle-check', child)"></span>
          <span v-else style="width:28px;flex-shrink:0;"></span>
          <span v-if="child.type === 'dir'" class="arrow" :class="{ open: child.expanded }">▶</span>
          <span class="icon">{{ child.type === 'dir' ? '📂' : '📄' }}</span>
          <span class="name">{{ child.name }}</span>
          <button v-if="child.type === 'file'" class="fav-star" :class="{ faved: child.is_favorite }" @click.stop="$emit('toggle-fav', child)">
            {{ child.is_favorite ? '★' : '☆' }}
          </button>
          <button v-if="child.type === 'file'" class="del-btn" title="删除" @click.stop="$emit('delete-file', child)">🗑</button>
        </div>
      </template>

      <!-- 文件（根级） -->
      <div v-if="item.type === 'file'" class="tree-item" @click="onClick(item)">
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

<script setup>
defineProps({
  items: { type: Array, default: () => [] },
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
.tree-child { padding-left: 48px; }
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
