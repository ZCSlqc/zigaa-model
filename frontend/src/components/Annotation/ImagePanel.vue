<template>
  <div class="image-panel">
    <div class="panel-header">
      <h4 class="panel-title">{{ resourceLabel }}图片</h4>
      <span class="image-count">
        <span v-if="hasAnnotationCount > 0" class="count-ok">{{ hasAnnotationCount }} 张</span>
        <span v-if="hasErrorCount > 0" class="count-err">{{ hasErrorCount }} 张</span>
      </span>
    </div>
    <div class="panel-actions">
      <div class="panel-actions-left">
        <span class="action-link" @click="expandAll">全部展开</span>
        <span class="action-sep">/</span>
        <span class="action-link" @click="collapseAll">全部折叠</span>
      </div>
      <el-select v-model="currentCategoryFilter" size="small" style="width: 110px; font-size: 12px">
        <el-option label="全部" value="all" />
        <el-option label="未标完" value="undone" />
        <el-option label="待确认" value="pending" />
      </el-select>
    </div>
    <div v-if="store.loading" class="loading-text">加载中...</div>
    <div v-else-if="filteredTree.length === 0" class="empty-text">暂无图片</div>
    <div v-else class="image-list" ref="imageListRef">
      <TreeItem
        v-for="node in filteredTree"
        :key="node.name"
        :node="node"
        :expanded-folders="expandedFolders"
        :selected-path="store.currentImage?.path"
        @toggle-folder="toggleFolder"
        @select-image="selectImage"
        @delete-folder="confirmDeleteFolder"
        @show-category-menu="showCategoryMenu"
      />
    </div>

    <!-- Category change popup menu -->
    <div
      v-if="categoryMenuVisible"
      class="category-popup"
      :style="{ top: categoryMenuY + 'px', left: categoryMenuX + 'px' }"
    >
      <div class="popup-title">标记状态</div>
      <div class="popup-options">
        <div class="popup-option" :class="{ active: store.categoryFilter === undefined }" @click="setCategory(undefined)">
          <span class="dot" /> 无标记
        </div>
        <div class="popup-option" :class="{ active: store.categoryFilter === 'undone' }" @click="setCategory('undone')">
          <span class="dot undone" /> 未标注
        </div>
        <div class="popup-option" :class="{ active: store.categoryFilter === 'pending' }" @click="setCategory('pending')">
          <span class="dot pending" /> 待确认
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted, onMounted, nextTick } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useAnnotationStore, type TreeNode, type TreeFile } from '../../stores/annotation'
import TreeItem from './TreeItem.vue'

const store = useAnnotationStore()
const imageListRef = ref<HTMLElement | null>(null)

// ── Category filter sync ──

const currentCategoryFilter = ref<string | undefined>('all')
watch(currentCategoryFilter, (val) => {
  store.categoryFilter = val === 'all' ? undefined : val
})
watch(
  () => store.categoryFilter,
  (val) => { currentCategoryFilter.value = val ?? 'all' }
)

// ── Filtered tree (ref + watch for performance) ──

const filteredTree = ref<TreeNode[]>([])

watch(
  () => [store.tree, store.categoryFilter] as const,
  ([newTree, newFilter]) => {
    if (!newFilter) { filteredTree.value = newTree; return }
    const cat = newFilter
    const filterNode = (nodes: TreeNode[]): TreeNode[] => {
      const result: TreeNode[] = []
      for (const n of nodes) {
        if ('children' in n) {
          const filtered = filterNode(n.children)
          if (filtered.length > 0) result.push({ ...n, children: filtered })
        } else if ((n as TreeFile).category === cat) {
          result.push(n)
        }
      }
      return result
    }
    const filtered = filterNode(newTree)
    filteredTree.value = filtered

    // If currentImage was filtered out, clear canvas
    if (store.currentImage) {
      const match = findFile(filtered, store.currentImage.path)
      if (match) {
        // Keep currentImage but update to match node (preserve channels)
        store.currentImage = { ...match, channels: store.currentImage.channels }
      } else {
        store.currentImage = null
        store.annotationData = null
      }
    }
  },
  { deep: false }
)

// Recursively find a file in filtered tree
function findFile(nodes: TreeNode[], path: string): TreeFile | null {
  for (const n of nodes) {
    if ('children' in n) {
      const m = findFile(n.children, path)
      if (m) return m
    } else if ((n as TreeFile).path === path) return n as TreeFile
  }
  return null
}

// Remove a matched image from filtered tree when its category changes
const offCatUpdated = store.onCategoryUpdated((path) => {
  if (!store.categoryFilter) return
  const remove = (nodes: TreeNode[]): boolean => {
    for (let i = nodes.length - 1; i >= 0; i--) {
      const n = nodes[i]
      if ('children' in n) {
        if (remove(n.children)) {
          if (n.children.length === 0) nodes.splice(i, 1)
          return true
        }
      } else if ((n as TreeFile).original_rel_path === path) {
        nodes.splice(i, 1)
        return true
      }
    }
    return false
  }
  remove(filteredTree.value)
})

