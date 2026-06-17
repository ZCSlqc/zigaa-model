<template>
  <AppLayout>
    <div class="annotate-page">
      <Toolbar
        @back="router.push(`/model/${modelId}`)"
        :mode="mode"
        :has-polygons="currentEntries.length > 0"
        :resource-type="store.resourceType as 'good' | 'defect'"
        :show-labels="showLabels"
        :show-edges="showEdges"
        :has-image="!!store.currentImage"
        :image-name="store.currentImage?.name"
        :loading-save="loadingSave"
        :loading-reset="loadingReset"
        :loading-delete-image="loadingDeleteImage"
        @set-mode="(m) => setMode(m as any)"
        @delete-all="deleteAnnotation"
        @reset-annotation="resetAnnotation"
        @save="saveAnnotation"
        @switch-resource="onSwitchResource"
        @toggle-labels="showLabels = !showLabels"
        @toggle-edges="showEdges = !showEdges"
        @delete-image="deleteImage"
      />

      <div class="annotate-body">
        <ImagePanel />

        <div class="canvas-container" ref="containerRef" @contextmenu.prevent>
          <div v-if="store.currentImage" class="canvas-title">
            <span class="canvas-title-info">
              图片路径：{{ store.currentImage.rel_path }}&ensp;|&ensp;通道数：{{ store.currentImage.channels || 3 }}&ensp;|&ensp;分辨率：{{ imgW }}×{{ imgH }}
            </span>
            <span class="canvas-title-category">
              <el-button
                v-for="opt in categoryOptions"
                :key="opt.value"
                :type="currentCategory === opt.value ? 'primary' : ''"
                size="small"
                :class="{ active: currentCategory === opt.value }"
                @click="setCategory(opt.value)"
              >{{ opt.label }}</el-button>
            </span>
          </div>
          <v-stage
            v-if="imageReady"
            ref="stageRef"
            :config="{ width: stageWidth, height: stageHeight, scaleX: scale, scaleY: scale, x: panX, y: panY }"
            @mousedown="handleStageMouseDown"
            @mousemove="handleStageMouseMove"
            @mouseup="handleStageMouseUp"
            @contextmenu.prevent
          >
            <v-layer>
              <v-image
                :config="{ image: bgImage, x: 0, y: 0, width: imgW, height: imgH }"
              />

              <!-- 1. 多边形（填充 + 边独立渲染以支持 hover 加粗） -->
              <template v-for="(entry, idx) in currentEntries" :key="idx" v-if="showEdges">
                <!-- 填充层 -->
                <v-path
                  :config="{
                    data: toPathData(entry.pts),
                    fill: 'rgba(64, 158, 255, 0.1)',
                    stroke: '#409eff',
                    strokeWidth: 0,
                    listening: false,
                  }"
                />
                <!-- select 模式：每条边独立渲染 -->
                <template v-if="mode === 'select'">
                  <v-line
                    v-for="(_pt, edgeI) in entry.pts"
                    :key="'edg-' + edgeI"
                    :config="{
                      points: [entry.pts[edgeI].x, entry.pts[edgeI].y, entry.pts[(edgeI + 1) % entry.pts.length].x, entry.pts[(edgeI + 1) % entry.pts.length].y],
                      stroke: isEdgeHovered(idx, edgeI) ? '#36b1ff' : '#409eff',
                      strokeWidth: isEdgeHovered(idx, edgeI) ? (ANNOTATION_EDGE_HOVER_WIDTH / scale) : (ANNOTATION_EDGE_WIDTH / scale),
                      tension: 0,
                      listening: false,
                    }"
                  />
                </template>
                <!-- 非 select 模式：一条闭合线 -->
                <v-line
                  v-if="mode !== 'select'"
                  :config="{
                    points: toPathLinePoints(entry.pts),
                    stroke: '#409eff',
                    strokeWidth: ANNOTATION_EDGE_WIDTH / scale,
                    tension: 0,
                    listening: false,
                  }"
                />
              </template>

              <!-- 2. 编辑模式下顶点控制点 -->
              <template v-if="mode === 'select'">
                <template v-for="(entry, eIdx) in currentEntries" :key="'h-' + eIdx">
                  <v-circle
                    v-for="(pt, i) in entry.pts"
                    :key="i"
                    :config="{
                      x: pt.x,
                      y: pt.y,
                      radius: isVertexHovered(eIdx, i) ? (ANNOTATION_VERTEX_HOVER_RADIUS / scale) : (ANNOTATION_VERTEX_RADIUS / scale),
                      fill: shiftKey && isVertexHovered(eIdx, i) ? '#f56c6c' : (isVertexHovered(eIdx, i) ? '#36b1ff' : '#409eff'),
                      stroke: '#fff',
                      strokeWidth: ANNOTATION_EDGE_WIDTH / scale,
                      draggable: !shiftKey,
                    }"
                    @dragmove="onEntryPointDragMove($event, entry._origIdx, i)"
                    @dragend="onEntryPointDragEnd($event, entry._origIdx, i)"
                  />
                </template>
              </template>

              <!-- 3. 标签（首点居中正上方） -->
              <template v-for="(entry, idx) in currentEntries" :key="'lbl-' + idx">
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
                      fill: isLabelHovered(idx) ? 'rgba(230, 162, 60, 1)' : 'rgba(230, 162, 60, 0.75)',
                      cornerRadius: 3 / scale,
                      lineHeight: 14 / scale,
                    }"
                  />
                  <v-text
                    :config="{
                      text: entry.labelname || `${entry.label}`,
                      fontSize: 12 / scale,
                      fontFamily: 'sans-serif',
                      fill: '#fff',
                      padding: 4 / scale,
                    }"
                  />
                </v-label>
              </template>

              <!-- 4. × 删除按钮（首点正下方，仅 select 模式） -->
              <template v-for="(entry, idx) in currentEntries" :key="'del-' + idx">
                <v-circle
                  v-if="mode === 'select'"
                  :config="{
                    x: entry.pts[0].x,
                    y: entry.pts[0].y + 8 / scale,
                    radius: ANNOTATION_DELETE_BTN_RADIUS / scale,
                    fill: isDeleteHovered(idx) ? 'rgba(245, 108, 108, 1)' : 'rgba(245, 108, 108, 0.75)',
                    stroke: '#fff',
                    strokeWidth: ANNOTATION_EDGE_WIDTH / scale,
                    listening: false,
                  }"
                />
              </template>



              <!-- 正在绘制中的线段 -->
              <v-line
                v-if="drawingPoints.length > 1"
                :config="{
                  points: linePoints(drawingPoints),
                  stroke: '#409eff',
                  strokeWidth: 1.5 / scale,
                  tension: 0,
                  listening: false,
                }"
              />

              <!-- 鼠标预览线 -->
              <v-line
                v-if="isDrawing && drawingPoints.length > 1"
                :config="{
                  points: previewLinePoints(),
                  stroke: 'rgba(64, 158, 255, 0.5)',
                  strokeWidth: 1 / scale,
                  tension: 0,
                  listening: false,
                }"
              />

              <!-- 绘制中的控制点 -->
              <v-circle
                v-for="(pt, i) in drawingPoints"
                :key="i"
                :config="{
                  x: pt.x,
                  y: pt.y,
                  radius: getPointRadius(i),
                  fill: getPointColor(i),
                  stroke: '#fff',
                  strokeWidth: ANNOTATION_EDGE_WIDTH / scale,
                  listening: false,
                }"
              />
            </v-layer>
          </v-stage>

          <div v-if="!store.currentImage" class="canvas-empty">
            请从左侧选择一张图片开始标注
          </div>
          <div v-else-if="!imageReady && store.annotationLoading" class="canvas-empty">
            加载图片中...
          </div>
        </div>
      </div>

      <!-- 标签编辑弹窗 -->
      <el-dialog v-model="showLabelDialog" :title="labelDialogTitle" width="450px" @open="onLabelDialogOpen" @close="onLabelDialogClose">
        <div class="label-dialog-input-row">
          <span class="label-dialog-text">新建标注</span>
          <el-input v-model="labelDialogInput" placeholder="输入标签名称" @keyup.enter="confirmLabelDialog" />
        </div>
        <div class="label-dialog-buttons" v-if="labelHistory.length > 0">
          <el-button v-for="(l, i) in labelHistory" :key="l" size="small" class="label-history-btn" @click="selectLabel(l)" @contextmenu.prevent="removeLabelHistory(i)">{{ l }}</el-button>
        </div>
        <template #footer>
          <div class="label-dialog-footer">
            <span class="label-dialog-hint">右键删除标签</span>
            <div class="label-dialog-footer-btns">
              <el-button @click="showLabelDialog = false">取消</el-button>
              <el-button type="primary" @click="confirmLabelDialog">确定</el-button>
            </div>
          </div>
        </template>
      </el-dialog>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppLayout from '../components/Layout/AppLayout.vue'
