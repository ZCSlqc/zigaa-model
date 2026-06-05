<template>
  <div class="zip-upload">
    <input
      ref="inputRef"
      type="file"
      accept=".zip"
      multiple
      style="display: none"
      @change="handleFileSelect"
    />

    <!-- 暂存区：虚线框内有文件列表，无文件时显示提示 -->
    <div
      v-if="!isProcessing"
      class="upload-area"
      :class="{ dragging }"
      @click="triggerSelect"
      @drop.prevent="handleDrop"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
    >
      <div v-if="pendingFiles.length === 0" class="upload-hint">
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <p class="upload-text">{{ dragging ? '释放选择 ZIP' : '点击或拖拽 ZIP 文件到此处（支持多选）' }}</p>
      </div>
      <div v-for="(item, idx) in pendingFiles" :key="idx" class="pending-item">
        <el-icon class="file-icon"><Document /></el-icon>
        <span class="file-name" :title="item.name">{{ item.name }}</span>
        <span class="file-size">{{ formatSize(item.size) }}</span>
        <el-icon class="remove-icon" @click.stop="removePending(idx)"><Close /></el-icon>
      </div>
      <div v-if="pendingFiles.length > 0" class="add-hint">
        <span class="add-text">点击或拖拽继续添加</span>
      </div>
    </div>

    <!-- 暂存区按钮（框外） -->
    <div v-if="!isProcessing" class="pending-actions">
      <el-button @click="clearPending" :disabled="pendingFiles.length === 0">清除</el-button>
      <el-button type="primary" :disabled="pendingFiles.length === 0" @click="startUpload">上传 ({{ pendingFiles.length }})</el-button>
    </div>

    <!-- 上传中队列 -->
    <div v-if="fileQueue.length > 0" class="file-queue">
      <div v-for="item in fileQueue" :key="item.uploadId" class="queue-item">
        <div class="queue-header">
          <el-icon :class="['status-icon', statusIconClass(item.status)]">
            <component :is="statusIcon(item.status)" />
          </el-icon>
          <span class="file-name" :title="item.file.name">{{ item.file.name }}</span>
          <span class="file-size">{{ formatSize(item.file.size) }}</span>
          <span class="status-text">{{ statusText(item.status, item.result, item.error) }}</span>
        </div>
        <el-progress
          :percentage="Math.round(item.progress)"
          :status="item.status === 'failed' ? 'exception' : item.status === 'completed' ? 'success' : undefined"
          :stroke-width="6"
        />
        <div v-if="item.status === 'uploading' || item.status === 'processing'" class="progress-detail">
          {{ progressDetail(item) }}
        </div>
      </div>

      <div class="queue-actions">
        <el-button @click="cancelAll">取消</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Document, Loading, CircleCheckFilled, CircleCloseFilled, Close } from '@element-plus/icons-vue'
import { uploadInit, uploadChunk, uploadComplete, checkDiskSpace, getUploadStatus } from '../../api/resource'

const props = defineProps<{
  modelId: string
  type: 'good' | 'defect' | 'test' | 'template'
}>()

const emit = defineEmits<{
  uploaded: [result: any]
  'all-uploaded': []
}>()

const CHUNK_SIZE = 64 * 1024 * 1024

interface UploadFileItem {
  file: File
  uploadId: string
  status: 'uploading' | 'processing' | 'completed' | 'failed'
  progress: number
  totalChunks: number
  completedChunks: number
  result?: { passed_count: number; failed_count: number; errors: any[] }
  error?: string
  pollTimer?: ReturnType<typeof setInterval>
  countdownTimer?: ReturnType<typeof setInterval>
  controller?: AbortController | undefined
  // processing countdown
  estimatedSeconds: number
  countdownSeconds: number
  // per-item upload velocity tracking
  velocity: number
  lastLoaded: number
  lastTime: number
  etaSeconds: number
}

const inputRef = ref<HTMLInputElement>()
const dragging = ref(false)
const pendingFiles = ref<{ file: File; name: string; size: number }[]>([])
const fileQueue = ref<UploadFileItem[]>([])
const isProcessing = ref(false)

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' KB'
  if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB'
  return (bytes / 1024 / 1024 / 1024).toFixed(2) + ' GB'
}

