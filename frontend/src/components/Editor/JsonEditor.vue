<template>
  <el-dialog v-model="visible" :title="title" width="700px" @close="onClose">
    <div class="json-editor-wrap">
      <div ref="editorRef" class="json-editor"></div>
      <div v-if="parseError" class="parse-error">
        <el-alert :title="parseError" type="error" :closable="false" show-icon />
      </div>
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import { EditorView, basicSetup } from 'codemirror'
import { json } from '@codemirror/lang-json'

const props = defineProps<{
  modelValue: boolean
  title?: string
  initialContent?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  save: [content: string]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const editorRef = ref<HTMLDivElement>()
const parseError = ref('')
let editorView: EditorView | null = null

watch(visible, (v) => {
  if (v) {
    nextTick(() => {
      initEditor()
    })
  }
})

function initEditor() {
  if (!editorRef.value) return
  if (editorView) editorView.destroy()
  parseError.value = ''

  const content = props.initialContent || ''
  editorView = new EditorView({
    doc: content,
    extensions: [
      basicSetup,
      json(),
      EditorView.theme({
        '&': { height: '400px', fontSize: '14px', borderRadius: '4px' },
        '&.cm-focused': { outline: 'none' },
        '.cm-scroller': { fontFamily: 'monospace' },
      }),
    ],
    parent: editorRef.value,
  })
}

function getEditorContent(): string {
  return editorView?.state.doc.toString() ?? ''
}

function handleSave() {
  const content = getEditorContent().trim()
  // 空内容 = 删除文件
  if (!content) {
    emit('save', '')
    return
  }
  // 语法校验
  try {
    JSON.parse(content)
  } catch (e: any) {
    parseError.value = `JSON 语法错误：${e.message}`
    return
  }
  parseError.value = ''
  emit('save', content)
}

function onClose() {
  if (editorView) {
    editorView.destroy()
    editorView = null
  }
  parseError.value = ''
}
</script>

<style scoped lang="scss">
.json-editor-wrap {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.json-editor {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.parse-error {
  margin-top: var(--spacing-xs);
}
</style>
