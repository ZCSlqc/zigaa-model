<template>
  <AppLayout>
    <div class="preview-page">
      <PreviewToolbar
        @back="router.push(`/model/${modelId}`)"
        :resource-type="store.resourceType as 'test' | 'template'"
        :has-image="!!store.currentImage"
        :image-name="store.currentImage?.name"
        :loading-delete-image="loadingDeleteImage"
        :loading-download-image="loadingDownloadImage"
        @switch-resource="onSwitchResource"
        @delete-image="deleteImage"
        @download-image="downloadImage"
      />

      <div class="preview-body">
        <ImagePanel
          @delete-folder="store.deleteFolder"
        />

        <div class="canvas-container" ref="containerRef" @contextmenu.prevent>
          <div v-if="store.currentImage" class="canvas-title">
            图片路径：{{ store.currentImage.rel_path }}&ensp;|&ensp;通道数：{{ store.currentImage.channels || 3 }}（{{ store.channelLabel(store.currentImage.channels) }}）&ensp;|&ensp;分辨率：{{ imgW }}×{{ imgH }}
          </div>
          <v-stage
            v-if="imageReady"
            ref="stageRef"
            :config="{ width: stageWidth, height: stageHeight, scaleX: scale, scaleY: scale, x: panX, y: panY, cursor: cursor }"
            @mousedown="onMouseDown"
            @mousemove="onMouseMove"
            @mouseup="onMouseUp"
          >
            <v-layer :config="{ imageSmoothingEnabled: false }">
              <v-image
                :config="{ image: bgImage, x: 0, y: 0, width: imgW, height: imgH }"
              />

              <!-- Annotation polygons -->
              <template v-for="(entry, idx) in currentEntries" :key="idx">
                <!-- Fill -->
                <v-path
                  :config="{
                    data: toPathData(entry.pts),
                    fill: 'rgba(64, 158, 255, 0.1)',
                    stroke: '#409eff',
                    strokeWidth: 0,
                    listening: false,
                  }"
                />

                <!-- Edges -->
                <v-line
                  :config="{
                    points: toPathLinePoints(entry.pts),
                    stroke: '#409eff',
                    strokeWidth: 0.6 / scale,
                    tension: 0,
                    listening: false,
                  }"
                />

                <!-- Label badge -->
                <v-label
                  v-if="showLabels"
                  :config="{
                    x: entry.pts[0].x - labelWidthPx(entry) / 2,
                    y: entry.pts[0].y - 24 / scale,
                    rotation: 0,
                    listening: false,
                  }"
                >
                  <v-tag
                    :config="{
                      fill: 'rgba(230, 162, 60, 0.75)',
                      cornerRadius: 3 / scale,
                      lineHeight: 14 / scale,
                    }"
                  />
                  <v-text
                    :config="{
                      text: getLabelWithArea(entry),
                      fontSize: 12 / scale,
                      fontFamily: 'sans-serif',
                      fill: '#fff',
                      padding: 4 / scale,
                    }"
                  />
                </v-label>
              </template>
            </v-layer>
          </v-stage>

          <div v-if="!store.currentImage" class="canvas-empty">
            请从左侧选择一张图片
          </div>
          <div v-else-if="!imageReady && store.annotationLoading" class="canvas-empty">
            加载图片中...
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppLayout from '../components/Layout/AppLayout.vue'
import PreviewToolbar from '../components/Annotation/PreviewToolbar.vue'
import ImagePanel from '../components/Annotation/ImagePanel.vue'
import { useAnnotationStore } from '../stores/annotation'
import client from '../api/client'
import { base64ToBlob } from '../utils/blob'

const route = useRoute()
const router = useRouter()
const store = useAnnotationStore()
const modelId = computed(() => route.params.modelId as string)

// Canvas
const containerRef = ref<HTMLElement>()
const stageRef = ref<any>(null)
const stageWidth = ref(800)
const stageHeight = ref(600)
const scale = ref(1)
const panX = ref(0)
const panY = ref(0)

// Image
const bgImage = ref<HTMLImageElement | null>(null)
const imgW = ref(0)
const imgH = ref(0)
const imageReady = ref(false)

// Pan
const isPanning = ref(false)
const lastPos = ref<{ x: number; y: number }>({ x: 0, y: 0 })

// Loading
let _loadGen = 0
let loadingTimer: ReturnType<typeof setTimeout> | null = null
const loadingDeleteImage = ref(false)
const loadingDownloadImage = ref(false)

