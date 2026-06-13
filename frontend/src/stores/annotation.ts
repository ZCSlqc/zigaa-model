import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getResourceTree, getAnnotation, saveAnnotation, deleteImage, deleteFolder, getImageInfo } from '../api/resource'
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
  channels?: number // 1=灰度, 3=彩色
  error?: string
  error_level?: number // 1-5 red (critical), 6-9 yellow (warning), 0 = OK
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

  const allImages = computed(() => {
    const images: TreeFile[] = []
    const walk = (nodes: TreeNode[]) => {
      for (const node of nodes) {
        if (isFolder(node)) {
          walk(node.children)
        } else {
          images.push(node)
        }
      }
    }
    walk(tree.value)
    return images
  })

  function isFolder(node: TreeNode): node is TreeFolder {
    return 'children' in node
  }

  function extractRelPath(fullPath: string): string {
    const idx = fullPath.indexOf('/original/')
    if (idx !== -1) return fullPath.slice(idx + 10)
    return fullPath.replace(/^\/uploads\/[^/]+\/[^/]+\/[^/]+\/(.*?)(\.[^.]+)$/, '$1')
  }

  async function loadModel(modelIdValue: string, type: 'good' | 'defect' | 'test' | 'template' = 'good') {
    modelId.value = modelIdValue
    resourceType.value = type
    loading.value = true
    try {
      const [treeRes, modelRes] = await Promise.all([
        getResourceTree(modelIdValue, type, ''),
        getModel(modelIdValue).catch(() => null),
      ])

      // Build error map from backend errors (key = image path with extension)
      const errorMap = new Map<string, { message: string; level: number }>()
      const modelData = modelRes?.data
      const pkg = modelData?.packages?.find((p: any) => p.resource_type === type)
      for (const err of pkg?.errors || []) {
        errorMap.set(err.path, { message: err.message, level: err.level ?? 1 })
      }

      const fullTree = treeRes.data.tree
      const origNode = (fullTree.children || []).find((c: any) => c.name === 'original')
      const rawChildren: any[] = origNode?.children || []

      const buildTree = (nodes: any[]): TreeNode[] => {
        return nodes.map(node => {
          if (node.children) {
            return {
              name: node.name,
              path: node.path || '',
              children: buildTree(node.children),
            } as TreeFolder
          }

          // Skip JSON files, only show images
          if (node.name.endsWith('.json')) return null!

          const relPath = extractRelPath(node.path)
          const backendError = errorMap.get(relPath)

          return {
            name: node.name,
            size: node.size,
            path: node.path,
            has_annotation: backendError === undefined,
            rel_path: relPath,
            original_rel_path: relPath,
            compress_path: node.compress_path,
            preview_path: node.preview_path,
            error: backendError?.message,
            error_level: backendError?.level ?? 0,
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

  // Cached channel count per image (persisted across image switches)
  const channelsCache = new Map<string, number>()

  async function selectImage(img: TreeFile) {
    // Save current channels for flicker-free transition
    const oldChannels = currentImage.value?.channels
    const cachedCh = channelsCache.get(img.original_rel_path)

    // Use cached channels if available, otherwise fall back to old value
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
    } catch {
      // image info optional, proceed without it
    }
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
      // Update tree to show no error
      updateTreeNodeError(currentImage.value, undefined, 0)
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || '保存失败'
      throw new Error(msg)
    }
  }

  function updateTreeNodeError(target: TreeFile, error: string | undefined, level: number) {
    const walk = (nodes: TreeNode[]) => {
      for (const n of nodes) {
        if (!isFolder(n) && n.path === target.path) {
          n.error = error
          n.error_level = level
          n.has_annotation = error === undefined
          return true
        }
        if (isFolder(n) && walk(n.children)) return true
      }
      return false
    }
    walk(tree.value)
  }

  // 从 tree 中移除文件节点，如果父文件夹空了也移除，返回被移除的文件夹路径
  function removeFileNode(target: TreeFile): string[] {
    const removedFolders: string[] = []
    const walk = (nodes: TreeNode[]): boolean => {
      for (let i = 0; i < nodes.length; i++) {
        if (isFolder(nodes[i])) {
          const folder = nodes[i] as TreeFolder
          if (walk(folder.children)) {
            if (folder.children.length === 0) {
              removedFolders.push(folder.path)
              nodes.splice(i, 1)
            }
            return true
          }
        } else if (nodes[i].path === target.path) {
          nodes.splice(i, 1)
          return true
        }
      }
      return false
    }
    walk(tree.value)
    return removedFolders
  }

  // 从 tree 中移除文件夹节点
  function removeFolderNode(folderPath: string): void {
    const walk = (nodes: TreeNode[]) => {
      for (let i = 0; i < nodes.length; i++) {
        if (isFolder(nodes[i])) {
          const folder = nodes[i] as TreeFolder
          if (folder.path === folderPath) {
            nodes.splice(i, 1)
            return true
          }
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
      const removedFolders = removeFileNode(img)
      // Return expandedFolders to caller so it can update
      emitRemovedFolders(removedFolders)
      currentImage.value = null
      annotationData.value = null
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || '删除失败'
      ElMessage.error(msg)
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
      const msg = e.response?.data?.detail || e.message || '删除失败'
      ElMessage.error(msg)
    }
  }

  // Track which folders were auto-removed so ImagePanel can remove from expandedFolders
  const onFolderRemovedCallbacks: ((paths: string[]) => void)[] = []
  function emitRemovedFolders(paths: string[]) {
    for (const cb of onFolderRemovedCallbacks) { cb(paths) }
  }
  function onFolderRemoved(cb: (paths: string[]) => void) {
    onFolderRemovedCallbacks.push(cb)
    return () => {
      const idx = onFolderRemovedCallbacks.indexOf(cb)
      if (idx >= 0) onFolderRemovedCallbacks.splice(idx, 1)
    }
  }

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

  function prevImage() {
    const images = allImages.value
    if (images.length === 0 || !currentImage.value) return
    const idx = images.findIndex(img => img.path === currentImage.value!.path)
    if (idx > 0) selectImage(images[idx - 1])
  }

  function nextImage() {
    const images = allImages.value
    if (images.length === 0 || !currentImage.value) return
    const idx = images.findIndex(img => img.path === currentImage.value!.path)
    if (idx < images.length - 1) selectImage(images[idx + 1])
  }

  return {
    modelId,
    resourceType,
    annotationData,
    tree,
    currentImage,
    loading,
    annotationLoading,
    allImages,
    loadModel,
    switchResourceType,
    selectImage,
    loadAnnotation,
    save,
    deleteCurrentImage,
    deleteFolder: deleteFolderFn,
    getCompressPathByImage,
    getPreviewPathByImage,
    channelLabel,
    prevImage,
    nextImage,
    onFolderRemoved,
  }
})