function generateUploadId(file: File): string {
  // Simple hash (FNV-1a) to avoid crypto.subtle which requires HTTPS
  const key = `${props.modelId}-${props.type}-${file.name}-${file.size}-${file.lastModified}`
  let h1 = 0xdeadbeef, h2 = 0x41c6ce57
  for (let i = 0; i < key.length; i++) {
    const ch = key.charCodeAt(i)
    h1 = Math.imul(h1 ^ ch, 2654435761)
    h2 = Math.imul(h2 ^ ch, 1597334677)
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909)
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909)
  return ((h1 >>> 0).toString(16).padStart(8, '0') + (h2 >>> 0).toString(16).padStart(8, '0')).slice(0, 32)
}

function triggerSelect() {
  if (isProcessing.value) return
  inputRef.value?.click()
}

function handleFileSelect(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (files) addPendingFiles(Array.from(files))
  if (inputRef.value) inputRef.value.value = ''
}

function handleDrop(e: DragEvent) {
  dragging.value = false
  const files = e.dataTransfer?.files
  if (files) addPendingFiles(Array.from(files))
}

function addPendingFiles(files: File[]) {
  for (const file of files) {
    if (!file.name.toLowerCase().endsWith('.zip')) continue
    pendingFiles.value.push({ file, name: file.name, size: file.size })
  }
}

function removePending(idx: number) {
  pendingFiles.value.splice(idx, 1)
}

function clearPending() {
  pendingFiles.value = []
}

function startUpload() {
  if (pendingFiles.value.length === 0 || isProcessing.value) return

  // 收集已在队列和上传中的文件名，去重
  const existingNames = new Set(fileQueue.value.map(item => item.file.name))
  const uniquePending: typeof pendingFiles.value = []
  for (const pf of pendingFiles.value) {
    if (!existingNames.has(pf.file.name)) {
      uniquePending.push(pf)
      existingNames.add(pf.file.name)
    }
  }
  if (uniquePending.length < pendingFiles.value.length) {
    ElMessage.warning(`已跳过 ${pendingFiles.value.length - uniquePending.length} 个重复文件`)
  }

  for (const pf of uniquePending) {
    const item: UploadFileItem = {
      file: pf.file,
      uploadId: generateUploadId(pf.file),
      status: 'uploading',
      progress: 0,
      totalChunks: Math.ceil(pf.size / CHUNK_SIZE),
      completedChunks: 0,
      estimatedSeconds: 0,
      countdownSeconds: 0,
      velocity: 30 * 1024 * 1024,
      lastLoaded: 0,
      lastTime: 0,
      etaSeconds: 0,
    }
    fileQueue.value.push(item)
  }
  pendingFiles.value = []
  drainQueue()
}

function statusIcon(status: string) {
  const map: Record<string, any> = {
    uploading: Loading,
    processing: Loading,
    completed: CircleCheckFilled,
    failed: CircleCloseFilled,
  }
  return map[status] || Document
}

function statusIconClass(status: string) {
  const map: Record<string, string> = {
    uploading: 'icon-uploading',
    processing: 'icon-processing',
    completed: 'icon-completed',
    failed: 'icon-failed',
  }
  return map[status] || ''
}

function statusText(status: string, result?: any, error?: string) {
  if (status === 'completed' && result) {
    return `通过 ${result.passed_count} 张，失败 ${result.failed_count} 张`
  }
  if (status === 'failed') return error || '处理失败'
  const map: Record<string, string> = {
    uploading: '上传中',
    assembling: '后端处理中',
    processing: '后端处理中',
    completed: '完成',
  }
  return map[status] || status
}

function progressDetail(item: UploadFileItem): string {
  if (item.status === 'uploading') {
    let text = `${Math.round(item.progress)}%`
    if (item.velocity > 0 && item.etaSeconds > 0) {
      const speedMb = (item.velocity / (1024 * 1024)).toFixed(0)
      const mins = Math.floor(item.etaSeconds / 60)
      const secs = item.etaSeconds % 60
      text += ` | 速度 ${speedMb}MB/s | 预计 ${mins}分${secs}秒`
    }
    return text
  }
  if (item.status === 'processing') {
    if (item.countdownSeconds > 2) {
      const mins = Math.floor(item.countdownSeconds / 60)
      const secs = item.countdownSeconds % 60
      const text = mins > 0 ? `${mins}分${secs}秒` : `${secs}秒`
      return `后端处理中 | 预计 ${text}`
    }
    return `后端处理中 | 预计 2秒`
  }
  return ''
}

