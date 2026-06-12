<template>
  <div class="image-panel">
    <div class="panel-header">
      <h4 class="panel-title">{{ resourceLabel }}图片</h4>
      <span class="image-count">
        <span v-if="hasAnnotationCount > 0" class="count-ok">{{ hasAnnotationCount }} 张</span>
        <span v-if="hasErrorCount > 0" class="count-err">{{ hasErrorCount }} 张</span>
      </span>
    </div>
    <div v-if="currentImageRelPath" class="current-path" :title="currentImageRelPath">
      文件路径：{{ currentImageRelPath }}
    </div>
    <div class="panel-actions">
      <span class="action-link" @click="expandAll">全部展开</span>
      <span class="action-sep">/</span>
      <span class="action-link" @click="collapseAll">全部折叠</span>
    </div>
    <div v-if="store.loading" class="loading-text">加载中...</div>
    <div v-else-if="treeFlat.length === 0" class="empty-text">暂无图片</div>
    <div v-else class="image-list" ref="imageListRef">
      <TreeItem
        v-for="node in treeFlat"
        :key="node.name"
        :node="node"
        :expanded-folders="expandedFolders"
        :selected-path="store.currentImage?.path"
        @toggle-folder="toggleFolder"
        @select-image="selectImage"
        @delete-folder="confirmDeleteFolder"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted, nextTick } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useAnnotationStore, type TreeNode } from '../../stores/annotation'
import TreeItem from './TreeItem.vue'

const store = useAnnotationStore()
const imageListRef = ref<HTMLElement | null>(null)

function scrollIntoSelected() {
  nextTick(() => {
    const el = imageListRef.value?.querySelector('.selected')
    if (el && 'scrollIntoView' in el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  })
}

const resourceLabel = computed(() => {
  const labels: Record<string, string> = { good: '良品', defect: '缺陷', test: '测试', template: '模板' }
  return labels[store.resourceType] || store.resourceType
})

const treeFlat = computed(() => store.tree)

const currentImageRelPath = computed(() => {
  const img = store.currentImage
  if (!img) return ''
  return img.rel_path
})
const hasAnnotationCount = computed(() => store.allImages.filter(img => img.has_annotation).length)
const hasErrorCount = computed(() => store.allImages.filter(img => !img.has_annotation).length)
const expandedFolders = ref(new Set<string>())

function toggleFolder(path: string) {
  if (expandedFolders.value.has(path)) {
    expandedFolders.value.delete(path)
  } else {
    expandedFolders.value.add(path)
  }
  scrollIntoSelected()
}

function expandAll() {
  const walk = (nodes: TreeNode[]) => {
    for (const node of nodes) {
      if ('children' in node) {
        expandedFolders.value.add(node.path)
        walk(node.children)
      }
    }
  }
  walk(store.tree)
  scrollIntoSelected()
}

function collapseAll() {
  expandedFolders.value.clear()
}

function selectImage(img: any) {
  store.selectImage(img)
}

async function confirmDeleteFolder(folderPath: string) {
  const folderName = folderPath.split('/').pop() || folderPath
  try {
    await ElMessageBox.confirm(`确定删除文件夹 "${folderName}" 及其下所有内容？`, '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await store.deleteFolder(folderPath)
  } catch {
    // cancelled
  }
}

// 只在首次加载时全部展开，tree 变动（删除后）不重置
let treeInitialized = false
watch(() => store.tree, (newTree) => {
  if (newTree.length > 0 && !treeInitialized) {
    treeInitialized = true
    const expandAll = (nodes: TreeNode[]) => {
      for (const node of nodes) {
        if ('children' in node) {
          expandedFolders.value.add(node.path)
          expandAll(node.children)
        }
      }
    }
    expandAll(newTree)
  }
}, { immediate: true })

// 删除后从 expandedFolders 移除已被删的路径
const folderCb = (removedPaths: string[]) => {
  for (const p of removedPaths) {
    expandedFolders.value.delete(p)
  }
}
const offFolderRemoved = store.onFolderRemoved(folderCb)

// 高亮元素滚动到可视区域（切换图片时触发）
watch(
  () => store.currentImage?.path,
  (newPath, oldPath) => {
    if (!newPath || newPath === oldPath) return
    scrollIntoSelected()
  },
)

onUnmounted(() => {
  offFolderRemoved()
})
</script>

<style scoped lang="scss">
.image-panel {
  width: 280px;
  flex-shrink: 0;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  max-height: calc(100vh - 140px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--border-light);
}

.panel-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.image-count {
  font-size: 12px;
  display: flex;
  gap: 8px;
  align-items: center;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-md);
  font-size: 12px;
}

.action-link {
  cursor: pointer;
  color: var(--color-primary);
}

.action-link:hover {
  opacity: 0.75;
}

.current-path {
  font-size: 11px;
  color: var(--color-primary);
  padding: 0 var(--spacing-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-height: 1.4;
  white-space: normal;
}

.action-sep {
  color: var(--border-color);
  user-select: none;
}

.count-ok {
  color: #67c23a;
}

.count-err {
  color: #f56c6c;
}

.image-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-xs);
}

.loading-text,
.empty-text {
  color: var(--text-secondary);
  font-size: 13px;
  text-align: center;
  padding: var(--spacing-lg) 0;
}
</style>
