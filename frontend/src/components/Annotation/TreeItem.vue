<template>
  <div class="tree-item">
    <div
      v-if="isFolder"
      @click="toggleFolder"
    >
      <span class="icon">
        <el-icon v-if="expanded"><ArrowDown /></el-icon>
        <el-icon v-else><ArrowRight /></el-icon>
      </span>
      <el-icon class="folder-icon"><Folder /></el-icon>
      <span class="label">{{ node.name }}</span>
      <el-icon class="delete-folder-icon" @click.stop="emit('deleteFolder', (node as TreeFolder).path)">
        <Delete />
      </el-icon>
    </div>

    <div
      v-else
      :class="['tree-file', { selected: selectedPath === fileNode?.path }]"
      @click="$emit('selectImage', node as any)"
    >
      <el-icon class="file-icon"><Picture /></el-icon>
      <span class="label">{{ node.name }}</span>
      <el-tag v-if="fileNode?.has_annotation && !fileNode?.error" size="small" type="success" class="ann-tag">✓</el-tag>
      <el-tooltip v-else-if="fileNode?.error" :content="tooltipContent" placement="top" :show-after="200" raw-content>
        <span :class="['status-dot', errorLevel <= 5 ? 'dot-error' : 'dot-warn']"></span>
      </el-tooltip>
    </div>

    <div v-if="isFile && fileNode" class="tree-thumb">
      <img
        :src="store.getCompressPathByImage(fileNode)"
        :alt="fileNode.name"
        class="thumb-img"
        @click.stop="$emit('selectImage', fileNode)"
        loading="lazy"
      />
    </div>

    <div v-if="isFolder && expanded" class="tree-children">
      <TreeItem
        v-for="child in folderNode!.children"
        :key="child.name"
        :node="child"
        :expanded-folders="expandedFolders"
        :selected-path="selectedPath"
        @toggle-folder="$emit('toggleFolder', $event)"
        @select-image="$emit('selectImage', $event)"
        @delete-folder="$emit('deleteFolder', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ArrowRight, ArrowDown, Folder, Picture, Delete } from '@element-plus/icons-vue'
import type { TreeNode, TreeFolder, TreeFile } from '../../stores/annotation'
import { useAnnotationStore } from '../../stores/annotation'

const store = useAnnotationStore()

const props = defineProps<{
  node: TreeNode
  expandedFolders: Set<string>
  selectedPath: string | undefined
}>()

const emit = defineEmits<{
  toggleFolder: [path: string]
  selectImage: [img: TreeFile]
  deleteFolder: [path: string]
}>()

const isFolder = computed(() => 'children' in props.node)
const isFile = computed(() => !isFolder.value)
const folderNode = computed(() => isFolder.value ? (props.node as TreeFolder) : null)
const fileNode = computed(() => isFile.value ? (props.node as TreeFile) : null)
const expanded = computed(() => {
  if (isFolder.value) return props.expandedFolders.has((props.node as TreeFolder).path)
  return false
})
const errorLevel = computed(() => fileNode.value?.error_level ?? 0)

const tooltipContent = computed(() => {
  if (!fileNode.value?.error) return ''
  const fix = '解决办法：绘制轮廓 → 编辑/选择 → 保存标注'
  return `<div style="line-height:1.6">
    <div>${fileNode.value.error}</div>
    <div style="color:#909399;margin-top:4px;font-size:12px">${fix}</div>
  </div>`
})

function toggleFolder() {
  emit('toggleFolder', (props.node as TreeFolder).path)
}
</script>

<style scoped lang="scss">
.tree-item {
  user-select: none;
}

.tree-children {
  padding-left: 16px;
}

.tree-file {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px var(--spacing-xs);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 12px;
  overflow: hidden;

  .file-icon {
    font-size: 14px;
    color: var(--color-primary);
    flex-shrink: 0;
  }

  .label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
  }

  .ann-tag {
    flex-shrink: 0;
    font-size: 10px;
    padding: 0 4px;
    line-height: 18px;
  }

  .status-dot {
    flex-shrink: 0;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    cursor: pointer;
  }

  .dot-error {
    background: #f56c6c;
  }

  .dot-warn {
    background: #fadb14;
  }

  &:hover {
    background: var(--bg-hover);
  }

  &.selected {
    background: var(--color-primary);
    color: #fff;

    .file-icon {
      color: #fff;
    }
  }
}

.tree-thumb {
  padding: 2px var(--spacing-xs) 4px;
  width: fit-content;
}

.thumb-img {
  width: 120px;
  height: auto;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-light);
  cursor: pointer;
  object-fit: cover;
  transition: opacity 0.15s;

  &:hover {
    opacity: 0.8;
  }
}

.icon {
  display: inline-flex;
  align-items: center;
  width: 16px;
  font-size: 10px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.folder-icon {
  font-size: 14px;
  color: #e6a23c;
  flex-shrink: 0;
}

.label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  font-size: 13px;
}

.delete-folder-icon {
  font-size: 14px;
  color: var(--text-secondary);
  cursor: pointer;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s;

  &:hover {
    color: #f56c6c;
  }
}

.tree-item > div:first-child:hover .delete-folder-icon {
  opacity: 1;
}
</style>
