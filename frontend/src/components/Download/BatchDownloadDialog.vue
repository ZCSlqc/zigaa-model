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
      <div class="arrange-list-wrapper" :style="{ maxHeight: listMaxHeight + 'px' }">
        <el-checkbox-group v-model="selected">
          <div v-for="name in props.arrangeNames" :key="name" class="arrange-item">
            <el-checkbox :label="name" :disabled="isStatus(name, 'downloading')">
              <span class="name">{{ name }}</span>
              <span v-if="isStatus(name, 'downloading')" class="status-tag downloading">下载中...</span>
              <span v-else-if="isStatus(name, 'complete')" class="status-tag done">✓</span>
              <span v-else-if="isStatus(name, 'error')" class="status-tag error">✗</span>
            </el-checkbox>
          </div>
        </el-checkbox-group>
      </div>

      <!-- 批量进度摘要 -->
      <div v-if="downloadingNames.length > 0 || completedCount > 0" class="batch-summary">
        <el-progress
          :percentage="summaryPercentage"
          :status="summaryStatus"
          :stroke-width="16"
          :text-inside="true"
        />
        <div class="summary-text">
          完成 {{ completedCount }}/{{ selected.length }}
        </div>
      </div>

      <div class="batch-actions">
        <el-button @click="toggleSelectAll">
          {{ allSelected ? '取消全选' : '全选' }}
        </el-button>
        <el-button type="danger" @click="cancelDownload" :disabled="selected.length === 0 || downloading">
          取消下载
        </el-button>
        <el-button type="primary" @click="startDownload" :disabled="selected.length === 0" :loading="downloading">
          下载 ({{ selected.length }})
        </el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useDownloadManager } from '../../composables/useDownloadManager'
import type { DownloadSessionData } from '../../composables/useDownloadManager'

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
}>(), {
  resourceLabel: ''
})

const emit = defineEmits<{
  allDone: []
}>()

const { state, startWithSession, cancel: cancelDownloadMgr, reset: resetManager, formatSize } = useDownloadManager()

const visible = ref(false)
const selected = ref<string[]>([])
const downloading = ref(false)
const itemStatuses = ref<Record<string, 'idle' | 'downloading' | 'complete' | 'error'>>({})
let downloadDialogClosedResolver: (() => void) | null = null

// 列表最大高度
const listMaxHeight = ref(360)

// 监听 DownloadDialog 关闭事件
function setupDialogCloseListener() {
  const handler = () => {
    if (downloadDialogClosedResolver) {
      downloadDialogClosedResolver()
      downloadDialogClosedResolver = null
    }
  }
  window.addEventListener('download-dialog-closed', handler)
}
setupDialogCloseListener()

const dialogTitle = computed(() => {
  return `选择要下载的批次 — ${props.resourceLabel || props.resourceType}`
})

const allSelected = computed(() => {
  return props.arrangeNames.length > 0 && selected.value.length === props.arrangeNames.length
})

const completedCount = computed(() => {
  return Object.values(itemStatuses.value).filter(s => s === 'complete').length
})

const downloadingNames = computed(() => {
  return Object.entries(itemStatuses.value)
    .filter(([, s]) => s === 'downloading')
    .map(([n]) => n)
})

const summaryPercentage = computed(() => {
  if (selected.value.length === 0) return 0
  return Math.round((completedCount.value / selected.value.length) * 100)
})

const summaryStatus = computed(() => {
  if (completedCount.value === selected.value.length && selected.value.length > 0) return 'success'
  return ''
})

function isStatus(name: string, target: string) {
  return itemStatuses.value[name] === target
}

const toggleSelectAll = () => {
  if (allSelected.value) {
    selected.value = []
  } else {
    selected.value = [...props.arrangeNames]
  }
}

// 等待 DownloadDialog 的弹窗关闭（visible 变 false）
function waitForDialogClose(timeout = 300000): Promise<void> {
  return new Promise((resolve) => {
    const start = Date.now()
    const check = () => {
      const ref = document.querySelector('[data-dialog-download]') as any
      const el = ref?.__vue_parent_component__?.vnode?.el as HTMLElement
      if (!el) {
        // 降级：用 setTimeout 等待
        setTimeout(resolve, 1500)
        return
      }
      if (!el.closest('.el-dialog')) {
        resolve()
        return
      }
      if (Date.now() - start > timeout) {
        resolve()
        return
      }
      setTimeout(check, 300)
    }
    check()
  })
}

