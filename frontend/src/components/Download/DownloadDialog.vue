<template>
  <el-dialog
    v-model="visible"
    :title="state.filename || '下载文件'"
    width="520px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    destroy-on-close
    @close="handleClose"
  >
    <div class="download-progress">
      <el-progress
        :percentage="Math.round(state.percentage)"
        :stroke-width="8"
        :status="state.status === 'error' ? 'exception' : undefined"
      />
      <div class="download-info">
        <div class="info-row">
          <span class="label">文件</span>
          <span class="value">{{ state.filename }}</span>
        </div>
        <div class="info-row">
          <span class="label">大小</span>
          <span class="value">{{ formatSize(state.totalSize) }}</span>
        </div>
        <div class="info-row">
          <span class="label">已下载</span>
          <span class="value">{{ formatSize(state.downloaded) }} / {{ formatSize(state.totalSize) }}</span>
        </div>
        <div class="info-row" v-if="state.speed > 0">
          <span class="label">速度</span>
          <span class="value">{{ (state.speed / 1024 / 1024).toFixed(1) }} MB/s</span>
        </div>
        <div class="info-row" v-if="state.eta > 0 && (state.status === 'downloading' || state.status === 'assembling')">
          <span class="label">预计剩余</span>
          <span class="value">{{ etaText }}</span>
        </div>
        <div class="info-row" v-if="state.status === 'init'">
          <span class="label">状态</span>
          <span class="value">正在准备...</span>
        </div>
        <div class="info-row" v-if="state.status === 'assembling'">
          <span class="label">状态</span>
          <span class="value">正在组装文件...</span>
        </div>
        <div class="info-row" v-if="state.error">
          <span class="label">错误</span>
          <span class="value error">{{ state.error }}</span>
        </div>
      </div>
    </div>
    <template #footer>
      <el-button
        v-if="state.status === 'downloading' || state.status === 'init'"
        @click="handleCancel"
      >
        取消
      </el-button>
      <el-button v-else @click="handleClose">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useDownloadManager, type DownloadSessionData } from '../../composables/useDownloadManager'
import type { DownloadConfig } from '../../composables/useDownloadManager'

const { state, start, startWithSession, cancel, reset, formatSize } = useDownloadManager()
const visible = ref(false)

const etaText = computed(() => {
  const secs = state.eta
  const mins = Math.floor(secs / 60)
  const s = secs % 60
  return `${mins}分${s}秒`
})

function openDownload(config: DownloadConfig) {
  visible.value = true
  start(config)
}

function openDownloadWithSession(config: DownloadConfig, sessionData: DownloadSessionData) {
  visible.value = true
  startWithSession(config, sessionData)
}

async function handleCancel() {
  await cancel()
}

function handleClose() {
  visible.value = false
  reset()
}

defineExpose({ openDownload, openDownloadWithSession })
</script>

<style scoped lang="scss">
.download-progress {
  padding: 8px 0;
}

.download-info {
  margin-top: 20px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 14px;
  border-bottom: 1px solid var(--border-light);

  &:last-child {
    border-bottom: none;
  }
}

.label {
  color: var(--text-secondary);
}

.value {
  color: var(--text-regular);
  font-family: 'Courier New', monospace;
}

.value.error {
  color: #f56c6c;
  font-family: inherit;
}
</style>
