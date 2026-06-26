<template>
  <AppLayout>
    <div class="project-page">
      <aside class="project-sidebar">
        <div class="sidebar-header">
          <h3>项目列表</h3>
          <el-button type="primary" size="small" @click="showCreateProject = true">
            新建项目
          </el-button>
        </div>
        <div class="project-list">
          <div
            v-for="p in store.projects"
            :key="p.id"
            :class="['project-item', { active: store.currentProjectId === p.id }]"
            @click="store.selectProject(p.id)"
          >
            <div class="project-item-name">{{ p.name }}</div>
            <div class="project-item-meta">
              {{ p.models[0]?.count || 0 }} 个模型
            </div>
            <div class="project-item-actions">
              <el-button
                size="small"
                class="btn-edit"
                @click.stop="showEditProject(p)"
              >
                编辑
              </el-button>
              <el-button
                size="small"
                class="btn-delete"
                :loading="isLoading('delete-project-' + p.id)"
                @click.stop="confirmDeleteProject(p)"
              >
                删除
              </el-button>
            </div>
          </div>
          <div v-if="store.projects.length === 0" class="empty-hint">
            暂无项目，点击"新建项目"开始
          </div>
        </div>
      </aside>

      <section class="project-main">
        <div v-if="!store.currentProjectId" class="select-hint">
          请选择或创建一个项目
        </div>
        <div v-else>
          <div class="model-header">
            <h3>模型</h3>
            <el-button type="primary" @click="showCreateModel = true">
              新建模型
            </el-button>
          </div>
          <div class="model-grid">
            <div
              v-for="m in store.models"
              :key="m.id"
              class="model-card"
              @click="onModelCardClick(m)"
            >
              <div class="model-card-header">
                <span class="model-name">{{ m.name }}</span>
                <el-tag size="small" :type="dataStatusTagType(ds(m))">{{ dataStatusDisplayText(ds(m)) }}</el-tag>
                <el-tag size="small" :type="trainingStatusTagType(ts(m))">{{ trainingStatusDisplayText(ts(m)) }}</el-tag>
                <el-tag size="small" :type="testStatusTagType(testSt(m))">{{ testStatusDisplayText(testSt(m)) }}</el-tag>
                <div class="model-card-actions-header">
                  <el-button
                    size="small"
                    class="btn-edit"
                    @click.stop="showEditModel(m)"
                  >
                    编辑
                  </el-button>
                  <el-button
                    size="small"
                    class="btn-delete"
                    :loading="isLoading('delete-model-' + m.id)"
                    @click.stop="confirmDeleteModel(m)"
                  >
                    删除
                  </el-button>
                </div>
              </div>
              <div class="model-card-desc">{{ m.description || '暂无描述' }}</div>
              <div class="model-card-actions" @click.stop>
                <el-button
                  size="small"
                  :type="ts(m) === 'training' ? 'danger' : 'primary'"
                  class="btn-solid"
                  :loading="isLoading('train-' + m.id)"
                  :disabled="hasLoading() && !isLoading('train-' + m.id)"
                  @click="handleTrainOrStop(m)"
                >
                  {{ trainButtonText(ts(m)) }}
                </el-button>
                <el-button
                  size="small"
                  :type="testSt(m) === 'generating' ? 'danger' : 'success'"
                  class="btn-solid"
                  :loading="isLoading('test-' + m.id)"
                  :disabled="hasLoading() && !isLoading('test-' + m.id)"
                  @click="handleTestOrStop(m)"
                >
                  {{ testButtonText(testSt(m)) }}
                </el-button>
                <el-button
                  size="small"
                  :loading="isLoading('logs-' + m.id)"
                  :disabled="hasLoading() && !isLoading('logs-' + m.id) || !isTrainingActive(ts(m))"
                  @click="handleCheckLogs(m)"
                >
                  训练日志
                </el-button>
                <el-button
                  size="small"
                  type="warning"
                  class="btn-solid"
                  :loading="isLoading('download-model-' + m.id)"
                  :disabled="hasLoading() && !isLoading('download-model-' + m.id) || !isTrainingSuccess(ts(m))"
                  @click="handleDownloadModel(m)"
                >
                  下载模型
                </el-button>
              </div>
            </div>
          </div>
          <div v-if="store.models.length === 0" class="empty-hint">
            暂无模型
          </div>
        </div>
      </section>
    </div>

    <!-- 新建项目对话框 -->
    <el-dialog v-model="showCreateProject" title="新建项目" width="400px">
      <el-form @submit.prevent="handleCreateProject">
        <el-form-item label="项目名称">
          <el-input v-model="newProjectName" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newProjectDesc" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateProject = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreateProject">创建</el-button>
      </template>
    </el-dialog>

    <!-- 新建模型对话框 -->
    <el-dialog v-model="showCreateModel" title="新建模型" width="400px">
      <el-form @submit.prevent="handleCreateModel">
        <el-form-item label="模型名称">
          <el-input v-model="newModelName" placeholder="请输入模型名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newModelDesc" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateModel = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreateModel">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑项目对话框 -->
    <el-dialog v-model="showEditProjectDialog" title="编辑项目" width="400px">
      <el-form @submit.prevent="handleEditProject">
        <el-form-item label="项目名称">
          <el-input v-model="editProjectName" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editProjectDesc" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditProjectDialog = false">取消</el-button>
        <el-button type="primary" :loading="editing" @click="handleEditProject">保存</el-button>
      </template>
    </el-dialog>

    <!-- 编辑模型对话框 -->
    <el-dialog v-model="showEditModelDialog" title="编辑模型" width="400px">
      <el-form @submit.prevent="handleEditModel">
        <el-form-item label="模型名称">
          <el-input v-model="editModelName" placeholder="请输入模型名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editModelDesc" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditModelDialog = false">取消</el-button>
        <el-button type="primary" :loading="editing" @click="handleEditModel">保存</el-button>
      </template>
    </el-dialog>

    <!-- 检查日志对话框 -->
    <el-dialog v-model="showLogsDialog" title="训练日志" width="700px">
      <pre class="logs-content">{{ logsContent || '暂无日志' }}</pre>
    </el-dialog>

    <DownloadDialog ref="downloadDialogRef" />

  </AppLayout>