import Toolbar from '../components/Annotation/Toolbar.vue'
import ImagePanel from '../components/Annotation/ImagePanel.vue'
import { useAnnotationStore } from '../stores/annotation'

const route = useRoute()
const router = useRouter()
const store = useAnnotationStore()
const modelId = computed(() => route.params.modelId as string)

// Category buttons on canvas-title
const categoryOptions = [
  { label: '默认', value: 'none' },
  { label: '未标完', value: 'undone' },
  { label: '待确认', value: 'pending' },
]

const currentCategory = computed(() => store.currentImage?.category ?? 'none')

async function setCategory(category: string) {
  if (!store.currentImage) return
  const oldPath = store.currentImage.rel_path
  const images = store.getFilteredImages(store.categoryFilter)
  const idx = images.findIndex(i => i.path === store.currentImage!.path)
  await store.updateImageMsg(oldPath, category)
  if (store.categoryFilter) {
    const remaining = store.getFilteredImages(store.categoryFilter)
    if (remaining.length > 0) {
      store.selectImage(remaining[idx % remaining.length])
    } else {
      store.currentImage = null
      store.annotationData = null
    }
  }
}

// Canvas state
const containerRef = ref<HTMLElement>()
const stageRef = ref<any>(null)
const stageWidth = ref(800)
const stageHeight = ref(600)
const scale = ref(1)
const panX = ref(0)
const panY = ref(0)

// Persisted view state across image switches
let globalScale = 1
let globalPanX = 0
let globalPanY = 0
let firstLoad = true

