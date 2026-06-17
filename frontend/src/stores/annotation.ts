import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getResourceTree, getAnnotation, saveAnnotation, deleteImage, deleteFolder, getImageInfo, updateImageMsg } from '../api/resource'
import { getModel } from '../api/model'
import { ElMessage } from 'element-plus'

export interface AnnotationData {
  va: Array<{
    label: number
    labelname: string
    pts: Array<{ x: number; y: number }>
  }>
  width: number
  height: number
  wl: number
  ww: number
}

export interface TreeFile {
  name: string
  size: number
  path: string
  has_annotation: boolean
  rel_path: string
  compress_path?: string
  preview_path?: string
  width?: number
  height?: number
  channels?: number // 1=灰度, 3=彩色
  error?: string
  error_level?: number // 1-5 red (critical), 6-9 yellow (warning), 0 = OK
  category: 'none' | 'undone' | 'pending' // 用户分类标记，始终有值
}

export interface TreeFolder {
  name: string
  path: string
  children: TreeNode[]
}

export type TreeNode = TreeFile | TreeFolder

export const useAnnotationStore = defineStore('annotation', () => {
  const modelId = ref('')
  const resourceType = ref<'good' | 'defect' | 'test' | 'template'>('good')
  const annotationData = ref<AnnotationData | null>(null)
  const initialSnapshot = ref<AnnotationData | null>(null)   // 初始快照（给撤销用）
  const savedSnapshot = ref<AnnotationData | null>(null)     // 最后保存态（给跳过优化用）
  const sourceTree = ref<TreeNode[]>([])                     // 唯一真实数据源
  const currentImage = ref<TreeFile | null>(null)
  const loading = ref(false)
  const annotationLoading = ref(false)
  const categoryFilter = ref<string | undefined>(undefined)

  // ── displayTree: 每次筛选时从 sourceTree 浅过滤生成的视图 ──

  const displayTree = computed(() => {
    const filter = categoryFilter.value
    if (!filter) return sourceTree.value

    // Recursively filter: keep folder only if it has matching children
    const filterNode = (nodes: TreeNode[]): TreeNode[] => {
      return nodes.flatMap(node => {
        if (isFolder(node)) {
          const filteredChildren = filterNode(node.children)
          return filteredChildren.length > 0 ? [{ ...node, children: filteredChildren }] : []
        }
        return (node as TreeFile).category === filter ? [node] : []
      })
    }

    return sourceTree.value.map(folder => ({
      ...folder,
      children: filterNode(folder.children),
    })).filter((f: TreeNode) => f.children.length > 0) as TreeFolder[]
  })

  // ── Auto-save ──

  let _globalTimer: ReturnType<typeof setTimeout> | null = null
  const _mode = ref<'draw' | 'select'>('draw')

  function clearAutoSaveTimers() {
    if (_globalTimer) { clearTimeout(_globalTimer); _globalTimer = null }
  }

  // Schedule a 10s auto-save timer — only fires in edit mode
  function scheduleAutoSave(delayMs: number) {
    clearAutoSaveTimers()
    _globalTimer = setTimeout(async () => {
      _globalTimer = null
      if (_mode.value !== 'select') return  // 仅编辑模式启动
      if (!annotationData.value || !currentImage.value) return
      await save(true, true)
    }, delayMs)
  }

  function setMode(m: 'draw' | 'select') {
    _mode.value = m
    if (m === 'select') {
      scheduleAutoSave(10000)  // 编辑模式启动 10s 定时
    } else {
      clearAutoSaveTimers()  // 非编辑模式清掉
    }
  }

  // ── Callbacks for external listeners ──

  // ── Tree helpers ──

  function isFolder(node: TreeNode): node is TreeFolder {
    return 'children' in node
  }

  function extractRelPath(fullPath: string): string {
    // 从 tree 节点路径中提取相对于 original/ 的相对路径
    // 格式如：upload/model/type/timestamp/folder/file.jpg → timestamp/folder/file.jpg
    const idx = fullPath.indexOf('/original/')
    if (idx !== -1) return fullPath.slice(idx + 10)
    // 通用提取：去掉前缀 upload/{model}/{type}/
    const parts = fullPath.split('/')
    // 找到 'original' 之后的部分
    const oi = parts.indexOf('original')
    if (oi >= 0) return parts.slice(oi + 1).join('/')
    // 兜底：去掉前缀 'upload/'
    if (parts[0] === 'upload') return parts.slice(1).join('/')
    return fullPath
  }

  // Flatten tree to all files
  const allImages = computed(() => {
    const images: TreeFile[] = []
    const walk = (nodes: TreeNode[]) => {
      for (const node of nodes) {
        if (isFolder(node)) walk(node.children)
        else images.push(node)
      }
    }
    walk(sourceTree.value)
    return images
  })

  // Filtered images by category
  function getFilteredImages(filter: string | undefined): TreeFile[] {
    if (!filter) return allImages.value
    return allImages.value.filter(img => img.category === filter)
  }

  // Find a TreeFile node in sourceTree by path (uses original object reference)
  function findNode(path: string): TreeFile | null {
    const walk = (nodes: TreeNode[]): TreeFile | null => {
      for (const n of nodes) {
        if ('children' in n) {
          const m = walk(n.children)
          if (m) return m
        } else if (n.path === path || n.rel_path === path) return n
      }
      return null
    }
    return walk(sourceTree.value)
  }

  // ── Async actions ──

  async function loadModel(modelIdValue: string, type: 'good' | 'defect' | 'test' | 'template' = 'good') {
    modelId.value = modelIdValue
    resourceType.value = type
    loading.value = true
    try {
      const [treeRes, modelRes] = await Promise.all([
        getResourceTree(modelIdValue, type, ''),
        getModel(modelIdValue).catch(() => null),
      ])

      const errorMap = new Map<string, { message: string; level: number }>()
      const msgsMap = new Map<string, { width?: number; height?: number; channels?: number; category?: string }>()
      const pkg = (modelRes?.data?.packages ?? []).find((p: any) => p.resource_type === type)

      for (const [path, err] of Object.entries(pkg?.errors || {})) {
        const e = err as any
        errorMap.set(path, { message: e.message, level: e.level ?? 1 })
      }
      for (const [path, msg] of Object.entries(pkg?.msgs || {})) {
        msgsMap.set(path, msg as any)
      }

      const rawChildren = ((treeRes.data.tree.children ?? []).find((c: any) => c.name === 'original')?.children) ?? []

      const buildTree = (nodes: any[]): TreeNode[] => {
        return nodes.map(node => {
          if (node.children) {
            return {
              name: node.name,
              path: node.path || '',
              children: buildTree(node.children),
            } as TreeFolder
          }

          if (node.name.endsWith('.json')) return null!

          const relPath = extractRelPath(node.path)
          const backendError = errorMap.get(relPath) || errorMap.get(`${relPath.replace(/\.(jpg|jpeg|png)$/, '.json')}`)
          const msgEntry = msgsMap.get(relPath) || msgsMap.get(`${relPath.replace(/\.(jpg|jpeg|png)$/, '.json')}`)

          const category: 'none' | 'undone' | 'pending' = msgEntry?.category && msgEntry.category !== '' ? msgEntry.category as 'none' | 'undone' | 'pending' : 'none'

          return {
            name: node.name, size: node.size, path: node.path,
            has_annotation: backendError === undefined,
            rel_path: relPath,
            compress_path: node.compress_path, preview_path: node.preview_path,
            width: msgEntry?.width ?? node.width,
            height: msgEntry?.height ?? node.height,
            channels: msgEntry?.channels,
            error: backendError?.message, error_level: backendError?.level ?? 0,
            category,
          } as TreeFile
        }).filter(Boolean)
      }

      sourceTree.value = buildTree(rawChildren)

      currentImage.value = null
      annotationData.value = null
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || '加载图片失败')
    } finally {
      loading.value = false
    }
  }

  function switchResourceType(type: 'good' | 'defect' | 'test' | 'template') {
    if (type !== resourceType.value && modelId.value) {
      currentImage.value = null
      annotationData.value = null
      loadModel(modelId.value, type)
    }
  }

  // Prevent concurrent image switches
  let _pendingSwitch = false

  async function selectImage(img: TreeFile) {
    // Same image already selected — no action needed
    if (currentImage.value?.path === img.path) return
    // Guard: if a switch is already in progress, wait for it to finish
    // so we don't race between loadImage/loadAnnotation of different images
    if (_pendingSwitch) {
      // Wait a tick and retry (the watch will have resolved)
      await new Promise(r => setTimeout(r, 50))
      if (_pendingSwitch) return selectImage(img)
    }
    _pendingSwitch = true
    try {
      // 1. Save old image BEFORE switching (currentImage.value rel_path is the save key)
      if (currentImage.value && annotationData.value) {
        try { await save(true, true) } catch { /* silent */ }
      }
      // 2. Clear annotation data
      annotationData.value = null
      // 3. Switch image — component's watch handles image + annotation loading
      currentImage.value = img
    } finally {
      _pendingSwitch = false
    }
  }

  async function loadAnnotation(img: TreeFile) {
    annotationLoading.value = true
    try {
      const res = await getAnnotation(modelId.value, resourceType.value, img.rel_path)
      annotationData.value = res.data
      const data = JSON.parse(JSON.stringify(res.data))
      initialSnapshot.value = data
      savedSnapshot.value = data   // 三态初始化
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || '加载标注失败')
    } finally {
      annotationLoading.value = false
    }
  }

  async function save(isSilent = false, isAuto = false) {
    if (!annotationData.value || !currentImage.value) return
    // Compare with savedSnapshot — skip if unchanged (no toast)
    if (savedSnapshot.value && JSON.stringify(annotationData.value) === JSON.stringify(savedSnapshot.value)) return
    try {
      await saveAnnotation(modelId.value, resourceType.value, currentImage.value.rel_path, annotationData.value)
      if (!isSilent) {
        if (isAuto) {
          ElMessage.success('自动保存')
        } else {
          ElMessage.success('标注已保存')
        }
      }
      currentImage.value.has_annotation = true
      currentImage.value.error = undefined
      currentImage.value.error_level = 0
      updateTreeNodeError(currentImage.value, undefined, 0)
      // Update savedSnapshot after every successful save
      savedSnapshot.value = JSON.parse(JSON.stringify(annotationData.value))
      clearAutoSaveTimers()
    } catch (e: any) {
      if (!isSilent) throw new Error(e.response?.data?.detail || e.message || '保存失败')
    }
  }

  function updateTreeNodeError(target: TreeFile, error: string | undefined, level: number) {
    const walk = (nodes: TreeNode[]): boolean => {
      for (const n of nodes) {
        if (!isFolder(n) && n.path === target.path) { n.error = error; n.error_level = level; n.has_annotation = error === undefined; return true }
        if (isFolder(n) && walk(n.children)) return true
      }
      return false
    }
    walk(sourceTree.value)
  }

  // ── Category update ──

  // Remove non-matching files from displayTree when category changes (filter mode only)
  // displayTree nodes are same refs as sourceTree — splice only changes the view array
  function updateDisplayTreeAfterCategoryChange(filePath: string, newCategory: 'none' | 'undone' | 'pending') {
    const filter = categoryFilter.value
    if (!filter) return  // "全部"模式 — displayTree = sourceTree，自动反映
    if (newCategory === filter) return  // 改成了当前筛选值，不需要移除

    // splice out from displayTree's children (folder is original ref, sourceTree already updated)
    for (const folder of displayTree.value) {
      const idx = folder.children.findIndex(
        (n: TreeNode) => !isFolder(n) && (n as TreeFile).rel_path === filePath,
      )
      if (idx >= 0) {
        folder.children.splice(idx, 1)
        if (folder.children.length === 0) {
          _emptyFolders.push(folder.path)
        }
        break
      }
    }
  }

  const _emptyFolders: string[] = []
  function getEmptyFolders(): string[] { const e = _emptyFolders.slice(); _emptyFolders.length = 0; return e }

  async function updateImageMsgFn(path: string, category: string) {
    try {
      await updateImageMsg(modelId.value, resourceType.value, path, { category })
      const cat = category as 'none' | 'undone' | 'pending'
      const found = findNode(path)
      if (found) {
        found.category = cat
        updateDisplayTreeAfterCategoryChange(path, cat)
        // Don't reassign currentImage — let the
        // caller (setCategory / ImagePanel) handle clearing or switching.
      }
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || '更新标记失败')
    }
  }

  // ── Navigation ──

  function prevImage(filter?: string | undefined) {
    const images = getFilteredImages(filter)
    if (images.length === 0 || !currentImage.value) return
    const idx = images.findIndex(img => img.path === currentImage.value!.path)
    selectImage(images[(idx - 1 + images.length) % images.length])
  }

  function nextImage(filter?: string | undefined) {
    const images = getFilteredImages(filter)
    if (images.length === 0 || !currentImage.value) return
    const idx = images.findIndex(img => img.path === currentImage.value!.path)
    selectImage(images[(idx + 1) % images.length])
  }

  // ── Delete ──

  // Remove a file from both sourceTree and displayTree, upward-clean empty folders
  function removeFileFromTrees(target: TreeFile): string[] {
    const removedFolders: string[] = []
    const walk = (nodes: TreeNode[]): boolean => {
      for (let i = 0; i < nodes.length; i++) {
        if (isFolder(nodes[i])) {
          const folder = nodes[i] as TreeFolder
          if (walk(folder.children)) {
            if (folder.children.length === 0) { removedFolders.push(folder.path); nodes.splice(i, 1) }
            return true
          }
        } else if (nodes[i].path === target.path) { nodes.splice(i, 1); return true }
      }
      return false
    }
    walk(sourceTree.value)
    // displayTree is a computed — re-filter will regenerate automatically
    return removedFolders
  }

  // Remove a folder from both trees
  function removeFolderFromTrees(folderPath: string): void {
    const walk = (nodes: TreeNode[]): boolean => {
      for (let i = 0; i < nodes.length; i++) {
        if (isFolder(nodes[i])) {
          const folder = nodes[i] as TreeFolder
          if (folder.path === folderPath) { nodes.splice(i, 1); return true }
          if (walk(folder.children)) return true
        }
      }
      return false
    }
    walk(sourceTree.value)
  }

  async function deleteCurrentImage() {
    if (!currentImage.value) return
    const img = currentImage.value
    try {
      await deleteImage(modelId.value, resourceType.value, img.rel_path)
      ElMessage.success('图片已删除')
      emitRemovedFolders(removeFileFromTrees(img))
      currentImage.value = null
      annotationData.value = null
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || e.message || '删除失败')
    }
  }

  async function deleteFolderFn(folderPath: string) {
    // 提取相对路径：/uploads/{model}/{type}/original/{rel} → {rel}
    const idx = folderPath.indexOf('/original/')
    const relPath = idx !== -1 ? folderPath.slice(idx + 10) : folderPath
    try {
      await deleteFolder(modelId.value, resourceType.value, relPath)
      ElMessage.success('文件夹已删除')
      removeFolderFromTrees(folderPath)
      if (currentImage.value && currentImage.value.path.startsWith(folderPath)) {
        currentImage.value = null
        annotationData.value = null
      }
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || e.message || '删除失败')
    }
  }

  // ── Folder removal notifications ──

  const _folderCallbacks: ((paths: string[]) => void)[] = []
  function onFolderRemoved(cb: (paths: string[]) => void) {
    _folderCallbacks.push(cb)
    return () => { const i = _folderCallbacks.indexOf(cb); if (i >= 0) _folderCallbacks.splice(i, 1) }
  }
  function emitRemovedFolders(paths: string[]) { for (const cb of _folderCallbacks) cb(paths) }

  // ── Utilities ──

  function getCompressPathByImage(img: TreeFile): string {
    return img.compress_path || `/uploads/${modelId.value}/${resourceType.value}/compress/${img.rel_path}`
  }

  function getPreviewPathByImage(img: TreeFile): string {
    return img.preview_path || `/uploads/${modelId.value}/${resourceType.value}/preview/${img.rel_path}`
  }

  function channelLabel(channels: number | undefined): string {
    if (channels === 1) return '灰度'
    return '彩色'
  }

  return {
    modelId, resourceType, annotationData, initialSnapshot, savedSnapshot, sourceTree, displayTree, currentImage,
    loading, annotationLoading, allImages,
    loadModel, switchResourceType, selectImage, loadAnnotation, save,
    deleteCurrentImage, deleteFolder: deleteFolderFn,
    getCompressPathByImage, getPreviewPathByImage, channelLabel,
    getFilteredImages, prevImage, nextImage,
    getEmptyFolders,
    onFolderRemoved, categoryFilter,
    updateImageMsg: updateImageMsgFn,
    clearAutoSaveTimers,
    scheduleAutoSave,
    getMode: () => _mode.value,
    setMode,
  }
})