</template>

<script setup lang="ts">
defineOptions({ name: 'Project' })
import { ref, onMounted, onActivated, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import AppLayout from '../components/Layout/AppLayout.vue'
import DownloadDialog from '../components/Download/DownloadDialog.vue'
import { useProjectStore } from '../stores/project'
import { useAuthStore } from '../stores/auth'
import { useDelayedLoading } from '../composables/useDelayedLoading'
import { resolveDataStatus, dataStatusTagType, dataStatusDisplayText, resolveTrainingStatus, trainingStatusTagType, trainingStatusDisplayText, isTraining, isTrainingSuccess, trainButtonText, resolveTestStatus, testStatusTagType, testStatusDisplayText, testButtonText } from '../utils/model-status'

const route = useRoute()
const router = useRouter()
const store = useProjectStore()
const authStore = useAuthStore()
const creating = ref(false)
const { startLoading, stopLoading, isLoading, hasLoading } = useDelayedLoading()
const downloadDialogRef = ref<InstanceType<typeof DownloadDialog>>()

const showCreateProject = ref(false)
const newProjectName = ref('')
const newProjectDesc = ref('')

const showCreateModel = ref(false)
const newModelName = ref('')
const newModelDesc = ref('')

// Logs dialog
const showLogsDialog = ref(false)
const logsContent = ref('')

// Edit state
const editing = ref(false)
const showEditProjectDialog = ref(false)
const editProjectId = ref('')
const editProjectName = ref('')
const editProjectDesc = ref('')
const showEditModelDialog = ref(false)
const editModelId = ref('')
const editModelName = ref('')
const editModelDesc = ref('')

function ds(m: any) {
  return resolveDataStatus(m.status)
}

function ts(m: any) {
  return resolveTrainingStatus(m.status)
}

function testSt(m: any) {
  return resolveTestStatus(m.status)
}

function isTrainingActive(status: string) {
  return isTraining(status) || isTrainingSuccess(status) || status === 'failure'
}

onMounted(async () => {
  await store.fetchProjects()
  const selectId = route.query.select as string
  if (selectId && store.projects.find(p => p.id === selectId)) {
    store.selectProject(selectId)
  }
  startPolling()
})

onActivated(async () => {
  await store.fetchProjects()
  if (store.currentProjectId && !store.projects.find(p => p.id === store.currentProjectId)) {
    store.currentProjectId = ''
    store.models = []
  } else if (store.currentProjectId) {
    await store.fetchModels(store.currentProjectId)
  }
  startPolling()
})

let pollTimer: any = null
function hasPending(): boolean {
  return store.models.some(m => ts(m) === 'training' || testSt(m) === 'generating')
}
async function refreshModels() {
  if (store.currentProjectId) {
    await store.fetchModels(store.currentProjectId)
  }
  startPolling()
}

function startPolling() {
  if (!hasPending()) {
    stopPolling()
    return
  }
  stopPolling()
  async function tick() {
    try {
      if (store.currentProjectId && hasPending()) {
        const pendingModels = store.models.filter(m => ts(m) === 'training' || testSt(m) === 'generating')
        await Promise.all(pendingModels.map(m => store.pollStatus(m.id)))
      }
      if (!hasPending()) {
        stopPolling()
        return
      }
    } finally {
      pollTimer = setTimeout(tick, Number(import.meta.env.VITE_POLL_INTERVAL) || 10000)
    }
  }
  tick()
}
function stopPolling() {
  if (pollTimer) { clearTimeout(pollTimer); pollTimer = null }
}

onUnmounted(() => {
  stopPolling()
})

async function handleCreateProject() {
  if (!newProjectName.value.trim()) {
    ElMessage.warning('请输入项目名称')
    return
  }
  creating.value = true
  try {
    await store.addProject(newProjectName.value.trim(), newProjectDesc.value.trim())
    showCreateProject.value = false
    newProjectName.value = ''
    newProjectDesc.value = ''
    ElMessage.success('项目创建成功')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

async function handleCreateModel() {
  if (!newModelName.value.trim()) {
    ElMessage.warning('请输入模型名称')
    return
  }
  creating.value = true
  try {
    await store.addModel(newModelName.value.trim(), newModelDesc.value.trim())
    showCreateModel.value = false
    newModelName.value = ''
    newModelDesc.value = ''
    ElMessage.success('模型创建成功')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

function showEditProject(p: any) {
  editProjectId.value = p.id
  editProjectName.value = p.name
  editProjectDesc.value = p.description || ''
  showEditProjectDialog.value = true
}

function showEditModel(m: any) {
  editModelId.value = m.id
  editModelName.value = m.name
  editModelDesc.value = m.description || ''
  showEditModelDialog.value = true
}

async function handleEditProject() {
  if (!editProjectName.value.trim()) {
    ElMessage.warning('请输入项目名称')
    return
  }
  editing.value = true
  try {
    await store.updateProject(editProjectId.value, editProjectName.value.trim(), editProjectDesc.value.trim())
    showEditProjectDialog.value = false
    ElMessage.success('项目更新成功')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '更新失败')
  } finally {
    editing.value = false
  }
}

async function handleEditModel() {
  if (!editModelName.value.trim()) {
    ElMessage.warning('请输入模型名称')
    return
  }
  editing.value = true
  try {
    await store.updateModel(editModelId.value, editModelName.value.trim(), editModelDesc.value.trim())
    showEditModelDialog.value = false
    ElMessage.success('模型更新成功')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '更新失败')
  } finally {
    editing.value = false
  }
}

async function confirmDeleteProject(p: any) {
  await ElMessageBox.confirm(`确定删除项目 "${p.name}" 及其所有模型？`, '确认删除', {
    type: 'warning',
  })
  startLoading('delete-project-' + p.id)
  try {
    await store.removeProject(p.id)
    ElMessage.success('项目已删除')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  } finally {
    stopLoading()
  }
}

async function confirmDeleteModel(m: any) {
  await ElMessageBox.confirm(`确定删除模型 "${m.name}"？`, '确认删除', {
    type: 'warning',
  })
  startLoading('delete-model-' + m.id)
  try {
    await store.removeModel(m.id)
    ElMessage.success('模型已删除')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  } finally {
    stopLoading()
  }
}

function onModelCardClick(m: any) {
  router.push(`/model/${m.id}`)
}

async function handleTrainOrStop(m: any) {
  const s = ts(m)
  if (s === 'training') {
    handleStopTraining(m)
  } else {
    handleTrainModel(m)
  }
}

async function handleTrainModel(m: any) {
  if (authStore.role === 'user') {
    ElMessage.warning('普通用户无权训练模型')
    return
  }
  if (ds(m) !== 'ready') {
    ElMessage.warning('数据不完整或有错误，请先完善数据')
    return
  }
  startLoading('train-' + m.id)
  try {
    await store.trainModel(m.id)
    ElMessage.success('训练已触发')
    refreshModels()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '训练触发失败')
  } finally {
    stopLoading()
  }
}

async function handleStopTraining(m: any) {
  await ElMessageBox.confirm(`确定终止模型 "${m.name}" 的训练？`, '确认终止', { type: 'warning' })
  startLoading('train-' + m.id)
  try {
    await store.stopTraining(m.id)
    ElMessage.success('训练已终止')
    refreshModels()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '终止失败')
  } finally {
    stopLoading()
  }
}

async function handleTestOrStop(m: any) {
  const s = testSt(m)
  if (s === 'generating') {
    await handleStopTest(m)
  } else {
    await handleRunTest(m)
  }
}

async function handleRunTest(m: any) {
  if (authStore.role === 'user') {
    ElMessage.warning('普通用户无权执行测试')
    return
  }
  if (ts(m) !== 'success') {
    ElMessage.warning('模型未训练成功，无法生成测试')
    return
  }
  startLoading('test-' + m.id)
  try {
    await store.runTest(m.id)
    ElMessage.success('测试生成已触发')
    refreshModels()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '测试生成失败')
  } finally {
    stopLoading()
  }
}