// Image
const bgImage = ref<HTMLImageElement | null>(null)
const imgW = ref(0)
const imgH = ref(0)
const imageReady = ref(false)

// Drawing state
const mode = ref<'draw' | 'select'>('draw')
const drawingPoints = ref<Array<{ x: number; y: number }>>([])
const isDrawing = ref(false)
const showLabels = ref(true)
const showEdges = ref(true)

// Loading states with 500ms delay
let loadingTimer: ReturnType<typeof setTimeout> | null = null
let loadingTarget: 'save' | 'reset' | 'delete-image' | null = null
const loadingSave = ref(false)
const loadingReset = ref(false)
const loadingDeleteImage = ref(false)

function startLoading(target: 'save' | 'reset' | 'delete-image') {
  stopLoading()
  loadingTarget = target
  loadingTimer = setTimeout(() => {
    if (loadingTarget === 'save') loadingSave.value = true
    else if (loadingTarget === 'reset') loadingReset.value = true
    else loadingDeleteImage.value = true
  }, 500)
}
function stopLoading() {
  if (loadingTimer) { clearTimeout(loadingTimer); loadingTimer = null }
  loadingTarget = null
  loadingSave.value = false
  loadingReset.value = false
  loadingDeleteImage.value = false
}

// Hover state for interactive UI elements
const hoveredDeleteBtn = ref<number | null>(null)     // entry idx
const hoveredLabel = ref<number | null>(null)           // entry idx
const hoveredVertex = ref<{ entryIdx: number; ptIdx: number } | null>(null)  // hovered vertex control point
const hoveredEdge = ref<{ entryIdx: number; edgeIdx: number } | null>(null)   // hovered edge

const HIT_RADIUS = parseFloat(import.meta.env.VITE_HIT_RADIUS || '4')
const EDGE_HIT_RADIUS = parseFloat(import.meta.env.VITE_EDGE_HIT_RADIUS || '3')
const ANNOTATION_EDGE_WIDTH = parseFloat(import.meta.env.VITE_ANNOTATION_EDGE_WIDTH || '0.6')
const ANNOTATION_VERTEX_RADIUS = parseFloat(import.meta.env.VITE_ANNOTATION_VERTEX_RADIUS || '1')
const ANNOTATION_VERTEX_HOVER_RADIUS = parseFloat(import.meta.env.VITE_ANNOTATION_VERTEX_HOVER_RADIUS || '2.5')
const ANNOTATION_EDGE_HOVER_WIDTH = parseFloat(import.meta.env.VITE_ANNOTATION_EDGE_HOVER_WIDTH || '2.5')
const ANNOTATION_DELETE_BTN_RADIUS = parseFloat(import.meta.env.VITE_ANNOTATION_DELETE_BTN_RADIUS || '5')
const shiftKey = ref(false)

// Label dialog state
const showLabelDialog = ref(false)
const labelDialogTitle = ref('添加标注')
const labelDialogInput = ref('')
const labelHistory = ref<string[]>([]) // previously used label names
let labelDialogCallback: ((name: string | null) => void) | null = null
let labelDialogPending = false // whether drawing is waiting for label input

function openLabelDialog(title: string, defaultName: string, callback: (name: string | null) => void) {
  labelDialogTitle.value = title
  labelDialogCallback = callback
  labelDialogPending = true
  if (store.annotationData?.va) {
    for (const entry of store.annotationData.va) {
      const name = entry.labelname
      if (name && !labelHistory.value.includes(name)) {
        labelHistory.value.push(name)
      }
    }
  }
  labelDialogInput.value = labelHistory.value.length > 0 ? labelHistory.value[0] : defaultName || 'label_1'
  showLabelDialog.value = true
}

function onLabelDialogOpen() {
  // no-op
}

function onLabelDialogClose() {
  if (labelDialogPending) {
    labelDialogPending = false
    isDrawing.value = false
    isDrawingDrag.value = false
    lastDrawPoint.value = null
    hoveredPointIdx.value = null
    drawingPoints.value = []
  }
  labelDialogCallback = null
}

function selectLabel(name: string) {
  labelDialogInput.value = name
  confirmLabelDialog()
}

function removeLabelHistory(idx: number) {
  const name = labelHistory.value[idx]
  if (name) {
    labelHistory.value.splice(idx, 1)
  }
}

function confirmLabelDialog() {
  const name = labelDialogInput.value.trim() || null
  if (name && !labelHistory.value.includes(name)) {
    labelHistory.value.push(name)
  }
  // Save data and reset drawing state immediately
  if (labelDialogCallback) labelDialogCallback(name)
  labelDialogCallback = null
  labelDialogPending = false
  isDrawing.value = false
  isDrawingDrag.value = false
  lastDrawPoint.value = null
  hoveredPointIdx.value = null
  drawingPoints.value = []
  showLabelDialog.value = false
}

// Pan state
const isPanning = ref(false)
const lastPos = ref<{ x: number; y: number }>({ x: 0, y: 0 })

