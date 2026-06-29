<template>
  <div class="tree-item">
    <div
      v-if="isFolder"
      :class="['tree-folder', { selected: folderSelected }]"
      @click="toggleFolder"
    >
      <span class="icon">
        <el-icon v-if="expanded"><ArrowDown /></el-icon>
        <el-icon v-else><ArrowRight /></el-icon>
      </span>
      <el-icon class="folder-icon"><Folder /></el-icon>
      <span class="label">{{ node.name }}</span>
      <el-icon class="download-folder-icon" @click.stop="emit('downloadFolder', (node as TreeFolder).path)">
        <Download />
      </el-icon>
      <el-icon class="delete-folder-icon" @click.stop="emit('deleteFolder', (node as TreeFolder).path)">
        <Delete />
      </el-icon>
    </div>

    <div
      v-else
      :class="['tree-file', { selected: selectedPath === fileNode?.path }]"
      @click="$emit('selectImage', node as any)"
      @contextmenu.prevent="$emit('showCategoryMenu', { node: $event, path: fileNode?.rel_path || '' })"
    >
      <el-icon class="file-icon"><Picture /></el-icon>
      <span class="label">{{ node.name }}</span>
      <el-tag v-if="fileNode?.category === 'undone'" size="small" type="warning" class="cat-tag">未标完</el-tag>
      <el-tag v-else-if="fileNode?.category === 'pending'" size="small" type="primary" class="cat-tag">待确认</el-tag>
      <el-tag v-if="fileNode?.has_annotation && !fileNode?.error" size="small" type="success" class="ann-tag">✓</el-tag>
      <el-tooltip v-else-if="fileNode?.error" :content="tooltipContent" placement="top" :show-after="200" raw-content>
        <span :class="['status-dot', errorLevel <= 5 ? 'dot-error' : 'dot-warn']"></span>
      </el-tooltip>
    </div>

    <div v-if="isFile && fileNode && thumbVisible" class="tree-thumb">
      <img
        :src="store.getCompressPathByImage(fileNode)"
        :alt="fileNode.name"
        :class="['thumb-img', { active: props.selectedPath === fileNode.path }]"
        @click.stop="$emit('selectImage', fileNode)"
      />
    </div>

    <div v-if="isFolder && expanded" class="tree-children">
      <TreeItem
        v-for="child in folderNode!.children"
        :key="child.path"
        :node="child"
        :expanded-folders="expandedFolders"
        :selected-path="selectedPath"
        @toggle-folder="$emit('toggleFolder', $event)"
        @select-image="$emit('selectImage', $event)"
        @download-folder="$emit('downloadFolder', $event)"
        @delete-folder="$emit('deleteFolder', $event)"
        @show-category-menu="$emit('showCategoryMenu', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ArrowRight, ArrowDown, Folder, Picture, Delete, Download } from '@element-plus/icons-vue'
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
  downloadFolder: [path: string]
  deleteFolder: [path: string]
  showCategoryMenu: [data: { node: MouseEvent; path: string }]
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

// Thumbnails: only show when path is in cache
const thumbVisible = computed(() => {
  if (!isFile.value || !fileNode.value) return false
  return store.thumbsIncludePath(fileNode.value.path)
})

/** "Bubble-up" highlight from the timestamp folder outward.
 *
 *  Tree structure (example):
 *    good (injected root) → original (injected) → 20260612_112342 (timestamp)
 *        → category/ → subfolder/ → img.jpg
 *
 *  Rule: starting from the timestamp folder, walk inward along the
 *  selected-path. The first *collapsed* folder gets the blue highlight.
 *  If all folders from timestamp to file are expanded, highlight the
 *  file itself.
 *  Good/Original are always ignored (they are code-injected, never
 *  user-toggleable). */
const folderSelected = computed(() => {
  if (!props.selectedPath || !isFolder.value) return false
  const folderPath = (props.node as TreeFolder).path
  if (!props.selectedPath.startsWith(folderPath + '/')) return false

  // Must be inside the timestamp-folder chain: walk the image segments,
  // find which segment is the timestamp folder (matches YYYYMMDD_HHMMSS).
  const imageSegments = props.selectedPath.split('/')

  // Find the index of the timestamp folder segment in the image path.
  // We scan all segments and use a regex to detect it.
  const tsRegex = /^\d{8}_\d{6}$/
  let tsSegmentIndex = -1
  for (let i = 0; i < imageSegments.length; i++) {
    if (tsRegex.test(imageSegments[i])) {
      tsSegmentIndex = i
      break
    }
  }

  // If no timestamp folder found in path, fallback to old behavior
  if (tsSegmentIndex === -1) {
    const result = computeFolderSelected(folderPath, imageSegments)
    return result
  }

  // Now our folder is a candidate only if it starts at or after tsSegmentIndex.
  // Our depth in segments.
  const myDepth = folderPath.split('/').length
  const mySegmentIndex = myDepth - 1

  // If we're NOT at or below the timestamp folder, we're good/original → never selected
  if (mySegmentIndex < tsSegmentIndex) return false

  // Check all folders from timestamp down to (but not including) the image file.
  // Find the first COLLAPSED folder. If WE are that first collapsed one, highlight us.
  // firstCollapsedDepth is the segment INDEX (0-based) of the first collapsed folder.
  let firstCollapsedIdx = -1
  for (let i = tsSegmentIndex; i < imageSegments.length - 1; i++) {
    const segPath = imageSegments.slice(0, i + 1).join('/')
    if (!props.expandedFolders.has(segPath)) {
      firstCollapsedIdx = i
      break
    }
  }

  // If no collapsed folder was found at all, highlight the file instead
  if (firstCollapsedIdx === -1) return false

  return mySegmentIndex === firstCollapsedIdx
})

function computeFolderSelected(folderPath: string, imageSegments: string[]): boolean {
  // Fallback: old behavior when no timestamp folder found.
  const myIdx = folderPath.split('/').length - 1
  let firstCollapsedIdx = -1
  for (let i = 0; i < imageSegments.length - 1; i++) {
    const segPath = imageSegments.slice(0, i + 1).join('/')
    if (!props.expandedFolders.has(segPath)) {
      firstCollapsedIdx = i
      break
    }
  }
  if (firstCollapsedIdx === -1) return false
  return myIdx === firstCollapsedIdx
}

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

.tree-folder {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px var(--spacing-xs);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 12px;
  overflow: hidden;
  user-select: none;

  &:hover {
    background: var(--bg-hover);
  }

  &.selected {
    background: var(--color-primary);
    color: #fff;

    .folder-icon {
      color: #fff;
    }

    .label {
      color: #fff;
    }

    .icon {
      color: #fff;
    }

    .download-folder-icon,
    .delete-folder-icon {
      color: #fff;
      opacity: 0;
      transition: opacity 0.15s;
    }
  }
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

  .cat-tag {
    flex-shrink: 0;
    font-size: 9px;
    padding: 0 3px;
    line-height: 16px;
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

/* intentionally left empty — styles moved above for flex layout */

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

  &.active {
    border-color: var(--color-primary);
    box-shadow: 0 0 0 2px var(--color-primary-light);
  }
}

.tree-thumb {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 4px var(--spacing-xs) 8px;
  width: fit-content;
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

.download-folder-icon {
  font-size: 14px;
  color: #67c23a;
  cursor: pointer;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s;

  &:hover {
    color: #85ce61;
  }
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

.tree-item > div:first-child:hover .download-folder-icon,
.tree-item > div:first-child:hover .delete-folder-icon {
  opacity: 1;
}
</style>
