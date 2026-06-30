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
        <span
          class="action-link action-expand"
          :class="{ disabled: store.allImages.length > 5000 }"
          @click="expandAll"
        >全部展开</span>
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
    <div v-else-if="store.displayTree.length === 0" class="empty-text">暂无图片</div>
    <div v-else class="image-list" ref="imageListRef">
      <TreeItem
        v-for="node in store.displayTree"
        :key="node.name"
        :node="node"
        :expanded-folders="expandedFolders"
        :selected-path="store.currentImage?.path"
        @toggle-folder="toggleFolder"
        @select-image="selectImage"
        @delete-folder="confirmDeleteFolder"
        @download-folder="startDownloadFolder"
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
          <span class="dot undone" /> 未标完
        </div>
        <div class="popup-option" :class="{ active: store.categoryFilter === 'pending' }" @click="setCategory('pending')">
          <span class="dot pending" /> 待确认
        </div>
      </div>
    </div>

    <!-- Folder download progress dialog -->
    <BatchDownloadDialog
      ref="batchDownloadRef"
      v-model:visible="folderDownloadVisible"
      :model-id="store.modelId || (route.params.modelId as string)"
      :resource-type="store.resourceType || (route.query.type as string)"
      :arrange-names="folderDownloadArrangement ? [folderDownloadArrangement] : []"
      :download-api="folderDownloadApi"
      :auto-start="true"
      @all-done="onFolderDownloadDone"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useAnnotationStore, type TreeNode, type TreeFile, type TreeFolder } from '../../stores/annotation'
import TreeItem from './TreeItem.vue'
import { downloadInit, downloadChunk, downloadCleanup } from '../../api/resource'
import { extractRelPath } from '../../utils/path'
import BatchDownloadDialog from '../Download/BatchDownloadDialog.vue'

const store = useAnnotationStore()
const route = useRoute()
const imageListRef = ref<HTMLElement | null>(null)

// ── Category filter sync (双向绑定) ──

const currentCategoryFilter = ref<string | undefined>('all')
watch(currentCategoryFilter, (val) => {
  store.categoryFilter = val === 'all' ? undefined : val
})
watch(
  () => store.categoryFilter,
  (val) => { currentCategoryFilter.value = val ?? 'all' }
)

// If currentImage was filtered out, clear canvas
watch([() => store.displayTree, () => store.categoryFilter], ([tree]) => {
  if (store.currentImage) {
    const match = findFile(tree as TreeNode[], store.currentImage.path)
    if (!match) {
      store.currentImage = null
      store.annotationData = null
    }
  }
})

// Recursively find a file in displayTree by path
function findFile(nodes: TreeNode[], path: string): TreeFile | null {
  for (const n of nodes) {
    if ('children' in n) {
      const m = findFile((n as TreeFolder).children, path)
      if (m) return m
    } else if ((n as TreeFile).path === path) return n as TreeFile
  }
  return null
}

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

async function setCategory(category: 'none' | 'undone' | 'pending' | undefined) {
  const cat = category === undefined ? 'none' : category
  await store.updateImageMsg(categoryMenuPath.value, cat)
  hideCategoryMenu()
}

onMounted(() => { document.addEventListener('click', hideCategoryMenu) })
onUnmounted(() => {
  document.removeEventListener('click', hideCategoryMenu)
})

// ── Tree interaction ──

const expandedFolders = ref(new Set<string>())

function scrollIntoSelected() {
  nextTick(() => {
    const el = imageListRef.value?.querySelector('.selected')
    if (el && 'scrollIntoView' in el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

function toggleFolder(path: string) {
  const ef = expandedFolders.value
  ef.has(path) ? ef.delete(path) : ef.add(path)
  // 保持 ref 指向，不创建新 Set，避免 3w 组件全量重渲染
  expandedFolders.value = new Set(ef)
  scrollIntoSelected()
}

function expandAll() {
  // 大于 5000 张不展开，灰色不可点
  const count = store.allImages.length
  if (count > 5000) {
    ElMessage.warning(`图片数量 ${count} 超过 5000，暂不支持全部展开`)
    return
  }
  const ef = new Set<string>()
  const stack = [...store.sourceTree]
  while (stack.length > 0) {
    const node = stack.pop()!
    if ('children' in node) {
      ef.add((node as TreeFolder).path)
      stack.push(...(node as TreeFolder).children)
    }
  }
  expandedFolders.value = ef
  scrollIntoSelected()
}

function collapseAll() { expandedFolders.value = new Set() }
function selectImage(img: TreeFile) { store.selectImage(img) }

async function confirmDeleteFolder(folderPath: string) {
  const folderName = folderPath.split('/').pop() || folderPath
  try {
    await ElMessageBox.confirm(`确定删除文件夹 "${folderName}" 及其下所有内容？`, '确认删除', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
    await store.deleteFolder(folderPath)
  } catch { /* cancelled */ }
}

// ── Folder download ──
const folderDownloadVisible = ref(false)
const folderDownloadArrangement = ref('')
const batchDownloadRef = ref<{ openDialog: () => void } | null>(null)

const folderDownloadApi = {
  init: (modelId: string, resourceType: string, arrangeName: string) => downloadInit(modelId, resourceType, { arrange_name: arrangeName }),
  chunk: (modelId: string, resourceType: string, sessionId: string, chunkIndex: number, signal?: AbortSignal) => downloadChunk(modelId, resourceType, sessionId, chunkIndex, signal),
  cleanup: (modelId: string, resourceType: string, sessionId: string) => downloadCleanup(modelId, resourceType, sessionId),
}

function onFolderDownloadDone() {
  folderDownloadArrangement.value = ''
}

async function startDownloadFolder(folderPath: string) {
  const folderName = folderPath.split('/').pop() || folderPath
  try {
    await ElMessageBox.confirm(`确定下载文件夹 "${folderName}"？将打包为 ZIP 文件。`, '确认下载', {
      confirmButtonText: '下载', cancelButtonText: '取消', type: 'info',
    })
  } catch { return }

  const arrangeName = extractRelPath(folderPath)
  const modelId = store.modelId || (route.params.modelId as string)
  if (!modelId) {
    ElMessage.error('请先选择模型')
    return
  }

  folderDownloadArrangement.value = arrangeName
  batchDownloadRef.value?.openDialog()
}

// No auto-expand — tree starts fully collapsed

// Remove deleted folders from expandedFolders
const folderCb = (paths: string[]) => {
  const ef = new Set(expandedFolders.value)
  for (const p of paths) ef.delete(p)
  expandedFolders.value = ef
}
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

  &.disabled {
    cursor: not-allowed;
    color: var(--text-placeholder);

    &:hover {
      opacity: 1;
    }
  }
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

/* Folder download dialog */
</style>