// Drawing interaction state
const hoveredPointIdx = ref<number | null>(null)
const mousePos = ref<{ x: number; y: number }>({ x: 0, y: 0 })
const isDrawingDrag = ref(false) // mouse down during draw, adding points by dragging
const lastDrawPoint = ref<{ x: number; y: number } | null>(null)
const DRAW_MIN_IMAGE_DIST = parseFloat(import.meta.env.VITE_DRAW_MIN_IMAGE_DIST || '1.5')
const DRAW_MIN_SCREEN_DIST = parseFloat(import.meta.env.VITE_DRAW_MIN_SCREEN_DIST || '8')

function isInImageBounds(pt: { x: number; y: number }): boolean {
  return pt.x >= 0 && pt.x <= imgW.value && pt.y >= 0 && pt.y <= imgH.value
}

/** Clamp a point to image boundaries [0, imgW] x [0, imgH] */
function clampToImage(pt: { x: number; y: number }): { x: number; y: number } {
  return {
    x: Math.max(0, Math.min(imgW.value, pt.x)),
    y: Math.max(0, Math.min(imgH.value, pt.y)),
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

  globalScale = scale.value
  globalPanX = panX.value
  globalPanY = panY.value
}

function resizeContainer() {
  if (containerRef.value) {
    const rect = containerRef.value.getBoundingClientRect()
    stageWidth.value = rect.width
    stageHeight.value = rect.height
    if (imageReady.value) centerImage()
  }
}

async function loadImage() {
  if (!store.currentImage) return
  imageReady.value = false
  hoveredPointIdx.value = null

  const origPath = store.getPreviewPathByImage(store.currentImage)
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const img = new window.Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      imgW.value = img.naturalWidth
      imgH.value = img.naturalHeight
      bgImage.value = img
      imageReady.value = true

      // First image: fit to canvas; subsequent images: keep global scale + pan
      if (firstLoad) {
        firstLoad = false
        const initScale = Math.min(1, (stageWidth.value - 40) / img.naturalWidth, (stageHeight.value - 40) / img.naturalHeight)
        scale.value = initScale
        globalScale = initScale
        centerImage()
        globalPanX = panX.value
        globalPanY = panY.value
      } else {
        scale.value = globalScale
        panX.value = globalPanX
        panY.value = globalPanY
      }
      resolve(img)
    }
    img.onerror = () => {
      ElMessage.error('图片加载失败')
      imageReady.value = false
      reject(new Error('图片加载失败'))
    }
    img.src = origPath
  })
}

function linePoints(pts: Array<{ x: number; y: number }>): number[] {
  return pts.flatMap(p => [p.x, p.y])
}

function previewLinePoints(): number[] {
  if (drawingPoints.value.length === 0) return []
  const last = drawingPoints.value[drawingPoints.value.length - 1]
  const clamped = clampToImage(mousePos.value)
  return [last.x, last.y, clamped.x, clamped.y]
}

function findHoveredPoint(skipLast: boolean = false) {
  const r = HIT_RADIUS / scale.value
  const startIdx = skipLast ? drawingPoints.value.length - 2 : drawingPoints.value.length - 1
  for (let i = startIdx; i >= 0; i--) {
    const pt = drawingPoints.value[i]
    const dx = pt.x - mousePos.value.x
    const dy = pt.y - mousePos.value.y
    const hitR = (i === 0 && drawingPoints.value.length >= 3) ? r * 2 : r
    if (dx * dx + dy * dy < hitR * hitR) return i
  }
  return null
}

function getPointColor(idx: number): string {
  if (hoveredPointIdx.value !== idx) return '#409eff'
  if (idx === drawingPoints.value.length - 1) return '#f56c6c'
  if (idx === 0 && drawingPoints.value.length >= 3) return '#67c23a'
  return '#409eff'
}

function getPointRadius(idx: number): number {
  if (hoveredPointIdx.value === idx) return ANNOTATION_VERTEX_HOVER_RADIUS / scale.value
  return ANNOTATION_VERTEX_RADIUS / scale.value
}
function toPathData(pts: Array<{ x: number; y: number }>): string {
  if (pts.length < 2) return ''
  let d = `M ${pts[0].x} ${pts[0].y}`
  for (let i = 1; i < pts.length; i++) {
    d += ` L ${pts[i].x} ${pts[i].y}`
  }
  d += ' Z'
  return d
}

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

function centerImage() {
  panX.value = (stageWidth.value - imgW.value * scale.value) / 2
  panY.value = (stageHeight.value - imgH.value * scale.value) / 2
  globalPanX = panX.value
  globalPanY = panY.value
}

function getStagePoint(e: any) {
  const stage = e.target.getStage()
  const pos = stage.getRelativePointerPosition()
  return { x: pos.x, y: pos.y }
}

