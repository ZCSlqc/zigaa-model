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

    <!-- 模式组 -->
    <div class="toolbar-group">
      <el-button
        size="small"
        :class="{ active: mode === 'draw' }"
        text
        @click="setMode('draw')"
      >
        绘制轮廓
      </el-button>
      <el-button
        size="small"
        :class="{ active: mode === 'select' }"
        text
        @click="setMode('select')"
      >
        编辑/选择
      </el-button>
    </div>

    <div class="toolbar-sep"></div>

    <!-- 操作组 -->
    <div class="toolbar-group">
      <el-button
        size="small"
        class="btn-save"
        text
        :disabled="!hasPolygons"
        :loading="loadingSave"
        @click="emit('save')"
      >
        保存标注
      </el-button>
      <el-button
        size="small"
        class="btn-delete"
        text
        :disabled="!hasPolygons"
        @click="confirmDeleteAll"
      >
        删除标注
      </el-button>
      <el-button
        size="small"
        class="btn-reset"
        text
        :disabled="!hasChanges"
        :loading="loadingReset"
        @click="emit('resetAnnotation')"
      >
        撤销标注
      </el-button>
    </div>

    <div class="toolbar-sep"></div>

    <!-- 图片操作 -->
    <div v-if="hasImage" class="toolbar-group">
      <el-button
        size="small"
        class="btn-download"
        :loading="loadingDownloadImage"
        @click="emit('downloadImage')"
      >
        下载图片
      </el-button>
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

    <!-- 辅助 -->
    <div class="toolbar-group">
      <el-button
        size="small"
        :class="{ active: showLabels }"
        text
        @click="emit('toggleLabels')"
      >
        {{ showLabels ? "隐藏标签" : "显示标签" }}
      </el-button>
      <el-button
        size="small"
        :class="{ active: showEdges }"
        text
        class="btn-edges"
        @click="emit('toggleEdges')"
      >
        {{ showEdges ? "隐藏轮廓" : "显示轮廓" }}
      </el-button>
    </div>

    <div class="toolbar-sep"></div>

    <!-- 分类组 -->
    <div class="toolbar-group resource-toggle">
      <el-button
        size="small"
        :class="{ active: resourceType === 'good' }"
        text
        class="resource-btn-good"
        @click="emit('switchResource', 'good')"
      >
        良品
      </el-button>
      <el-button
        size="small"
        :class="{ active: resourceType === 'defect' }"
        text
        class="resource-btn-defect"
        @click="emit('switchResource', 'defect')"
      >
        缺陷
      </el-button>
    </div>
  </div>

  <!-- 操作提示 -->
  <div class="toolbar-hints">
    <template v-if="mode === 'draw'">
      <span class="hint-item"><kbd>Ctrl+S</kbd> 保存</span>
      <span class="hint-sep">·</span>
      <span class="hint-item"><kbd>Tab</kbd> 编辑/选择</span>
      <span class="hint-sep">·</span>
      <span class="hint-item"><kbd>←</kbd><kbd>→</kbd> 切换图片</span>
      <span class="hint-sep">·</span>
      <span class="hint-item"><kbd>右键</kbd> 平移画布</span>
      <span class="hint-sep">·</span>
      <span class="hint-item"><kbd>Ctrl+Z</kbd> 取消绘制</span>
      <span class="hint-sep">·</span>
      <span class="hint-item"><kbd>Space</kbd> 撤销点</span>
      <span class="hint-sep">·</span>
      <span class="hint-item"><kbd>左键上个点</kbd> 撤销点</span>
      <span class="hint-sep">·</span>
      <span class="hint-item"><kbd>左键首个点</kbd> 闭合</span>
      <span class="hint-sep">·</span>
      <span class="hint-item"><kbd>左键点击/长按</kbd> 绘制线</span>
    </template>
    <template v-else>
      <span class="hint-item"><kbd>Ctrl+S</kbd> 保存</span>
      <span class="hint-sep">·</span>
      <span class="hint-item"><kbd>Tab</kbd> 绘制轮廓</span>
      <span class="hint-sep">·</span>
      <span class="hint-item"><kbd>←</kbd><kbd>→</kbd> 切换图片</span>
      <span class="hint-sep">·</span>
      <span class="hint-item"><kbd>右键</kbd> 平移画布</span>
      <span class="hint-sep">·</span>
      <span class="hint-item"><kbd>左键标签</kbd> 改标签</span>
      <span class="hint-sep">·</span>
      <span class="hint-item"><kbd>左键红点</kbd> 删标注</span>
      <span class="hint-sep">·</span>
      <span class="hint-item"><kbd>左键蓝点</kbd> 拖拽点</span>
      <span class="hint-sep">·</span>
      <span class="hint-item"><kbd>Shift</kbd><kbd>左键蓝点</kbd> 删除点</span>
      <span class="hint-sep">·</span>
      <span class="hint-item"><kbd>左键蓝边</kbd> 添加点</span>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ElMessageBox } from "element-plus";
