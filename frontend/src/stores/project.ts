import { defineStore } from 'pinia'
import { ref } from 'vue'
import { listProjects, createProject, deleteProject, updateProject as updateProjectApi } from '../api/project'
import { listModels, createModel, deleteModel, updateModel as updateModelApi, trainModel as trainModelApi, stopTraining as stopTrainingApi, getLogs as getLogsApi, getTestLogs as getTestLogsApi, pollStatus as pollStatusApi, runTest as runTestApi, stopTest as stopTestApi } from '../api/model'

export interface Project {
  id: string
  name: string
  description: string
  owner_id: string
  created_at: string
  models: { count: number }[]
}

export interface Model {
  id: string
  name: string
  description: string
  project_id: string
  status: {
    file_status?: { status: string }
    training_status?: { status: string; error?: string }
    test_status?: { status: string; error?: string }
    status?: string  // legacy fallback
  } | null
  upload_path: string | null
  created_at: string
  package_count: number
}

export const useProjectStore = defineStore('project', () => {
  const projects = ref<Project[]>([])
  const currentProjectId = ref('')
  const models = ref<Model[]>([])

  async function fetchProjects() {
    const res = await listProjects()
    projects.value = res.data
  }

  async function addProject(name: string, description: string) {
    const res = await createProject(name, description)
    await fetchProjects()
    return res.data
  }

  async function removeProject(id: string) {
    await deleteProject(id)
    if (currentProjectId.value === id) {
      currentProjectId.value = ''
      models.value = []
    }
    await fetchProjects()
  }

  async function updateProject(id: string, name: string, description: string) {
    await updateProjectApi(id, name, description)
    await fetchProjects()
  }

  function selectProject(id: string) {
    currentProjectId.value = id
    fetchModels(id)
  }

  async function fetchModels(projectId: string) {
    const res = await listModels(projectId)
    models.value = res.data
  }

  async function addModel(name: string, description: string) {
    if (!currentProjectId.value) return
    await createModel(currentProjectId.value, name, description)
    await fetchModels(currentProjectId.value)
  }

  async function removeModel(id: string) {
    await deleteModel(id)
    await fetchModels(currentProjectId.value)
  }

  async function updateModel(id: string, name: string, description: string) {
    await updateModelApi(id, name, description)
    await fetchModels(currentProjectId.value)
  }

  async function trainModel(id: string) {
    await trainModelApi(id)
  }

  async function stopTraining(id: string) {
    await stopTrainingApi(id)
  }

  async function getLogs(id: string) {
    const res = await getLogsApi(id)
    return res.data
  }

  async function getTestLogs(id: string) {
    const res = await getTestLogsApi(id)
    return res.data
  }

  async function pollStatus(id: string) {
    try {
      const res = await pollStatusApi(id)
      const model = models.value.find(m => m.id === id)
      if (model && model.status) {
        if (!model.status.training_status) model.status.training_status = { status: 'idle' }
        if (!model.status.test_status) model.status.test_status = { status: 'idle' }
        model.status.training_status.status = res.data.training_status || model.status.training_status.status
        model.status.test_status.status = res.data.test_status || model.status.test_status.status
        if (res.data.error) model.status.training_status.error = res.data.error
        if (res.data.test_error) model.status.test_status.error = res.data.test_error
      }
    } catch (e) {
      console.warn('pollStatus failed', id, e)
    }
  }

  async function runTest(id: string) {
    await runTestApi(id)
  }

  async function stopTest(id: string) {
    await stopTestApi(id)
  }

  return {
    projects,
    currentProjectId,
    models,
    fetchProjects,
    addProject,
    removeProject,
    updateProject,
    selectProject,
    fetchModels,
    addModel,
    removeModel,
    updateModel,
    trainModel,
    stopTraining,
    getLogs,
    getTestLogs,
    pollStatus,
    runTest,
    stopTest,
  }
})