function handleStageMouseDown(e: any) {
  // Right-click drag to pan in any mode
  if (e.evt.button === 2) {
    isPanning.value = true
    const containerRect = containerRef.value!.getBoundingClientRect()
    lastPos.value = { x: e.evt.clientX - containerRect.left, y: e.evt.clientY - containerRect.top }
    return
  }

  if (mode.value === 'select') {
    const pt = getStagePoint(e)

    // Shift + click on hovered vertex → delete that point
    if (shiftKey.value && hoveredVertex.value) {
      const { entryIdx, ptIdx } = hoveredVertex.value
      const entry = currentEntries.value[entryIdx]
      if (entry && entry.pts.length > 3) {
        const origIdx = entry._origIdx
        store.annotationData!.va[origIdx].pts.splice(ptIdx, 1)
        hoveredVertex.value = null
        return
      }
    }

    // Check insert button click (on hovered edge)
    if (hoveredEdge.value) {
      insertPointOnEdge(hoveredEdge.value.entryIdx, hoveredEdge.value.edgeIdx, pt)
      hoveredEdge.value = null
      return
    }

    // Check delete button click (below first good point)
    for (const entry of currentEntries.value) {
      if (!entry.pts.length) continue
      const fp = entry.pts[0]
      const dly = fp.y + 8 / scale.value
      const dbx = fp.x
      const dx = pt.x - dbx
      const dy = pt.y - dly
      if (dx * dx + dy * dy <= (7 / scale.value) * (7 / scale.value)) {
        deleteEntry(entry._origIdx)
        return
      }
    }

    // Check label click (label centered on first good point, above)
    if (showLabels.value) {
      for (const entry of currentEntries.value) {
        if (!entry.pts.length) continue
        const fp = entry.pts[0]
        const ly = fp.y - 24 / scale.value
        const halfW = labelWidthPx(entry) / 2 + 4 / scale.value
        if (Math.abs(pt.x - fp.x) < halfW && pt.y >= ly - 2 / scale.value && pt.y <= ly + 14 / scale.value) {
          startEditLabel(entry._origIdx)
          return
        }
      }
    }

    // Click on empty area → start panning
    const target = e.target
    const layer = target.getLayer()
    const bgImg = layer?.children?.[0]
    if (target === e.getStage() || target === bgImg) {
      isPanning.value = true
      const containerRect = containerRef.value!.getBoundingClientRect()
      lastPos.value = { x: e.evt.clientX - containerRect.left, y: e.evt.clientY - containerRect.top }
    }
    return
  }

  if (mode.value === 'draw' && imageReady.value && !showLabelDialog.value) {
    const pt = getStagePoint(e)

    if (hoveredPointIdx.value === drawingPoints.value.length - 1) {
      drawingPoints.value.pop()
      hoveredPointIdx.value = null
      if (drawingPoints.value.length < 2) {
        isDrawing.value = false
      }
      return
    }

    if (hoveredPointIdx.value === 0 && drawingPoints.value.length >= 3) {
      finishPolygon()
      return
    }

    isDrawingDrag.value = false
    lastDrawPoint.value = null
    if (!isDrawing.value) {
      isDrawing.value = true
      drawingPoints.value = []
    }
    // Clamp point to image boundaries
    const clampedPt = clampToImage(pt)
    drawingPoints.value.push(clampedPt)
    isDrawingDrag.value = true
    lastDrawPoint.value = { ...clampedPt }
  }
}

function handleStageMouseMove(e: any) {
  if (isPanning.value) {
    const containerRect = containerRef.value!.getBoundingClientRect()
    const screenX = e.evt.clientX - containerRect.left
    const screenY = e.evt.clientY - containerRect.top
    const dx = screenX - lastPos.value.x
    const dy = screenY - lastPos.value.y
    // Direct Konva API for smooth panning, sync refs on mouseUp
    const stageNode = stageRef.value?.getNode()
    if (stageNode) {
      stageNode.x(stageNode.x() + dx)
      stageNode.y(stageNode.y() + dy)
      stageNode.getLayer()?.batchDraw()
    }
    lastPos.value = { x: screenX, y: screenY }
    return
  }

  if (mode.value === 'draw') {
    if (!isDrawing.value) return
    const stage = e.target.getStage()
    const pos = stage.getRelativePointerPosition()
    const pt = { x: pos.x, y: pos.y }
    mousePos.value = pt

    if (isDrawingDrag.value && lastDrawPoint.value) {
      // Clamp point to image boundaries before distance check
      const clampedPt = clampToImage(pt)
      const dx = clampedPt.x - lastDrawPoint.value.x
      const dy = clampedPt.y - lastDrawPoint.value.y
      const minDist = Math.max(DRAW_MIN_IMAGE_DIST, DRAW_MIN_SCREEN_DIST / scale.value)
      if (dx * dx + dy * dy >= minDist * minDist) {
        drawingPoints.value.push(clampedPt)
        lastDrawPoint.value = clampedPt
      }
    }

    if (isInImageBounds(pt)) {
      hoveredPointIdx.value = findHoveredPoint(isDrawingDrag.value)
    } else {
      hoveredPointIdx.value = null
    }
    return
  }

  // Select mode: hover detection for label and delete button
  if (mode.value === 'select' && !isPanning.value) {
    const stageNode = stageRef.value?.getNode()
    const stageRect = stageNode?.container()?.getBoundingClientRect()
    if (stageRect) {
      const screenX = e.evt.clientX - stageRect.left
      const screenY = e.evt.clientY - stageRect.top
      const pt = {
        x: (screenX - panX.value) / scale.value,
        y: (screenY - panY.value) / scale.value,
      }

      let foundDelete = false
      let foundLabel = false
      let foundVertexOrEdge = false

      for (let idx = 0; idx < currentEntries.value.length; idx++) {
        const entry = currentEntries.value[idx]
        if (!entry.pts.length) continue
        const fp = entry.pts[0]

        // Delete button hover (below first point)
        const dly = fp.y + 8 / scale.value
        const dbx = fp.x
        const ddx = pt.x - dbx
        const ddy = pt.y - dly
        if (ddx * ddx + ddy * ddy <= (7 / scale.value) * (7 / scale.value)) {
          foundDelete = true
          hoveredDeleteBtn.value = idx
          break // delete button takes priority
        }

        // Label hover (centered on first point, above)
        const ly = fp.y - 24 / scale.value
        const halfW = labelWidthPx(entry) / 2 + 4 / scale.value
        if (Math.abs(pt.x - fp.x) < halfW && pt.y >= ly - 2 / scale.value && pt.y <= ly + 14 / scale.value) {
          foundLabel = true
          hoveredLabel.value = idx
        }
      }

      // Mutually exclusive: vertex hover OR edge hover
      // Only check when delete and label are not hit
      if (!foundDelete && !foundLabel) {
        const hit = findHoveredVertexOrEdge(pt)
        if (hit?.type === 'vertex') {
          foundVertexOrEdge = true
          hoveredVertex.value = { entryIdx: hit.entryIdx, ptIdx: hit.ptIdx }
          hoveredEdge.value = null
        } else if (hit?.type === 'edge') {
          foundVertexOrEdge = true
          hoveredEdge.value = { entryIdx: hit.entryIdx, edgeIdx: hit.edgeIdx }
          hoveredVertex.value = null
        }
      }

      if (!foundDelete) {
        hoveredDeleteBtn.value = null
      }
      if (!foundLabel) {
        hoveredLabel.value = null
      }
      if (!foundVertexOrEdge) {
        hoveredVertex.value = null
        hoveredEdge.value = null
      }

      // Update cursor based on hover state
      if (foundDelete || foundLabel || foundVertexOrEdge) {
        stageNode.container()?.style.setProperty('cursor', 'pointer')
      }
    }
  }
}