function startLoading() {
  if (loadingTimer) { clearTimeout(loadingTimer); loadingTimer = null }
  loadingTimer = setTimeout(() => { loadingDeleteImage.value = true }, 500)
}
function stopLoading() {
  if (loadingTimer) { clearTimeout(loadingTimer); loadingTimer = null }
  loadingDeleteImage.value = false
}

const cursor = computed(() => isPanning.value ? 'move' : 'default')
const showLabels = ref(true)

// Annotation rendering
function isValidPoint(pt: any): boolean {
  return pt && typeof pt.x === 'number' && typeof pt.y === 'number'
}

const currentEntries = computed(() => {
  if (!store.annotationData?.va) return []
  return store.annotationData.va
    .map((e: any, i: number) => {
      if (!Array.isArray(e.pts)) return null
      const goodPts = e.pts.filter((pt: any) => isValidPoint(pt))
      if (goodPts.length < 3) return null
      return { ...e, _origIdx: i, pts: goodPts }
    })
    .filter(Boolean) as Array<{ label: number; labelname: string; pts: Array<{ x: number; y: number }>; _origIdx: number }>
})

function toPathData(pts: Array<{ x: number; y: number }>): string {
  if (pts.length < 2) return ''
  let d = `M ${pts[0].x} ${pts[0].y}`
  for (let i = 1; i < pts.length; i++) {
    d += ` L ${pts[i].x} ${pts[i].y}`
  }
  d += ' Z'
  return d
}

function toPathLinePoints(pts: Array<{ x: number; y: number }>): number[] {
  const all = [...pts, pts[0]]
  return all.flatMap(p => [p.x, p.y])
}

function polygonArea(pts: Array<{ x: number; y: number }>): number {
  let area = 0
  for (let i = 0; i < pts.length; i++) {
    const j = (i + 1) % pts.length
    area += pts[i].x * pts[j].y
    area -= pts[j].x * pts[i].y
  }
  return Math.abs(area / 2)
}

function getLabelWithArea(entry: { labelname: string; label: number; pts: Array<{ x: number; y: number }> }): string {
  const label = entry.labelname || `${entry.label}`
  if (!entry.pts || entry.pts.length < 3) return label
  const area = polygonArea(entry.pts)
  return `${label} | ${area.toFixed(1)}`
}

function labelWidthPx(entry: { labelname: string; label: number; pts?: Array<{ x: number; y: number }> }): number {
  const text = entry.labelname || `${entry.label}`
  return (text.length * 7 + 8) / scale.value
}

function onMouseDown(e: any) {
  if (e.evt.button !== 2) return // only right-click triggers panning
  isPanning.value = true
  const rect = containerRef.value!.getBoundingClientRect()
  lastPos.value = { x: e.evt.clientX - rect.left, y: e.evt.clientY - rect.top }
}

function onMouseMove(e: any) {
  if (!isPanning.value) return
  const rect = containerRef.value!.getBoundingClientRect()
  const screenX = e.evt.clientX - rect.left
  const screenY = e.evt.clientY - rect.top
  const dx = screenX - lastPos.value.x
  const dy = screenY - lastPos.value.y
  const stageNode = stageRef.value?.getNode()
  if (stageNode) {
    stageNode.x(stageNode.x() + dx)
    stageNode.y(stageNode.y() + dy)
    stageNode.getLayer()?.batchDraw()
  }
  lastPos.value = { x: screenX, y: screenY }
}

function onMouseUp() {
  isPanning.value = false
  const stageNode = stageRef.value?.getNode()
  if (stageNode) {
    panX.value = stageNode.x()
    panY.value = stageNode.y()
  }
}

function handleWheel(e: WheelEvent) {
  e.preventDefault()
  const oldScale = scale.value
  const delta = e.deltaY > 0 ? 0.9 : 1.1
  scale.value = Math.max(0.01, Math.min(10, scale.value * delta))

  const rect = containerRef.value?.getBoundingClientRect()
  if (rect) {
    const mouseX = (e.clientX - rect.left) / oldScale - panX.value / oldScale
    const mouseY = (e.clientY - rect.top) / oldScale - panY.value / oldScale
    panX.value = mouseX * (oldScale - scale.value) + panX.value
    panY.value = mouseY * (oldScale - scale.value) + panY.value
  }
}

function resizeContainer() {
  if (containerRef.value) {
    const rect = containerRef.value.getBoundingClientRect()
    stageWidth.value = rect.width
    stageHeight.value = rect.height
    if (imageReady.value) centerImage()
  }
}