async function handleStopTest(m: any) {
  await ElMessageBox.confirm(`确定终止模型 "${m.name}" 的测试生成？`, '确认终止', { type: 'warning' })
  startLoading('test-' + m.id)
  try {
    await store.stopTest(m.id)
    ElMessage.success('测试已终止')
    refreshModels()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '终止失败')
  } finally {
    stopLoading()
  }
}

async function handleCheckLogs(m: any) {
  startLoading('logs-' + m.id)
  try {
    const res = await store.getLogs(m.id)
    logsContent.value = res.log
    showLogsDialog.value = true
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '获取日志失败')
  } finally {
    stopLoading()
  }
}

async function handleDownloadModel(m: any) {
  const { downloadModelInit, downloadModelChunk, downloadModelCleanup } = await import('../api/model')
  try {
    const initRes = await downloadModelInit(m.id)
    downloadDialogRef.value?.openDownloadWithSession(
      {
        modelId: m.id,
        resourceType: 'model',
        filename: 'model.zip',
        api: {
          init: () => Promise.resolve(),
          chunk: (mid: string, _rt: string, sid: string, idx: number, signal?: AbortSignal) => downloadModelChunk(mid, sid, idx, signal),
          cleanup: (mid: string, _rt: string, sid: string) => downloadModelCleanup(mid, sid),
        },
      },
      initRes.data,
    )
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '下载失败')
  }
}