function handleStageMouseUp() {
  // Draw mode: close if mouse is near start point (use doubled radius like hover)
  if (isDrawing.value && drawingPoints.value.length >= 3) {
    const first = drawingPoints.value[0]
    const dx = mousePos.value.x - first.x
    const dy = mousePos.value.y - first.y
    const dist = Math.sqrt(dx * dx + dy * dy)
    const closeThreshold = (HIT_RADIUS * 2) / scale.value
    if (dist <= closeThreshold) {
      finishPolygon()
      isDrawingDrag.value = false
      lastDrawPoint.value = null
      isPanning.value = false
      return
    }
  }

  isDrawingDrag.value = false
  lastDrawPoint.value = null
  isPanning.value = false
  // Sync Konva stage position back to Vue refs
  const stageNode = stageRef.value?.getNode()
  if (stageNode) {
    panX.value = stageNode.x()
    panY.value = stageNode.y()
    globalPanX = panX.value
    globalPanY = panY.value
  }
}

async function finishPolygon(labelname?: string) {
  if (drawingPoints.value.length < 3) {
    drawingPoints.value = []
    isDrawing.value = false
    isDrawingDrag.value = false
    lastDrawPoint.value = null
    hoveredPointIdx.value = null
    return
  }

  if (!store.annotationData) {
    store.annotationData = {
      va: [],
      width: imgW.value,
      height: imgH.value,
      wl: 0,
      ww: 0,
    }
  }

  const nextLabel = store.annotationData.va.length + 1

  // Prompt for label name if not provided
  if (!labelname) {
    const defaultName = `label_${nextLabel}`
    openLabelDialog('添加标注', defaultName, async (name) => {
      if (name === null) {
        // cancelled — discard drawing, nothing to do
        drawingPoints.value = []
        isDrawing.value = false
        return
      }
      const finalName = name.trim() || defaultName
      store.annotationData!.va.push({
        label: nextLabel,
        labelname: finalName,
        pts: [...drawingPoints.value],
      })
      try { await store.save(true, false) } catch { /* silent */ }
    })
    return // callback handles the rest
  }

  store.annotationData.va.push({
    label: nextLabel,
    labelname,
    pts: [...drawingPoints.value],
  })
  try { await store.save(true, false) } catch { /* silent */ }

  drawingPoints.value = []
  isDrawing.value = false
  isDrawingDrag.value = false
  lastDrawPoint.value = null
  hoveredPointIdx.value = null
}


function isLabelHovered(idx: number): boolean {
  return hoveredLabel.value === idx
}

function isDeleteHovered(idx: number): boolean {
  return hoveredDeleteBtn.value === idx
}

function isVertexHovered(entryIdx: number, ptIdx: number): boolean {
  return hoveredVertex.value?.entryIdx === entryIdx && hoveredVertex.value?.ptIdx === ptIdx
}

function isEdgeHovered(entryIdx: number, edgeIdx: number): boolean {
  return hoveredEdge.value?.entryIdx === entryIdx && hoveredEdge.value?.edgeIdx === edgeIdx
}

/** Convert image-space point to screen-space for distance comparison */
function toScreenPt(pt: { x: number; y: number }): { x: number; y: number } {
  return { x: pt.x * scale.value + panX.value, y: pt.y * scale.value + panY.value }
}