async function drainQueue() {
  isProcessing.value = true
  let i = 0
  while (i < fileQueue.value.length) {
    const item = fileQueue.value[i]
    await uploadOneFile(item)
    if (item.result) {
      emit('uploaded', item.result)
    }
    i++
  }
  // 所有文件已交后端，等 processing 的完成后再关闭
  checkAllDone()
}

function checkAllDone() {
  const remaining = fileQueue.value.filter(item => item.status === 'processing')
  if (remaining.length === 0) {
    isProcessing.value = false
    fileQueue.value = []
    emit('all-uploaded')
  } else {
    setTimeout(checkAllDone, 2000)
  }
}

async function uploadOneFile(item: UploadFileItem) {
  item.status = 'uploading'
  item.progress = 0
  item.controller = new AbortController()
  item.lastLoaded = 0
  item.lastTime = 0
  item.velocity = 30 * 1024 * 1024
  item.etaSeconds = 0
  item.estimatedSeconds = 0
  item.countdownSeconds = 0

  const file = item.file
  const totalChunks = item.totalChunks
  const calcEta = (loaded: number, total: number) => {
    const now = Date.now()
    if (item.lastTime > 0 && loaded > item.lastLoaded) {
      const dt = (now - item.lastTime) / 1000
      const dv = loaded - item.lastLoaded
      item.velocity = 0.3 * (dv / dt) + 0.7 * item.velocity
    }
    item.lastLoaded = loaded
    item.lastTime = now
    if (item.velocity > 0) {
      item.etaSeconds = Math.ceil((total - loaded) / item.velocity)
    }
  }

  try {
    const diskRes: any = await checkDiskSpace(props.modelId, props.type)
    const freeGb = diskRes.data.free_gb
    const fileSizeGb = file.size / (1024 * 1024 * 1024)
    if (fileSizeGb > freeGb * 0.4) {
      item.status = 'failed'
      item.error = `剩余空间 ${Math.floor(freeGb)}GB，空间不足`
      ElMessage.error(item.error)
      return
    }

    const initRes: any = await uploadInit(props.modelId, props.type, {
      upload_id: item.uploadId,
      filename: file.name,
      total_size: file.size,
      total_chunks: totalChunks,
      chunk_size: CHUNK_SIZE,
    })

    const skipped = new Set(initRes.data.uploaded_chunks || [])
    let completedChunks = skipped.size

    for (let ci = 0; ci < totalChunks; ci++) {
      if (item.controller?.signal.aborted) return
      if (skipped.has(ci)) {
        item.progress = Math.max(item.progress, (completedChunks / totalChunks) * 95)
        calcEta(completedChunks * CHUNK_SIZE, file.size)
        continue
      }
      const start = ci * CHUNK_SIZE
      const end = Math.min(start + CHUNK_SIZE, file.size)
      const chunkBlob = file.slice(start, end)
      const res: any = await uploadChunk(props.modelId, props.type, item.uploadId, ci, chunkBlob, item.controller.signal)
      completedChunks = res.data.uploaded
      item.completedChunks = completedChunks
      item.progress = Math.max(item.progress, (completedChunks / totalChunks) * 95)
      calcEta(completedChunks * CHUNK_SIZE, file.size)
    }

    if (item.controller?.signal.aborted) return

    await uploadComplete(props.modelId, props.type, item.uploadId, item.controller.signal)

    item.status = 'processing'
    item.progress = 95
    startPolling(item)
  } catch (e: any) {
    if (e.name === 'AbortError') {
      item.status = 'failed'
      item.error = '已取消'
      ElMessage.info('已取消')
    } else {
      item.status = 'failed'
      item.error = e.response?.data?.detail || '上传失败'
      ElMessage.error(item.error)
    }
  }
}