// 等待 DownloadDialog 状态结束
function waitForComplete(timeout = 300000): Promise<boolean> {
  return new Promise((resolve) => {
    const start = Date.now()
    const check = () => {
      if (state.status === 'complete' || state.status === 'cancelled' || state.status === 'error') {
        resolve(true)
        return
      }
      if (Date.now() - start > timeout) {
        resolve(false)
        return
      }
      setTimeout(check, 200)
    }
    check()
  })
}

async function startDownload() {
  if (selected.value.length === 0) {
    ElMessage.warning('请至少选择一个批次')
    return
  }

  downloading.value = true
  const remaining = [...selected.value]
  // 重置状态
  itemStatuses.value = {}
  for (const name of remaining) {
    itemStatuses.value[name] = 'idle'
  }

  try {
    for (let i = 0; i < remaining.length; i++) {
      const arrangeName = remaining[i]

      // 标记为下载中
      itemStatuses.value[arrangeName] = 'downloading'

      try {
        // 1. 后端打包该文件夹
        const initRes = await props.downloadApi.init(props.modelId, props.resourceType, arrangeName)
        const sessionData = initRes.data as DownloadSessionData

        // 2. 打开 DownloadDialog 显示进度（这会弹出独立的 el-dialog）
        //    通过调用 window.dispatchEvent 通知顶层打开 DownloadDialog
        window.dispatchEvent(new CustomEvent('batch-download-start', {
          detail: {
            modelId: props.modelId,
            resourceType: props.resourceType,
            filename: `${props.resourceType}_${arrangeName}.zip`,
            session: sessionData,
            api: {
              init: () => Promise.resolve(),
              chunk: (mid: string, rt: string, sid: string, idx: number, signal?: AbortSignal) =>
                props.downloadApi.chunk(mid, rt, sid, idx, signal),
              cleanup: (mid: string, rt: string, sid: string) =>
                props.downloadApi.cleanup(mid, rt, sid),
            },
          }
        }))

        // 3. 等待下载完成
        const finished = await waitForComplete()
        if (!finished) {
          throw new Error('下载超时')
        }

        // 4. 清理 session
        await props.downloadApi.cleanup(props.modelId, props.resourceType, sessionData.session_id)

        // 5. 标记完成
        if (state.status === 'complete') {
          itemStatuses.value[arrangeName] = 'complete'
        } else {
          itemStatuses.value[arrangeName] = 'error'
          throw new Error(state.status === 'cancelled' ? '已取消' : '下载失败')
        }

        // 6. 清理 + 等弹窗关闭
        resetManager()
        await new Promise<void>((resolve) => {
          downloadDialogClosedResolver = () => resolve()
          // 3秒超时兜底
          setTimeout(resolve, 3000)
        })
      } catch (e: any) {
        const msg = e?.response?.data?.detail || e?.message || '下载失败'
        itemStatuses.value[arrangeName] = 'error'
        if (state.status === 'downloading' || state.status === 'paused') {
          cancelDownloadMgr()
        }
        ElMessage.error(`批次 ${arrangeName} 下载失败: ${msg}`)
        // 清理 + 兜底等弹窗关闭
        resetManager()
        await new Promise<void>((resolve) => {
          downloadDialogClosedResolver = () => resolve()
          setTimeout(resolve, 3000)
        })
      }
    }
  } finally {
    downloading.value = false
    emit('allDone')
  }
}

function cancelDownload() {
  cancelDownloadMgr()
  downloading.value = false
  // 关闭进度弹窗
  window.dispatchEvent(new CustomEvent('batch-download-cancel'))
  ElMessage.info('已取消下载')
}

function handleClose() {
  cancelDownloadMgr()
  downloading.value = false
  itemStatuses.value = {}
}

function openDialog() {
  visible.value = true
  downloading.value = false
  itemStatuses.value = {}
  nextTick(() => {
    const wrapper = document.querySelector('.arrange-list-wrapper') as HTMLElement
    if (wrapper) {
      listMaxHeight.value = Math.min(360, props.arrangeNames.length * 44 + 20)
    }
  })
}

defineExpose({ openDialog })
</script>

<style scoped lang="scss">
.batch-download {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.arrange-list-wrapper {
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 8px;
  background: var(--bg-card);

  .arrange-item {
    padding: 4px 0;

    .status-tag {
      margin-left: 8px;
      font-size: 12px;
      &.downloading { color: #409eff; }
      &.done { color: #67c23a; }
      &.error { color: #f56c6c; }
    }
  }
}

.batch-summary {
  .summary-text {
    text-align: center;
    font-size: 13px;
    color: #909399;
    margin-top: 8px;
  }
}

.batch-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>