/** Point-to-segment squared distance (image coords) */
function distToSegmentSq(px: number, py: number, ax: number, ay: number, bx: number, by: number): number {
  const dx = bx - ax, dy = by - ay
  const lenSq = dx * dx + dy * dy
  if (lenSq === 0) return (px - ax) ** 2 + (py - ay) ** 2
  let t = ((px - ax) * dx + (py - ay) * dy) / lenSq
  t = Math.max(0, Math.min(1, t))
  const cx = ax + t * dx, cy = ay + t * dy
  return (px - cx) ** 2 + (py - cy) ** 2
}

/** Closest point on segment AB to P */
function closestOnSeg(px: number, py: number, ax: number, ay: number, bx: number, by: number): { x: number; y: number } {
  const dx = bx - ax, dy = by - ay
  const lenSq = dx * dx + dy * dy
  if (lenSq === 0) return { x: ax, y: ay }
  let t = ((px - ax) * dx + (py - ay) * dy) / lenSq
  t = Math.max(0, Math.min(1, t))
  return { x: ax + t * dx, y: ay + t * dy }
}

/** Get line points array for v-line from pts (used in non-select mode) */
function toPathLinePoints(pts: Array<{ x: number; y: number }>): number[] {
  const all = [...pts, pts[0]] // closed
  return all.flatMap(p => [p.x, p.y])
}



/**
 * Mutually exclusive hover: vertex > edge.
 * Check vertices first; if any vertex is hovered, edges are ignored.
 */
function findHoveredVertexOrEdge(mousePt: { x: number; y: number }): { type: 'vertex'; entryIdx: number; ptIdx: number } | { type: 'edge'; entryIdx: number; edgeIdx: number } | null {
  // Convert mousePt to screen-space for vertex comparison
  const mouseScreen = toScreenPt(mousePt)
  const vertexThresholdSq = HIT_RADIUS ** 2

  for (let e = currentEntries.value.length - 1; e >= 0; e--) {
    const entry = currentEntries.value[e]
    for (let i = entry.pts.length - 1; i >= 0; i--) {
      const ptScreen = toScreenPt(entry.pts[i])
      const dx = mouseScreen.x - ptScreen.x
      const dy = mouseScreen.y - ptScreen.y
      if (dx * dx + dy * dy < vertexThresholdSq) {
        return { type: 'vertex', entryIdx: e, ptIdx: i }
      }
    }
  }

  // No vertex hovered — check edges
  const edgeThresholdSq = (EDGE_HIT_RADIUS / scale.value) ** 2
  let best: { entryIdx: number; edgeIdx: number; distSq: number } | null = null

  for (let e = 0; e < currentEntries.value.length; e++) {
    const entry = currentEntries.value[e]
    const pts = entry.pts
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i]
      const b = pts[(i + 1) % pts.length]
      const dSq = distToSegmentSq(mousePt.x, mousePt.y, a.x, a.y, b.x, b.y)
      if (dSq < edgeThresholdSq && (!best || dSq < best.distSq)) {
        best = { entryIdx: e, edgeIdx: i, distSq: dSq }
      }
    }
  }

  return best ? { type: 'edge', entryIdx: best.entryIdx, edgeIdx: best.edgeIdx } : null
}

/** Insert a new vertex on edge at closest point to mouse */
function insertPointOnEdge(entryIdx: number, edgeIdx: number, mousePt: { x: number; y: number }) {
  const entry = store.annotationData?.va?.[entryIdx]
  if (!entry) return
  const pts = entry.pts
  const a = pts[edgeIdx]
  const b = pts[(edgeIdx + 1) % pts.length]
  const newPt = closestOnSeg(mousePt.x, mousePt.y, a.x, a.y, b.x, b.y)
  pts.splice(edgeIdx + 1, 0, newPt)
}

// Approximate label width in image coords (7px per char + 8px tag padding)
function labelWidthPx(entry: { labelname: string; label: number }): number {
  const text = entry.labelname || `${entry.label}`
  return (text.length * 7 + 8) / scale.value
}


function startEditLabel(origIdx: number) {
  const entry = store.annotationData?.va?.[origIdx]
  if (!entry || !entry.pts.length) return

  openLabelDialog('添加标注', entry.labelname || `${entry.label}`, async (name) => {
    if (name && name.trim()) {
      entry.labelname = name.trim()
      try { await store.save(true, false) } catch { /* silent */ }
    }
  })
}



function onEntryPointDragMove(e: any, origIdx: number, pointIdx: number) {
  const node = e.target
  const entry = store.annotationData?.va?.[origIdx]
  if (entry && entry.pts[pointIdx]) {
    entry.pts[pointIdx].x = node.x()
    entry.pts[pointIdx].y = node.y()
  }
}

function onEntryPointDragEnd(_e: any, _idx: number, _pointIdx: number) {
  // no-op — 依赖 10s 定时保存
}

async function deleteEntry(origIdx: number) {
  if (!store.annotationData?.va || !store.annotationData.va[origIdx]) return
  store.annotationData.va.splice(origIdx, 1)
  ElMessage.success('已删除标注')
  try { await store.save(true, false) } catch { /* silent */ }
}

async function deleteAnnotation() {
  if (!store.annotationData) return
  store.annotationData.va = []
  try { await store.save(true, false) } catch { /* silent */ }
}

