<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="520px"
    :close-on-click-modal="false"
    destroy-on-close
    @close="handleClose"
  >
    <div class="batch-download">
      <!-- 选择区 -->
      <div v-if="!downloading && !props.autoStart" class="select-area">
        <el-checkbox-group v-model="selected">
          <div v-for="name in props.arrangeNames" :key="name" class="select-item">
            <el-checkbox :label="name" />
          </div>
        </el-checkbox-group>
      </div>

      <!-- 下载队列 -->
      <div v-if="fileQueue.length > 0" class="file-queue">
        <div v-for="item in fileQueue" :key="item.name" class="queue-item">
          <div class="queue-header">
            <el-icon :class="['status-icon', statusIconClass(item.status)]">
              <component :is="statusIcon(item.status)" />
            </el-icon>
            <span class="file-name" :title="item.name">{{ item.name }}</span>
            <span class="file-size">{{ formatSize(item.totalSize) }}</span>
            <span class="status-text">{{ statusText(item) }}</span>
          </div>
          <el-progress
            :percentage="Math.round(item.percentage)"
            :status="item.status === 'error' ? 'exception' : item.status === 'complete' ? 'success' : undefined"
            :stroke-width="6"
          />
          <div v-if="item.status === 'downloading'" class="progress-detail">
            {{ item.progressText }}
          </div>
          <div v-else-if="item.status === 'assembling'" class="progress-detail">
            正在组装文件...
          </div>
        </div>
      </div>

      <div class="batch-actions">
        <template v-if="!downloading">
          <el-button v-if="!props.autoStart" @click="toggleSelectAll">
            {{ allSelected ? '取消全选' : '全选' }}
          </el-button>
          <el-button type="primary" @click="startDownload" :disabled="selected.length === 0">
            下载 ({{ selected.length }})
          </el-button>
        </template>
        <el-button v-if="downloading" type="danger" @click="cancelDownload">取消下载</el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watchEffect } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading, CircleCheckFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import { LONG_TIMEOUT } from '../../api/client'
import { useDownloadManager, type DownloadSessionData } from '../../composables/useDownloadManager'
import type { DownloadConfig } from '../../composables/useDownloadManager'

const props = withDefaults(defineProps<{
  modelId: string
  resourceType: 'good' | 'defect' | 'test' | 'template'
  arrangeNames: string[]
  downloadApi: {
    init: (modelId: string, resourceType: string, arrangeName: string) => Promise<any>
    chunk: (modelId: string, resourceType: string, sessionId: string, chunkIndex: number, signal?: AbortSignal) => Promise<any>
    cleanup: (modelId: string, resourceType: string, sessionId: string) => Promise<any>
  }
  resourceLabel?: string
  autoStart?: boolean
}>(), {
  resourceLabel: '',
  autoStart: false,
})

const emit = defineEmits<{
  allDone: []
}>()

const visible = ref(false)
const selected = ref<string[]>([])
const downloading = ref(false)
let cancelled = false

const { state, startWithSession, cancel: cancelDownloadMgr, reset: resetManager, formatSize } = useDownloadManager()

// 下载队列
interface DownloadQueueItem {
  name: string
  status: 'downloading' | 'assembling' | 'complete' | 'error'
  percentage: number
  totalSize: number
  downloaded: number
  speed: number
  eta: number
  progressText: string
}

const fileQueue = ref<DownloadQueueItem[]>([])

const dialogTitle = computed(() => {
  return `选择要下载的批次 — ${props.resourceLabel || props.resourceType}`
})

const allSelected = computed(() => {
  return props.arrangeNames.length > 0 && selected.value.length === props.arrangeNames.length
})

function toggleSelectAll() {
  if (allSelected.value) {
    selected.value = []
  } else {
    selected.value = [...props.arrangeNames]
  }
}

function statusIcon(status: string) {
  if (status === 'downloading' || status === 'assembling') return Loading
  if (status === 'complete') return CircleCheckFilled
  if (status === 'error') return CircleCloseFilled
  return Loading
}

function statusIconClass(status: string) {
  if (status === 'downloading' || status === 'assembling') return 'icon-downloading'
  if (status === 'complete') return 'icon-complete'
  if (status === 'error') return 'icon-error'
  return ''
}

function statusText(item: DownloadQueueItem) {
  if (item.status === 'complete') return '完成'
  if (item.status === 'error') return '失败'
  if (item.status === 'assembling') return '正在组装...'
  return '下载中'
}

function downloadProgressDetail(item: DownloadQueueItem) {
  let text = `${Math.round(item.percentage)}%`
  if (item.speed > 0 && item.eta > 0) {
    const speedMb = (item.speed / (1024 * 1024)).toFixed(0)
    const mins = Math.floor(item.eta / 60)
    const secs = item.eta % 60
    text += ` | 速度 ${speedMb}MB/s | 预计 ${mins}分${secs}秒`
  }
  return text
}

function waitForComplete(timeout = LONG_TIMEOUT): Promise<boolean> {
  return new Promise((resolve) => {
    const start = Date.now()
    let resolved = false

    const finish = (ok: boolean) => {
      if (resolved) return
      resolved = true
      clearTimeout(timer)
      resolve(ok)
    }

    // watchEffect 响应式监听（主）
    const stop = watchEffect(() => {
      const s = state.status
      if (s === 'complete') { finish(true); stop() }
      else if (s === 'cancelled' || s === 'error') { finish(false); stop() }
    })

    // 轮询兜底（万一 watchEffect 依赖追踪出问题）
    const timer = setTimeout(() => { finish(false) }, timeout)
    const check = () => {
      if (resolved) return
      const now = Date.now()
      if (now - start > timeout) { finish(false); return }
      if (state.status === 'complete') { finish(true); return }
      if (state.status === 'cancelled' || state.status === 'error') { finish(false); return }
      setTimeout(check, 200)
    }
    check()
  })
}

