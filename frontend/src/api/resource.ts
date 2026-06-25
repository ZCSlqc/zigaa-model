import client, { LONG_TIMEOUT } from './client'

// 磁盘空间检查
export function checkDiskSpace(modelId: string, type: 'good' | 'defect' | 'test' | 'template') {
  return client.get(`/resources/${modelId}/${type}/disk-check`)
}

// ZIP 分片上传
export function uploadInit(modelId: string, resourceType: 'good' | 'defect' | 'test' | 'template', data: {
  upload_id: string
  filename: string
  total_size: number
  total_chunks: number
  chunk_size: number
}) {
  return client.post(`/resources/${modelId}/${resourceType}/upload-init`, data)
}

export function uploadChunk(modelId: string, resourceType: 'good' | 'defect' | 'test' | 'template', uploadId: string, chunkIndex: number, chunkBlob: Blob, signal?: AbortSignal) {
  const formData = new FormData()
  formData.append('file', chunkBlob)
  return client.post(`/resources/${modelId}/${resourceType}/upload-chunk`, formData, {
    params: { upload_id: uploadId, chunk_index: chunkIndex },
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: LONG_TIMEOUT,
    signal,
  })
}

export function uploadComplete(modelId: string, resourceType: 'good' | 'defect' | 'test' | 'template', uploadId: string, signal?: AbortSignal) {
  return client.post(`/resources/${modelId}/${resourceType}/upload-complete`, null, {
    params: { upload_id: uploadId },
    signal,
  })
}

export function getUploadStatus(modelId: string, resourceType: string, uploadId: string) {
  return client.get(`/resources/${modelId}/${resourceType}/upload-status/${uploadId}`)
}

// JSON 参数上传
export function uploadParameter(modelId: string, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return client.post(`/resources/${modelId}/parameter/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// 获取/编辑/删除参数文件
export function getParameter(modelId: string) {
  return client.get(`/resources/${modelId}/parameter`)
}

export function editParameter(modelId: string, data: any) {
  return client.put(`/resources/${modelId}/parameter`, data)
}

export function deleteParameterFile(modelId: string) {
  return client.delete(`/resources/${modelId}/parameter/file`)
}

// 删除
export function deleteGood(modelId: string) {
  return client.delete(`/resources/${modelId}/good`)
}

export function deleteDefect(modelId: string) {
  return client.delete(`/resources/${modelId}/defect`)
}

export function deleteParameter(modelId: string) {
  return client.delete(`/resources/${modelId}/parameter`)
}

export function deleteTest(modelId: string) {
  return client.delete(`/resources/${modelId}/test`)
}

export function deleteTemplate(modelId: string) {
  return client.delete(`/resources/${modelId}/template`)
}

// 下载（返回 Blob 供前端触发保存）
export function downloadParameter(modelId: string) {
  return client.get(`/resources/${modelId}/parameter/download`, { responseType: 'blob' })
}

export function getResourceTree(modelId: string, resourceType: string, layer: string = '') {
  return client.get('/resources/tree', {
    params: { model_id: modelId, resource_type: resourceType, layer },
  })
}

export function getImageInfo(modelId: string, resourceType: string, path: string) {
  return client.get(`/resources/${modelId}/${resourceType}/image-info`, {
    params: { path },
  })
}

// 单图标注
export function getAnnotation(modelId: string, resourceType: string, imagePath: string) {
  return client.get(`/annotations/${modelId}/${resourceType}/${imagePath}`)
}

export function saveAnnotation(modelId: string, resourceType: string, imagePath: string, data: any) {
  return client.put(`/annotations/${modelId}/${resourceType}/${imagePath}`, data)
}

export function deleteImage(modelId: string, resourceType: string, imagePath: string) {
  return client.delete(`/annotations/${modelId}/${resourceType}/${imagePath}`)
}

export function deleteFolder(modelId: string, resourceType: string, folderPath: string) {
  return client.delete(`/annotations/${modelId}/${resourceType}/folder/${folderPath}`)
}

// 更新图片 msgs（category 等）
export function updateImageMsg(modelId: string, resourceType: string, imagePath: string, data: { category: string }) {
  return client.patch(`/annotations/${modelId}/${resourceType}/msg/${imagePath}`, data)
}

// 重新入库
export function reprocessResource(modelId: string, resourceType: string) {
  return client.post(`/resources/${modelId}/${resourceType}/reprocess`)
}

// 分片下载
export function arrangeList(modelId: string, resourceType: string) {
  return client.get(`/resources/${modelId}/${resourceType}/arrange-list`)
}

export function downloadInit(modelId: string, resourceType: string, extra?: Record<string, any>) {
  return client.post(`/resources/${modelId}/${resourceType}/download-init`, {}, { params: extra, timeout: LONG_TIMEOUT })
}

export function downloadChunk(modelId: string, resourceType: string, sessionId: string, chunkIndex: number, signal?: AbortSignal) {
  return client.get(`/resources/${modelId}/${resourceType}/download-chunk`, {
    params: { session_id: sessionId, chunk_index: chunkIndex },
    responseType: 'arraybuffer',
    timeout: LONG_TIMEOUT,
    signal,
  })
}

export function downloadCleanup(modelId: string, resourceType: string, sessionId: string) {
  return client.post(`/resources/${modelId}/${resourceType}/download-cleanup`, null, {
    params: { session_id: sessionId },
  })
}
