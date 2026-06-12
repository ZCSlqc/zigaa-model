import client from './client'

export function listModels(projectId: string) {
  return client.get('/models/', { params: { project_id: projectId } })
}

export function createModel(projectId: string, name: string, description: string) {
  return client.post('/models/', { name, description }, { params: { project_id: projectId } })
}

export function getModel(modelId: string) {
  return client.get(`/models/${modelId}`)
}

export function updateModel(modelId: string, name?: string, description?: string) {
  return client.put(`/models/${modelId}`, { name, description })
}

export function deleteModel(modelId: string) {
  return client.delete(`/models/${modelId}`)
}

export function trainModel(modelId: string) {
  return client.post(`/models/${modelId}/train`, {}, { timeout: 1200000 })
}

export function stopTraining(modelId: string) {
  return client.post(`/models/${modelId}/stop-training`)
}

export function getLogs(modelId: string) {
  return client.get(`/models/${modelId}/log/training`)
}

export function getTestLogs(modelId: string) {
  return client.get(`/models/${modelId}/log/test`)
}

export function pollStatus(modelId: string) {
  return client.get(`/models/${modelId}/poll-status`)
}

export function runTest(modelId: string) {
  return client.post(`/models/${modelId}/run-test`, {}, { timeout: 1200000 })
}

export function stopTest(modelId: string) {
  return client.post(`/models/${modelId}/stop-test`)
}

// 模型分片下载
export function downloadModelInit(modelId: string) {
  return client.post(`/models/${modelId}/model/download-init`, {}, { timeout: 1200000 })
}

export function downloadModelChunk(modelId: string, sessionId: string, chunkIndex: number, signal?: AbortSignal) {
  return client.get(`/models/${modelId}/model/download-chunk`, {
    params: { session_id: sessionId, chunk_index: chunkIndex },
    responseType: 'arraybuffer',
    signal,
  })
}

export function downloadModelCleanup(modelId: string, sessionId: string) {
  return client.post(`/models/${modelId}/model/download-cleanup`, null, {
    params: { session_id: sessionId },
  })
}