// ── UI state ──

const resourceLabel = computed(() => {
  const labels: Record<string, string> = { good: '良品', defect: '缺陷', test: '测试', template: '模板' }
  return labels[store.resourceType] || store.resourceType
})

const visibleImages = computed(() => {
  if (!store.categoryFilter) return store.allImages
  return store.allImages.filter(img => img.category === store.categoryFilter)
})
const hasAnnotationCount = computed(() => visibleImages.value.filter(img => img.has_annotation).length)
const hasErrorCount = computed(() => visibleImages.value.filter(img => !img.has_annotation).length)

// Category popup menu
const categoryMenuVisible = ref(false)
const categoryMenuX = ref(0)
const categoryMenuY = ref(0)
const categoryMenuPath = ref('')

function showCategoryMenu(data: { node: MouseEvent; path: string }) {
  categoryMenuX.value = data.node.clientX
  categoryMenuY.value = data.node.clientY
  categoryMenuPath.value = data.path
  categoryMenuVisible.value = true
}
function hideCategoryMenu() { categoryMenuVisible.value = false }

async function setCategory(category: string | undefined) {
  const cat = category === undefined ? 'none' : category
  await store.updateImageMsg(categoryMenuPath.value, cat)
  hideCategoryMenu()
}

onMounted(() => { document.addEventListener('click', hideCategoryMenu) })
onUnmounted(() => { document.removeEventListener('click', hideCategoryMenu) })

// ── Tree interaction ──

const expandedFolders = ref(new Set<string>())

function scrollIntoSelected() {
  nextTick(() => {
    const el = imageListRef.value?.querySelector('.selected')
    if (el && 'scrollIntoView' in el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

function toggleFolder(path: string) {
  expandedFolders.value.has(path) ? expandedFolders.value.delete(path) : expandedFolders.value.add(path)
  scrollIntoSelected()
}

function expandAll() {
  const walk = (nodes: TreeNode[]) => {
    for (const n of nodes) if ('children' in n) { expandedFolders.value.add(n.path); walk(n.children) }
  }
  walk(store.tree)
  scrollIntoSelected()
}

function collapseAll() { expandedFolders.value.clear() }
function selectImage(img: any) { store.selectImage(img) }

async function confirmDeleteFolder(folderPath: string) {
  const folderName = folderPath.split('/').pop() || folderPath
  try {
    await ElMessageBox.confirm(`确定删除文件夹 "${folderName}" 及其下所有内容？`, '确认删除', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
    await store.deleteFolder(folderPath)
  } catch { /* cancelled */ }
}

// Auto-expand on first load
let treeInitialized = false
watch(() => store.tree, (newTree) => {
  if (newTree.length > 0 && !treeInitialized) {
    treeInitialized = true
    const expandAll = (nodes: TreeNode[]) => {
      for (const n of nodes) if ('children' in n) { expandedFolders.value.add(n.path); expandAll(n.children) }
    }
    expandAll(newTree)
  }
}, { immediate: true })

// Remove deleted folders from expandedFolders
const folderCb = (paths: string[]) => { for (const p of paths) expandedFolders.value.delete(p) }
const offFolderRemoved = store.onFolderRemoved(folderCb)

// Scroll selected into view on image switch
watch(() => store.currentImage?.path, (newPath, oldPath) => {
  if (newPath && newPath !== oldPath) scrollIntoSelected()
})

onUnmounted(() => { offFolderRemoved() })
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

.panel-title { margin: 0; font-size: 14px; font-weight: 600 }

.image-count {
  font-size: 12px;
  display: flex;
  gap: 8px;
  align-items: center;
}

.panel-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-xs) var(--spacing-md);
  font-size: 12px;
}

.panel-actions-left { display: flex; align-items: center; gap: var(--spacing-xs) }

.action-link {
  cursor: pointer;
  color: var(--color-primary);
  &:hover { opacity: 0.75 }
}

.action-sep { color: var(--border-color); user-select: none }

.count-ok { color: #67c23a }
.count-err { color: #f56c6c }

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

/* Category popup */
.category-popup {
  position: fixed;
  z-index: 2000;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-md);
  min-width: 120px;
  padding: 4px 0;
}

.popup-title {
  font-size: 11px;
  color: var(--text-secondary);
  padding: 4px 12px;
  font-weight: 500;
}

.popup-options { display: flex; flex-direction: column }

.popup-option {
  padding: 6px 12px;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: background 0.15s;
  &:hover { background: var(--bg-hover) }
  &.active { color: var(--color-primary); font-weight: 500 }
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #dcdcdc;
  flex-shrink: 0;
  &.undone { background: #e6a23c }
  &.pending { background: #409eff }
}
</style>