// Reset: restore snapshot to annotation, then persist to server
async function resetAnnotation() {
  if (!store.currentImage) return
  // Clear current draw state
  drawingPoints.value = []
  isDrawing.value = false
  hoveredPointIdx.value = null
  // Restore snapshot (初始态，给撤销用)
  if (store.initialSnapshot) {
    store.annotationData = JSON.parse(JSON.stringify(store.initialSnapshot))
    try { await store.save(true, false) } catch { /* silent */ }
    ElMessage.success('已撤销修改')
  } else {
    await store.loadAnnotation(store.currentImage)
    ElMessage.success('已撤销修改')
  }
  store.clearAutoSaveTimers()
}

async function saveAnnotation() {
  if (!imgW.value || !imgH.value) {
    ElMessage.warning('请先加载图片')
    return
  }

  if (!store.annotationData) {
    store.annotationData = {
      va: [],
      width: imgW.value,
      height: imgH.value,
      wl: 0,
      ww: 0,
    }
  }

  store.annotationData.width = imgW.value
  store.annotationData.height = imgH.value

  startLoading('save')
  try {
    await store.save(false, false)
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    stopLoading()
  }
}

async function deleteImage() {
  startLoading('delete-image')
  await store.deleteCurrentImage()
  stopLoading()
}

function onSwitchResource(type: 'good' | 'defect') {
  store.switchResourceType(type)
}

function setMode(m: 'draw' | 'select') {
  mode.value = m
  store.setMode(m)
  if (m !== 'draw') {
    isDrawing.value = false
    drawingPoints.value = []
    hoveredPointIdx.value = null
  }
}


// Watch for image change — serial load: clear → load image → load annotation
watch(
  () => store.currentImage,
  async (newImg, oldImg) => {
    // 1. Clear all state
    drawingPoints.value = []
    isDrawing.value = false
    hoveredPointIdx.value = null
    mode.value = 'draw'

    if (!newImg) {
      imageReady.value = false
      bgImage.value = null
      store.annotationData = null
      return
    }

    // 2. Clear canvas, load new image
    imageReady.value = false
    bgImage.value = null
    await loadImage()

    // 3. Load new annotation (image is ready, dims are set)
    if (newImg) {
      await store.loadAnnotation(newImg)
    }
  },
)

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Shift') shiftKey.value = true
  const target = e.target as HTMLElement
  const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable
  if (isInput) return

  if (e.ctrlKey && e.key === 's') {
    e.preventDefault()
    saveAnnotation()
  } else if (e.ctrlKey && e.key === 'z') {
    e.preventDefault()
    if (mode.value === 'draw' && isDrawing.value) {
      drawingPoints.value = []
      isDrawing.value = false
      hoveredPointIdx.value = null
    }
  } else if (e.key === ' ' && !e.ctrlKey) {
    e.preventDefault()
    if (mode.value === 'draw' && isDrawing.value && drawingPoints.value.length > 0) {
      drawingPoints.value.pop()
      hoveredPointIdx.value = null
    }
  } else if (e.key === 'Tab') {
    e.preventDefault()
    setMode(mode.value === 'draw' ? 'select' : 'draw')
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault()
    store.prevImage(store.categoryFilter)
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    store.nextImage(store.categoryFilter)
  }
}

function handleKeyUp(e: KeyboardEvent) {
  if (e.key === 'Shift') shiftKey.value = false
}

onMounted(() => {
  const type = (route.query.type as string) || 'good'
  if (type === 'test' || type === 'template') {
    router.replace(`/preview/${modelId.value}?type=${type}`)
    return
  }

  resizeContainer()
  window.addEventListener('resize', resizeContainer)
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('keyup', handleKeyUp)
  containerRef.value!.addEventListener('wheel', handleWheel, { passive: false })

  store.loadModel(modelId.value, type as 'good' | 'defect')
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeContainer)
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('keyup', handleKeyUp)
  if (containerRef.value) {
    containerRef.value.removeEventListener('wheel', handleWheel)
  }
})
</script>

<style scoped lang="scss">
.annotate-page {
  display: flex;
  flex-direction: column;
  height: 100%;
}


.annotate-body {
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
  cursor: crosshair;
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
  display: flex;
  justify-content: space-between;
  align-items: center;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.canvas-title-info {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex-shrink: 1;
  min-width: 0;
}

.canvas-title-category {
  display: inline-flex;
  gap: 2px;
  flex-shrink: 0;
  margin-left: var(--spacing-md);
}

.canvas-title-category :deep(.el-button) {
  padding: 0 6px;
  height: 22px;
  line-height: 22px;
  font-size: 11px;
  min-width: auto;
}

.canvas-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: var(--text-secondary);
}

.label-dialog-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 12px;
}

.label-history-btn {
  color: var(--el-text-color-secondary);
  border-color: var(--el-border-color-light);
  padding: 4px 12px;

  &:hover {
    color: #409eff;
    border-color: #409eff;
  }
}

.label-dialog-input-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.label-dialog-text {
  font-size: 14px;
  color: #333;
  white-space: nowrap;
}

.label-dialog-hint {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  white-space: nowrap;
}

.label-dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.label-dialog-footer-btns {
  display: flex;
  gap: 8px;
}

:deep(.el-dialog__footer) {
  justify-content: flex-start !important;
}

</style>
