<template>
  <div class="json-upload" :class="{ dragging }">
    <input
      ref="inputRef"
      type="file"
      accept=".json"
      style="display: none"
      @change="handleFileSelect"
    />
    <div class="upload-area" @click="triggerSelect" @drop.prevent="handleDrop" @dragover.prevent="dragging = true" @dragleave.prevent="dragging = false">
      <template v-if="!uploading">
        <el-icon class="upload-icon"><Document /></el-icon>
        <p class="upload-text">{{ dragging ? '释放上传 JSON' : '点击或拖拽 JSON 文件到此处' }}</p>
      </template>
      <template v-else>
        <el-progress type="circle" :percentage="100" :stroke-width="6" :indeterminate="true" />
        <p class="upload-text">上传中...</p>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Document } from '@element-plus/icons-vue'
import { uploadParameter } from '../../api/resource'

const props = defineProps<{
  modelId: string
}>()

const emit = defineEmits<{
  uploaded: []
}>()

const inputRef = ref<HTMLInputElement>()
const dragging = ref(false)
const uploading = ref(false)

function triggerSelect() {
  inputRef.value?.click()
}

function handleFileSelect(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) doUpload(file)
}

function handleDrop(e: DragEvent) {
  dragging.value = false
  const file = e.dataTransfer?.files[0]
  if (file) doUpload(file)
}

async function doUpload(file: File) {
  if (!file.name.toLowerCase().endsWith('.json')) {
    ElMessage.warning('请选择 JSON 文件')
    return
  }
  uploading.value = true
  try {
    await uploadParameter(props.modelId, file)
    ElMessage.success('模型参数上传成功')
    emit('uploaded')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
    if (inputRef.value) inputRef.value.value = ''
  }
}
</script>

<style scoped lang="scss">
.json-upload.dragging .upload-area {
  border-color: var(--color-primary);
  background: rgba(64, 158, 255, 0.05);
}

.upload-area {
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-md);
  padding: 32px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    border-color: var(--color-primary);
  }
}

.upload-icon {
  font-size: 40px;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-sm);
}

.upload-text {
  font-size: 14px;
  color: var(--text-regular);
  margin: 0;
}
</style>