// 更新队列条目的进度（响应 state 变化）
function updateQueueItem(name: string) {
  const item = fileQueue.value.find(i => i.name === name)
  if (!item) return
  item.percentage = Math.round(state.percentage)
  item.downloaded = state.downloaded
  item.speed = state.speed
  item.eta = state.eta
  item.progressText = downloadProgressDetail(item)
  if (state.status === 'assembling') {
    item.status = 'assembling'
    item.percentage = Math.max(item.percentage, 95)
  }
  // 当前正在下载的那个标记为 downloading
  if (item.status !== 'complete' && item.status !== 'error' && state.status !== 'idle') {
    item.status = 'downloading'
  }
}

async function startDownload() {
  // autoStart 模式：自动全选
  const targets = props.autoStart ? [...props.arrangeNames] : selected.value
  if (targets.length === 0) {
    ElMessage.warning('请至少选择一个批次')
    return
  }

  downloading.value = true
  if (props.autoStart) {
    selected.value = targets
  }

  fileQueue.value = targets.map(name => ({
    name, status: 'downloading' as const, percentage: 0,
    totalSize: 0, downloaded: 0, speed: 0, eta: 0, progressText: '',
  }))

  try {
    for (let i = 0; i < selected.value.length; i++) {
      if (cancelled) break
      const arrangeName = selected.value[i]

      try {
        // 1. 后端打包
        const initRes = await props.downloadApi.init(props.modelId, props.resourceType, arrangeName)
        const sessionData = initRes.data as DownloadSessionData
        const config: DownloadConfig = {
          modelId: props.modelId,
          resourceType: props.resourceType,
          filename: `${props.resourceType}_${arrangeName}.zip`,
          api: {
            init: () => Promise.resolve(),
            chunk: (mid, rt, sid, idx, signal) => props.downloadApi.chunk(mid, rt, sid, idx, signal),
            cleanup: (mid, rt, sid) => props.downloadApi.cleanup(mid, rt, sid),
          },
        }

        // 更新队列：设置 totalSize
        const item = fileQueue.value.find(q => q.name === arrangeName)
        if (item) {
          item.totalSize = sessionData.size
          item.status = 'downloading'
        }

        // 2. 开始下载（直接在当前弹窗内，不需要第二层弹窗）
        startWithSession(config, sessionData)

        // 3. 监听进度：每 200ms 更新队列条目
        const progressTimer = setInterval(() => updateQueueItem(arrangeName), 200)

        // 4. 等待完成
        const finished = await waitForComplete()
        clearInterval(progressTimer)

        if (!finished) {
          throw new Error(state.status === 'cancelled' ? '已取消' : '下载超时')
        }

        // 5. 异步清理 session（不阻塞主流程）
        props.downloadApi.cleanup(props.modelId, props.resourceType, sessionData.session_id).catch(() => {})

        const doneItem = fileQueue.value.find(q => q.name === arrangeName)
        if (doneItem) {
          doneItem.status = 'complete'
          doneItem.percentage = 100
        }

        resetManager()
      } catch (e: any) {
        const msg = e?.response?.data?.detail || e?.message || '下载失败'
        const errItem = fileQueue.value.find(q => q.name === arrangeName)
        if (errItem) errItem.status = 'error'
        if (state.status === 'downloading') {
          cancelDownloadMgr()
        }
        ElMessage.error(`批次 ${arrangeName} 下载失败: ${msg}`)
        resetManager()
      }
    }
  } finally {
    downloading.value = false
    emit('allDone')
    // 全部完成后自动关闭弹窗
    visible.value = false
  }
}

function cancelDownload() {
  cancelled = true
  cancelDownloadMgr()
  downloading.value = false
  fileQueue.value = []
  selected.value = []
  ElMessage.info('已取消下载')
  // 立即关闭弹窗
  visible.value = false
}

function handleClose() {
  if (downloading.value) {
    cancelDownload()
    // 关闭弹窗时清空队列和状态
    fileQueue.value = []
    selected.value = []
  } else {
    resetManager()
    selected.value = []
    fileQueue.value = []
  }
  downloading.value = false
}

function openDialog() {
  visible.value = true
  downloading.value = false
  fileQueue.value = []
  selected.value = []
  cancelled = false
  // autoStart 模式：打开即全选
  if (props.autoStart) {
    selected.value = [...props.arrangeNames]
    nextTick(() => { startDownload() })
  }
  nextTick(() => {
    selected.value = [...props.arrangeNames]
    const wrapper = document.querySelector('.select-area') as HTMLElement
    if (wrapper) {
      listMaxHeight.value = Math.min(360, props.arrangeNames.length * 44 + 20)
    }
  })
}

// 列表最大高度
const listMaxHeight = ref(360)

defineExpose({ openDialog })
</script>

<style scoped lang="scss">
.batch-download {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.select-area {
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 8px;
  background: var(--bg-card);
  max-height: 360px;

  .select-item {
    padding: 2px 0;
  }
}

.file-queue {
  margin-top: 0;
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

.icon-downloading,
.icon-assembling {
  color: var(--color-primary);
}

.icon-complete {
  color: var(--color-success);
}

.icon-error {
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

.batch-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>