function centerImage() {
  panX.value = (stageWidth.value - imgW.value * scale.value) / 2
  panY.value = (stageHeight.value - imgH.value * scale.value) / 2
}

function loadImage() {
  if (!store.currentImage) return
  imageReady.value = false
  _loadGen++
  const gen = _loadGen

  const imgPath = store.getPreviewPathByImage(store.currentImage)
  const img = new window.Image()
  img.crossOrigin = 'anonymous'
  img.onload = () => {
    if (gen !== _loadGen) return // discard stale load
    imgW.value = img.naturalWidth
    imgH.value = img.naturalHeight
    bgImage.value = img
    imageReady.value = true
    scale.value = Math.min(1, (stageWidth.value - 40) / img.naturalWidth, (stageHeight.value - 40) / img.naturalHeight)
    centerImage()
  }
  img.onerror = () => {
    if (gen !== _loadGen) return
    ElMessage.error('图片加载失败')
    imageReady.value = false
  }
  img.src = imgPath
}

async function deleteImage() {
  startLoading()
  await store.deleteCurrentImage()
  stopLoading()
}

async function downloadImage() {
  if (!store.currentImage) return
  loadingDownloadImage.value = true
  try {
    const token = localStorage.getItem('token')
    const url = `/api/annotations/${modelId.value}/${store.resourceType}/${encodeURIComponent(store.currentImage.rel_path)}/download`
    const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
    if (!res.ok) throw new Error('下载失败')
    const data = await res.json()

    // 下载图片
    const imgBlob = base64ToBlob(data.image, 'image/*')
    const imgBlobUrl = URL.createObjectURL(imgBlob)
    const a1 = document.createElement('a')
    a1.href = imgBlobUrl
    a1.download = store.currentImage.name
    a1.click()
    URL.revokeObjectURL(imgBlobUrl)

    // 下载标注 JSON（如果有）
    if (data.annotation) {
      const jsonBlob = base64ToBlob(data.annotation, 'application/json')
      const jsonBlobUrl = URL.createObjectURL(jsonBlob)
      const a2 = document.createElement('a')
      a2.href = jsonBlobUrl
      a2.download = store.currentImage.name.replace(/\.\w+$/, '.json')
      a2.click()
      URL.revokeObjectURL(jsonBlobUrl)
    }

    ElMessage.success('下载成功')
  } catch (e: any) {
    ElMessage.error(e.message || '下载失败')
    return
  } finally {
    loadingDownloadImage.value = false
  }
}

function onSwitchResource(type: 'test' | 'template') {
  store.switchResourceType(type)
}

function applyCursor() {
  if (stageRef.value) {
    stageRef.value.getNode().container()?.style.setProperty('cursor', cursor.value)
  }
}

watch(cursor, () => applyCursor())

watch(() => store.currentImage, async (newImg) => {
  if (!newImg) {
    imageReady.value = false
    bgImage.value = null
  } else {
    imageReady.value = false
    loadImage()
    await store.loadAnnotation(newImg)
  }
})

function handleKeyDown(e: KeyboardEvent) {
  const target = e.target as HTMLElement
  if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) return
  if (e.key === 'ArrowLeft') { e.preventDefault(); store.prevImage() }
  if (e.key === 'ArrowRight') { e.preventDefault(); store.nextImage() }
}

onMounted(() => {
  resizeContainer()
  window.addEventListener('resize', resizeContainer)
  window.addEventListener('keydown', handleKeyDown)
  nextTick(() => applyCursor())
  containerRef.value!.addEventListener('wheel', handleWheel, { passive: false })

  const type = (route.query.type as 'test' | 'template') || 'test'
  store.loadModel(modelId.value, type)
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeContainer)
  window.removeEventListener('keydown', handleKeyDown)
  containerRef.value?.removeEventListener('wheel', handleWheel)
})
</script>

<style scoped lang="scss">
.preview-page {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.preview-body {
  display: flex;
  gap: var(--spacing-md);
  flex: 1;
  min-height: 0;
}

.canvas-container {
  flex: 1;
  min-width: 0;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  position: relative;
  touch-action: none;
  user-select: none;
  -webkit-user-drag: none;
  display: flex;
  flex-direction: column;
}

.canvas-title {
  flex-shrink: 0;
  padding: 6px var(--spacing-md);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-light);
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.canvas-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: var(--text-secondary);
}
</style>
