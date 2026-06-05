const DB_NAME = 'zigaa-downloads'
const DB_VERSION = 1
const CHUNK_STORE = 'chunks'
const SESSION_STORE = 'sessions'

export interface SessionRecord {
  sessionId: string
  filename: string
  totalSize: number
  totalChunks: number
  chunkSize: number
  modelId: string
  resourceType: string
  downloadedChunks: number[]
  createdAt: number
}

let dbCache: IDBDatabase | null = null
let dbOpen: Promise<IDBDatabase> | null = null

function openDb(): Promise<IDBDatabase> {
  if (dbCache) return Promise.resolve(dbCache)
  if (dbOpen) return dbOpen
  dbOpen = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(CHUNK_STORE)) {
        db.createObjectStore(CHUNK_STORE, { keyPath: 'key' })
      }
      if (!db.objectStoreNames.contains(SESSION_STORE)) {
        db.createObjectStore(SESSION_STORE, { keyPath: 'sessionId' })
      }
    }
    request.onsuccess = () => {
      dbCache = request.result
      dbOpen = null
      resolve(dbCache)
    }
    request.onerror = () => {
      dbOpen = null
      reject(request.error)
    }
  })
  return dbOpen
}

function tx(store: string, mode: IDBTransactionMode) {
  return new Promise<IDBObjectStore>(async (resolve) => {
    const db = await openDb()
    const transaction = db.transaction(store, mode)
    resolve(transaction.objectStore(store))
  })
}

export async function saveChunk(sessionId: string, chunkIndex: number, data: ArrayBuffer): Promise<void> {
  const store = await tx(CHUNK_STORE, 'readwrite')
  store.put({ key: `${sessionId}_${chunkIndex}`, data })
}

export async function getChunk(sessionId: string, chunkIndex: number): Promise<ArrayBuffer | undefined> {
  const store = await tx(CHUNK_STORE, 'readonly')
  return new Promise((resolve, reject) => {
    const req = store.get(`${sessionId}_${chunkIndex}`)
    req.onsuccess = () => resolve(req.result?.data)
    req.onerror = () => reject(req.error)
  })
}

export async function deleteSessionData(sessionId: string): Promise<void> {
  const store = await tx(CHUNK_STORE, 'readwrite')
  const range = IDBKeyRange.bound(sessionId + '_', sessionId + '`')
  const req = store.openCursor(range)
  req.onsuccess = (event) => {
    const cursor = (event.target as IDBRequest<IDBCursorWithValue>).result
    if (cursor) {
      cursor.delete()
      cursor.continue()
    }
  }
}

export async function saveSession(record: SessionRecord): Promise<void> {
  const store = await tx(SESSION_STORE, 'readwrite')
  store.put(record)
}

export async function getSession(sessionId: string): Promise<SessionRecord | undefined> {
  const store = await tx(SESSION_STORE, 'readonly')
  return new Promise((resolve, reject) => {
    const req = store.get(sessionId)
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export async function deleteSession(sessionId: string): Promise<void> {
  await deleteSessionData(sessionId)
  const store = await tx(SESSION_STORE, 'readwrite')
  store.delete(sessionId)
}

export async function getAllDownloadedChunks(sessionId: string): Promise<number[]> {
  const store = await tx(CHUNK_STORE, 'readonly')
  const chunks: number[] = []
  const range = IDBKeyRange.bound(sessionId + '_', sessionId + '`')
  const req = store.openCursor(range)
  const prefixLen = sessionId.length + 1
  return new Promise((resolve, reject) => {
    req.onsuccess = (event) => {
      const cursor = (event.target as IDBRequest<IDBCursorWithValue>).result
      if (cursor) {
        const key = (cursor.value as any).key as string
        const idx = parseInt(key.substring(prefixLen), 10)
        if (!isNaN(idx)) chunks.push(idx)
        cursor.continue()
      } else {
        resolve(chunks.sort((a, b) => a - b))
      }
    }
    req.onerror = () => reject(req.error)
  })
}

export async function getAllSessions(): Promise<SessionRecord[]> {
  const store = await tx(SESSION_STORE, 'readonly')
  const sessions: SessionRecord[] = []
  const req = store.openCursor()
  return new Promise((resolve, reject) => {
    req.onsuccess = (event) => {
      const cursor = (event.target as IDBRequest<IDBCursorWithValue>).result
      if (cursor) {
        sessions.push(cursor.value as SessionRecord)
        cursor.continue()
      } else {
        resolve(sessions)
      }
    }
    req.onerror = () => reject(req.error)
  })
}
