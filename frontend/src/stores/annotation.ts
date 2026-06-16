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
  original_rel_path: string
  compress_path?: string
  preview_path?: string
  width?: number
  height?: number
  channels?: number // 1=灰度, 3=彩色
  error?: string
  error_level?: number // 1-5 red (critical), 6-9 yellow (warning), 0 = OK
  category?: 'none' | 'undone' | 'pending' // 用户分类标记
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
  const tree = ref<TreeNode[]>([])
  const currentImage = ref<TreeFile | null>(null)
  const loading = ref(false)
  const annotationLoading = ref(false)
  const categoryFilter = ref<string | undefined>(undefined)

  // ── Callbacks for external listeners ──

  const _categoryCallbacks: ((path: string) => void)[] = []
  function onCategoryUpdated(cb: (path: string) => void) {
    _categoryCallbacks.push(cb)
    return () => { const i = _categoryCallbacks.indexOf(cb); if (i >= 0) _categoryCallbacks.splice(i, 1) }
  }

  // ── Tree helpers ──

  function isFolder(node: TreeNode): node is TreeFolder {
    return 'children' in node
  }

  function extractRelPath(fullPath: string): string {
    const idx = fullPath.indexOf('/original/')
    if (idx !== -1) return fullPath.slice(idx + 10)
    return fullPath.replace(/^\/uploads\/[^/]+\/[^/]+\/[^/]+\/(.*?)(\.[^.]+)$/, '$1')
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
    walk(tree.value)
    return images
  })

  // Filtered images by category
  function getFilteredImages(filter: string | undefined): TreeFile[] {
    if (!filter) return allImages.value
    return allImages.value.filter(img => img.category === filter)
  }

  // Find a TreeFile node in tree by path
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
    return walk(tree.value)
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

          const category = msgEntry?.category && msgEntry.category !== '' ? msgEntry.category as 'none' | 'undone' | 'pending' : undefined

          return {
            name: node.name, size: node.size, path: node.path,
            has_annotation: backendError === undefined,
            rel_path: relPath, original_rel_path: relPath,
            compress_path: node.compress_path, preview_path: node.preview_path,
            width: msgEntry?.width ?? node.width,
            height: msgEntry?.height ?? node.height,
            channels: msgEntry?.channels,
            error: backendError?.message, error_level: backendError?.level ?? 0,
            category,
          } as TreeFile
        }).filter(Boolean)
      }

      tree.value = buildTree(rawChildren)

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

  // Cached channel count per image
  const channelsCache = new Map<string, number>()

  async function selectImage(img: TreeFile) {
    const oldChannels = currentImage.value?.channels
    const cachedCh = channelsCache.get(img.original_rel_path)
    const channels = cachedCh ?? oldChannels
    currentImage.value = { ...img, channels }
    const imageInfo = getImageInfo(modelId.value, resourceType.value, img.original_rel_path).catch(() => null)
    await loadAnnotation(img)
    try {
      const res = await imageInfo
      if (res?.data) {
        channelsCache.set(img.original_rel_path, res.data.channels)
        currentImage.value!.channels = res.data.channels
      }
    } catch { /* optional */ }
  }

  async function loadAnnotation(img: TreeFile) {
    annotationLoading.value = true
    try {
      const res = await getAnnotation(modelId.value, resourceType.value, img.original_rel_path)
      annotationData.value = res.data
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || '加载标注失败')
    } finally {
      annotationLoading.value = false
    }
  }

  async function save() {
    if (!annotationData.value || !currentImage.value) return
    try {
      await saveAnnotation(modelId.value, resourceType.value, currentImage.value.original_rel_path, annotationData.value)
      ElMessage.success('标注已保存')
      currentImage.value.has_annotation = true
      currentImage.value.error = undefined
      currentImage.value.error_level = 0
      updateTreeNodeError(currentImage.value, undefined, 0)
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || '保存失败'
      throw new Error(msg)
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
    walk(tree.value)
  }

  // ── Category update ──

  async function updateImageMsgFn(path: string, category: string) {
    try {
      await updateImageMsg(modelId.value, resourceType.value, path, { category })
      const cat = category === 'none' ? undefined : (category as TreeFile['category'])
      const found = findNode(path)
      if (found) {
        found.category = cat
        // Don't reassign currentImage if it points to this node — let the
        // caller (setCategory / ImagePanel) handle clearing or switching.
      }
      _categoryCallbacks.forEach(cb => cb(path))
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

  function removeFileNode(target: TreeFile): string[] {
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
    walk(tree.value)
    return removedFolders
  }

  function removeFolderNode(folderPath: string): void {
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
    walk(tree.value)
  }

  async function deleteCurrentImage() {
    if (!currentImage.value) return
    const img = currentImage.value
    try {
      await deleteImage(modelId.value, resourceType.value, img.original_rel_path)
      ElMessage.success('图片已删除')
      emitRemovedFolders(removeFileNode(img))
      currentImage.value = null
      annotationData.value = null
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || e.message || '删除失败')
    }
  }

  async function deleteFolderFn(folderPath: string) {
    try {
      const relPath = extractRelPath(folderPath)
      await deleteFolder(modelId.value, resourceType.value, relPath)
      ElMessage.success('文件夹已删除')
      removeFolderNode(folderPath)
      if (currentImage.value && currentImage.value.original_rel_path.startsWith(relPath)) {
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
    modelId, resourceType, annotationData, tree, currentImage,
    loading, annotationLoading, allImages,
    loadModel, switchResourceType, selectImage, loadAnnotation, save,
    deleteCurrentImage, deleteFolder: deleteFolderFn,
    getCompressPathByImage, getPreviewPathByImage, channelLabel,
    getFilteredImages, prevImage, nextImage,
    onFolderRemoved, onCategoryUpdated, categoryFilter,
    updateImageMsg: updateImageMsgFn,
  }
})
