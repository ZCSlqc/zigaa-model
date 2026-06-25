import { reactive } from 'vue'
import { getChunk as getChunkFromDb, saveChunk, deleteSession, saveSession, getAllDownloadedChunks, type SessionRecord } from '../utils/download-db'

const CONCURRENCY = 3

export interface DownloadConfig {
  modelId: string
  resourceType: 'good' | 'defect' | 'test' | 'template' | 'model'
  filename: string
  api: {
    init: (...args: any[]) => Promise<any>
    chunk: (...args: any[]) => Promise<any>
    cleanup: (...args: any[]) => Promise<any>
  }
}

export interface DownloadSessionData {
  session_id: string
  filename: string
  size: number
  total_chunks: number
  chunk_size: number
}

export interface DownloadState {
  sessionId: string | null
  filename: string
  totalSize: number
  downloaded: number
  totalChunks: number
  downloadedChunks: number
  percentage: number
  speed: number
  eta: number
  status: 'idle' | 'init' | 'downloading' | 'assembling' | 'complete' | 'cancelled' | 'error'
  error?: string
}

export function useDownloadManager() {
  const state = reactive<DownloadState>({
    sessionId: null,
    filename: '',
    totalSize: 0,
    downloaded: 0,
    totalChunks: 0,
    downloadedChunks: 0,
    percentage: 0,
    speed: 0,
    eta: 0,
    status: 'idle',
  })

  let controller: AbortController | null = null
  let isActive = false
  let pendingCleanup: (() => Promise<void>) | null = null

  function reset() {
    Object.assign(state, {
      sessionId: null,
      filename: '',
      totalSize: 0,
      downloaded: 0,
      totalChunks: 0,
      downloadedChunks: 0,
      percentage: 0,
      speed: 0,
      eta: 0,
      status: 'idle',
      error: undefined,
    })
    isActive = false
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' KB'
    if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB'
    return (bytes / 1024 / 1024 / 1024).toFixed(2) + ' GB'
  }

  async function downloadChunks(config: DownloadConfig, sessionData: DownloadSessionData): Promise<void> {
    const { session_id, filename, size, total_chunks, chunk_size } = sessionData
    state.sessionId = session_id
    state.filename = filename
    state.totalSize = size
    state.totalChunks = total_chunks
    pendingCleanup = async () => {
      try { await config.api.cleanup(config.modelId, config.resourceType, session_id) } catch { /* ignore */ }
      try { await deleteSession(session_id) } catch { /* ignore */ }
    }

    const existingChunks = await getAllDownloadedChunks(session_id)
    const skipSet = new Set(existingChunks)
    let downloadedBytes = existingChunks.length * chunk_size

    await saveSession({
      sessionId: session_id,
      filename,
      totalSize: size,
      totalChunks: total_chunks,
      chunkSize: chunk_size,
      modelId: config.modelId,
      resourceType: config.resourceType,
      downloadedChunks: existingChunks,
      createdAt: Date.now(),
    } as SessionRecord)

    if (total_chunks === 0 || skipSet.size >= total_chunks) {
      await finishDownload(session_id, total_chunks)
      await config.api.cleanup(config.modelId, config.resourceType, session_id)
      pendingCleanup = null
      return
    }

    state.status = 'downloading'
    state.downloadedChunks = skipSet.size
    state.downloaded = downloadedBytes

    let lastLoaded = downloadedBytes
    let lastTime = Date.now()
    let velocity = 50 * 1024 * 1024

    const toFetch: number[] = []
    for (let i = 0; i < total_chunks; i++) {
      if (!skipSet.has(i)) toFetch.push(i)
    }

    const updateProgress = (bytes: number) => {
      const now = Date.now()
      if (lastTime > 0 && bytes > lastLoaded) {
        const dt = (now - lastTime) / 1000
        const dv = bytes - lastLoaded
        velocity = 0.3 * (dv / dt) + 0.7 * velocity
      }
      lastLoaded = bytes
      lastTime = now
      const remaining = size - bytes
      state.speed = velocity
      state.eta = velocity > 0 ? Math.ceil(remaining / velocity) : 0
      state.downloaded = bytes
      state.downloadedChunks = Math.floor(bytes / chunk_size)
      state.percentage = Math.round((bytes / size) * 100)
    }

    updateProgress(downloadedBytes)
    let fetchIdx = 0

    const fetchNext = async () => {
      while (fetchIdx < toFetch.length && isActive) {
        const idx = toFetch[fetchIdx++]
        try {
          const res = await config.api.chunk(config.modelId, config.resourceType, session_id, idx, controller!.signal)
          const data: ArrayBuffer = res.data
          await saveChunk(session_id, idx, data)
          downloadedBytes += data.byteLength
          updateProgress(downloadedBytes)
        } catch (e: any) {
          if (e.name === 'AbortError' || !isActive) return
          throw e
        }
      }
    }

    const workers: Promise<void>[] = []
    const workerCount = Math.min(CONCURRENCY, toFetch.length)
    for (let w = 0; w < workerCount; w++) {
      workers.push(fetchNext())
    }
    await Promise.all(workers)

    if (!isActive) return

    state.status = 'assembling'
    await finishDownload(session_id, total_chunks)
    pendingCleanup = null
    await config.api.cleanup(config.modelId, config.resourceType, session_id)
  }

  async function start(config: DownloadConfig): Promise<void> {
    if (isActive) return
    isActive = true
    controller = new AbortController()
    state.filename = config.filename
    state.status = 'init'

    try {
      const initRes = await config.api.init(config.modelId, config.resourceType)
      await downloadChunks(config, initRes.data)
    } catch (e: any) {
      if (e.name === 'AbortError' || !isActive) {
        state.status = 'cancelled'
      } else {
        state.status = 'error'
        state.error = e.response?.data?.detail || e.message || '下载失败'
      }
    } finally {
      isActive = false
      controller = null
    }
  }

  async function startWithSession(config: DownloadConfig, sessionData: DownloadSessionData): Promise<void> {
    if (isActive) return
    isActive = true
    controller = new AbortController()
    state.filename = sessionData.filename
    state.status = 'downloading'

    try {
      await downloadChunks(config, sessionData)
    } catch (e: any) {
      if (e.name === 'AbortError' || !isActive) {
        state.status = 'cancelled'
      } else {
        state.status = 'error'
        state.error = e.response?.data?.detail || e.message || '下载失败'
      }
    } finally {
      isActive = false
      controller = null
    }
  }

  async function finishDownload(sessionId: string, totalChunks: number): Promise<void> {
    // Stream: write each chunk to a Blob piece-by-piece to avoid loading everything into memory.
    // For very large files (e.g. 50GB+ model ZIPs) a Blob of all chunks would OOM the browser.
    // Instead we build a Blob from an array of Blob pieces, where each piece is one chunk's
    // ArrayBuffer wrapped in a Blob — the browser handles the concatenation lazily.
    // If the browser still chokes (e.g. Safari has a ~16MB Blob limit), fall back to
    // stream-to-filesystem via the Save FileSystem API.

    const MAX_BLOB_PIECES = 200  // heuristic cap — Safari's Blob limit is ~16MB per piece total
    if (totalChunks > MAX_BLOB_PIECES * 8) {
      // Very large files: try FileSystem API (Chrome/Edge only)
      try {
        await finishDownloadFileSystem(sessionId, totalChunks)
        return
      } catch {
        // Fallback: try Blob approach anyway, may still OOM on some browsers
      }
    }

    const parts: Blob[] = []
    for (let i = 0; i < totalChunks; i++) {
      const data = await getChunkFromDb(sessionId, i)
      if (data) parts.push(new Blob([data]))
    }
    const blob = new Blob(parts)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = state.filename
    document.body.appendChild(a)
    a.click()
    URL.revokeObjectURL(url)
    document.body.removeChild(a)
    await deleteSession(sessionId)
    state.status = 'complete'
    state.percentage = 100
  }

  async function finishDownloadFileSystem(sessionId: string, totalChunks: number): Promise<void> {
    // Use the File System Access API (Chrome 86+) to stream chunks directly to disk
    // without ever holding the full file in memory.
    const handle = await (window as any).showSaveFilePicker({
      suggestedName: state.filename,
      types: [{
        description: 'ZIP File',
        accept: { 'application/zip': ['.zip'] },
      }],
    })
    const writable = await handle.createWritable()
    for (let i = 0; i < totalChunks; i++) {
      const data = await getChunkFromDb(sessionId, i)
      if (data) {
        await writable.write(data)
      }
    }
    await writable.close()
    await deleteSession(sessionId)
    state.status = 'complete'
    state.percentage = 100
  }

async function cancel(): Promise<void> {
    isActive = false
    if (controller) {
      controller.abort()
      controller = null
    }
    if (pendingCleanup) {
      try { await pendingCleanup() } catch { /* ignore */ }
      pendingCleanup = null
    }
  }

  return {
    state,
    start,
    startWithSession,
    cancel,
    reset,
    formatSize,
  }
}