function startPolling(item: UploadFileItem) {
  // 初始化倒计时
  item.estimatedSeconds = item.estimatedSeconds || Math.max(5, Math.round(item.file.size / (1024 ** 3) * 10))
  item.countdownSeconds = item.estimatedSeconds

  // 每秒倒计时，到 2s 停住
  item.countdownTimer = setInterval(() => {
    if (item.status !== 'processing') {
      clearInterval(item.countdownTimer)
      return
    }
    if (item.countdownSeconds > 2) {
      item.countdownSeconds--
    }
  }, 1000)

  item.pollTimer = setInterval(async () => {
    if (item.status !== 'processing') return
    try {
      const res: any = await getUploadStatus(props.modelId, props.type, item.uploadId)
      const d = res.data
      if (d.status === 'completed') {
        item.status = 'completed'
        item.progress = 100
        item.result = d.result
        clearInterval(item.pollTimer)
        clearInterval(item.countdownTimer)
      } else if (d.status === 'failed') {
        item.status = 'failed'
        item.error = d.error || '处理失败'
        clearInterval(item.pollTimer)
        clearInterval(item.countdownTimer)
        ElMessage.error(`${item.file.name} 处理失败: ${item.error}`)
      } else {
        // processing 阶段保持 95%，不以后端进度覆盖（后端进度是阶段内 0-100）
        if (d.estimated_seconds) {
          item.estimatedSeconds = d.estimated_seconds
          if (!item.countdownSeconds || item.countdownSeconds <= 2) {
            item.countdownSeconds = d.estimated_seconds
          }
        }
      }
    } catch {
      // ignore polling errors
    }
  }, 5000)
}

function cancelAll() {
  for (const item of fileQueue.value) {
    if (item.controller) {
      item.controller.abort()
    }
    if (item.pollTimer) {
      clearInterval(item.pollTimer)
    }
    if (item.countdownTimer) {
      clearInterval(item.countdownTimer)
    }
  }
  fileQueue.value = []
  isProcessing.value = false
}

onUnmounted(() => {
  for (const item of fileQueue.value) {
    if (item.controller) {
      item.controller.abort()
    }
    if (item.pollTimer) {
      clearInterval(item.pollTimer)
    }
    if (item.countdownTimer) {
      clearInterval(item.countdownTimer)
    }
  }
})
</script>

<style scoped lang="scss">
.upload-area {
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-md);
  padding: 16px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  min-height: 120px;

  &:hover,
  &.dragging {
    border-color: var(--color-primary);
    background: rgba(64, 158, 255, 0.05);
  }
}

.upload-hint {
  padding: 24px 0;
}

.upload-icon {
  font-size: 48px;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-md);
}

.upload-text {
  font-size: 14px;
  color: var(--text-regular);
  margin: 0;
}

.pending-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 4px;
  text-align: left;

  &:hover {
    background: var(--bg-hover, #f5f7fa);
    border-radius: var(--radius-sm);
  }
}

.file-icon {
  font-size: 20px;
  color: var(--color-primary);
  flex-shrink: 0;
}

.file-name {
  font-size: 14px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.file-size {
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.remove-icon {
  font-size: 16px;
  color: var(--text-secondary);
  cursor: pointer;
  flex-shrink: 0;
  padding: 4px;
  border-radius: 50%;
  transition: all 0.2s;

  &:hover {
    color: var(--color-danger);
    background: rgba(245, 108, 108, 0.1);
  }
}

.add-hint {
  padding: 12px 0 4px;
  border-top: 1px dashed var(--border-light);
  margin-top: 4px;
}

.add-text {
  font-size: 13px;
  color: var(--text-placeholder);
}

.pending-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

.file-queue {
  margin-top: 20px;
}

.queue-item {
  padding: 12px 0;
  border-bottom: 1px solid var(--border-light);

  &:last-child {
    border-bottom: none;
  }
}

.queue-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.status-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.icon-uploading,
.icon-processing {
  color: var(--color-primary);
}

.icon-completed {
  color: var(--color-success);
}

.icon-failed {
  color: var(--color-danger);
}

.status-text {
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-detail {
  font-size: 13px;
  color: var(--text-regular);
  margin-top: 4px;
  padding-left: 24px;
}

.queue-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}
</style>
