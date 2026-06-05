<template>
  <div class="toolbar">
    <!-- 返回 -->
    <div class="toolbar-group">
      <el-button size="small" text @click="emit('back')">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
    </div>

    <div class="toolbar-sep"></div>

    <!-- 删除图片 -->
    <div v-if="hasImage" class="toolbar-group">
      <el-button
        size="small"
        class="btn-delete-img"
        text
        :loading="loadingDeleteImage"
        @click="confirmDeleteImage"
      >
        删除图片
      </el-button>
    </div>

    <div class="toolbar-spacer"></div>

    <!-- 分类组 -->
    <div class="toolbar-group resource-toggle">
      <el-button
        size="small"
        :class="{ active: resourceType === 'test' }"
        text
        class="resource-btn-test"
        @click="emit('switchResource', 'test')"
      >
        测试
      </el-button>
      <el-button
        size="small"
        :class="{ active: resourceType === 'template' }"
        text
        class="resource-btn-template"
        @click="emit('switchResource', 'template')"
      >
        模板
      </el-button>
    </div>
  </div>

  <!-- 操作提示 -->
  <div class="toolbar-hints">
    <span class="hint-item"><kbd>←</kbd><kbd>→</kbd> 切换图片</span>
    <span class="hint-sep">·</span>
    <span class="hint-item"><kbd>右键</kbd> 平移画布</span>
  </div>
</template>

<script setup lang="ts">
import { ElMessageBox } from "element-plus";
import { ArrowLeft } from "@element-plus/icons-vue";

const props = defineProps<{
  resourceType: "test" | "template";
  hasImage: boolean;
  imageName?: string;
  loadingDeleteImage?: boolean;
}>();

const emit = defineEmits<{
  back: [];
  switchResource: [type: "test" | "template"];
  deleteImage: [];
}>();

async function confirmDeleteImage() {
  try {
    await ElMessageBox.confirm(
      `确定要删除图片"${props.imageName}"吗？此操作将删除原图、压缩图。`,
      "确认删除图片",
      {
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
    emit("deleteImage");
  } catch {
    // cancelled
  }
}
</script>

<style scoped lang="scss">
.toolbar {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-card);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  box-shadow: var(--shadow-sm);
  margin-bottom: 0;
}

.toolbar-hints {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-md);
  background: var(--bg-card);
  border-radius: 0 0 var(--radius-md) var(--radius-md);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-md);
  flex-wrap: wrap;
}

.hint-item kbd {
  display: inline-block;
  padding: 0 4px;
  margin: 0 2px;
  font-size: 11px;
  font-family: inherit;
  background: var(--bg-hover);
  border: 1px solid var(--border-light);
  border-radius: 3px;
  color: var(--text-regular);
}

.hint-sep {
  color: var(--border-color);
  user-select: none;
}

.toolbar-group {
  display: flex;
  gap: 0;
}

.toolbar-group .el-button {
  border-radius: 0;
  border: 1px solid var(--border-light, #dcdfe6);
  margin-right: -1px;
}

.toolbar-group .el-button:first-child {
  border-radius: var(--radius-sm, 4px) 0 0 var(--radius-sm, 4px);
}

.toolbar-group .el-button:last-child {
  border-radius: 0 var(--radius-sm, 4px) var(--radius-sm, 4px) 0;
}

.toolbar-group .el-button:first-child:last-child {
  border-radius: var(--radius-sm, 4px);
}

.toolbar-sep {
  width: 1px;
  height: 20px;
  background: var(--border-light, #dcdfe6);
  margin: 0 var(--spacing-xs, 4px);
}

.toolbar-spacer {
  flex: 1;
}

.resource-toggle .el-button {
  border: 1px solid var(--border-light, #dcdfe6);
}

.toolbar-group .resource-btn-test.active {
  background: #e6a23c !important;
  border-color: #e6a23c !important;
  color: #fff !important;

  &:hover {
    background: #ebb563 !important;
    border-color: #ebb563 !important;
  }
}

.toolbar-group .resource-btn-template.active {
  background: #e6a23c !important;
  border-color: #e6a23c !important;
  color: #fff !important;

  &:hover {
    background: #ebb563 !important;
    border-color: #ebb563 !important;
  }
}

.btn-delete-img {
  background: #f56c6c !important;
  color: #fff !important;
  border-color: #f56c6c !important;

  &:hover {
    background: #f78989 !important;
    border-color: #f78989 !important;
  }
}
</style>