import { ArrowLeft } from "@element-plus/icons-vue";

const props = defineProps<{
  mode: string;
  hasPolygons: boolean;
  hasChanges: boolean;
  resourceType: "good" | "defect";
  showLabels: boolean;
  showEdges: boolean;
  hasImage: boolean;
  imageName?: string;
  loadingSave?: boolean;
  loadingReset?: boolean;
  loadingDeleteImage?: boolean;
  loadingDownloadImage?: boolean;
}>();

const emit = defineEmits<{
  back: [];
  setMode: [mode: string];
  deleteAll: [];
  resetAnnotation: [];
  save: [];
  switchResource: [type: "good" | "defect"];
  toggleLabels: [];
  toggleEdges: [];
  deleteImage: [];
  downloadImage: [];
}>();

function setMode(m: string) {
  emit("setMode", m);
}

async function confirmDeleteAll() {
  try {
    await ElMessageBox.confirm(
      "确定要删除当前图片的所有标注吗？",
      "确认删除标注",
      {
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
    emit("deleteAll");
  } catch {
    // cancelled
  }
}

async function confirmDeleteImage() {
  try {
    await ElMessageBox.confirm(
      `确定要删除图片"${props.imageName}"吗？此操作将删除原图、压缩图和标注。`,
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
  box-shadow: var(--shadow-sm);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-md);
  flex-wrap: wrap;
}

.hint-item {
  white-space: nowrap;
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

.toolbar-group .el-button.active {
  background: #409eff;
  border-color: #409eff;
  color: #fff;
  z-index: 1;
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

.toolbar-group .resource-btn-good.active {
  background: #67c23a !important;
  border-color: #67c23a !important;
  color: #fff !important;

  &:hover {
    background: #85ce61 !important;
    border-color: #85ce61 !important;
  }
}

.toolbar-group .resource-btn-defect.active {
  background: #f56c6c !important;
  border-color: #f56c6c !important;
  color: #fff !important;

  &:hover {
    background: #f78989 !important;
    border-color: #f78989 !important;
  }
}


.btn-save {
  color: #67c23a !important;
  &:disabled {
    opacity: 0.5 !important;
    pointer-events: none !important;
  }
}

.btn-delete {
  color: #f56c6c !important;
  &:disabled {
    opacity: 0.5 !important;
    pointer-events: none !important;
  }
}

.btn-reset {
  color: #409eff !important;
  &:disabled {
    opacity: 0.5 !important;
    pointer-events: none !important;
  }
}

.btn-download {
  background: #67c23a !important;
  color: #fff !important;
  border-color: #67c23a !important;

  &:hover {
    background: #85ce61 !important;
    border-color: #85ce61 !important;
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

.btn-edges.active {
  background: #e6a23c !important;
  border-color: #e6a23c !important;
  color: #fff !important;

  &:hover {
    background: #ebb563 !important;
    border-color: #ebb563 !important;
  }
}
</style>