</script>

<style scoped lang="scss">
.project-page {
  display: flex;
  height: 100%;
  gap: var(--spacing-lg);
}

.project-sidebar {
  width: 320px;
  flex-shrink: 0;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 88px);
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);

  h3 {
    margin: 0;
    font-size: 16px;
  }
}

.project-list {
  flex: 1;
  overflow-y: auto;
}

.project-item {
  padding: var(--spacing-sm) var(--spacing-sm);
  border-radius: var(--radius-sm);
  cursor: pointer;
  position: relative;
  margin-bottom: 4px;
  transition: background 0.2s;

  &:hover {
    background: var(--bg-hover);
  }

  &.active {
    background: var(--color-primary);
    color: #fff;

    .project-item-meta {
      color: rgba(255, 255, 255, 0.8);
    }
  }
}

.project-item-name {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 2px;
}

.project-item-meta {
  font-size: 12px;
  color: var(--text-secondary);
}

.project-item-actions {
  position: absolute;
  right: var(--spacing-sm);
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  gap: 0;
}

.btn-edit,
.btn-delete {
  color: #fff !important;
  padding: 0 var(--spacing-sm);
  height: 22px;
  line-height: 22px;
  font-size: 12px;
  border: none;

  &.is-disabled {
    color: #fff !important;
  }
}

.btn-edit {
  background: var(--color-success);

  &:hover {
    background: #85ce61;
  }

  border-radius: var(--radius-sm) 0 0 var(--radius-sm);
}

.btn-delete {
  background: var(--color-danger);

  &:hover {
    background: #f78989;
  }

  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.project-main {
  flex: 1;
  min-width: 0;
}

.select-hint,
.empty-hint {
  color: var(--text-secondary);
  padding: var(--spacing-xl);
  text-align: center;
}

.model-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-lg);

  h3 {
    margin: 0;
  }
}

.model-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(365px, 1fr));
  gap: var(--spacing-md);
}

.model-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.2s;
  cursor: pointer;
  position: relative;
  min-width: 365px;

  &:hover {
    box-shadow: var(--shadow-md);
  }
}

.model-card-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: 0;
}

.model-card-actions-header {
  display: flex;
  gap: 0;
  margin-left: auto;
}

.model-name {
  font-weight: 600;
  font-size: 15px;
}

.model-card-actions {
  display: flex;
  gap: 0;
  margin-top: var(--spacing-sm);

  .el-button {
    border: 1px solid var(--border-light);
    margin-right: -1px;
    color: var(--text-regular);

    &.btn-solid {
      color: #fff !important;

      &.is-disabled {
        color: #fff !important;
        opacity: 0.5 !important;

        .el-button__text {
          color: #fff !important;
        }
      }
    }

    &:first-child {
      border-radius: var(--radius-sm) 0 0 var(--radius-sm);
    }

    &:last-child {
      border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    }

    &:first-child:last-child {
      border-radius: var(--radius-sm);
    }

    &.is-disabled {
      color: var(--text-placeholder) !important;
    }
  }
}

.model-card-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: var(--spacing-sm);
}

.logs-content {
  margin: 0;
  white-space: pre-wrap;
  max-height: 400px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.6;
  font-family: 'Courier New', Courier, monospace;
}
</style>
