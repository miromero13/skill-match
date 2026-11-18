import { useCallback, useRef, useState } from "react"
import {
  computeBlobSha256Hex,
  footballValidationApi,
} from "../api/football-validation-api"
import type { ChunkUploadResponse } from "../state/football-session-machine"

export interface QueuedChunkItem {
  chunkIndex: number
  blob: Blob
  sha256?: string
  attempts: number
  confirmed: boolean
}

export interface ChunkUploaderDeps {
  uploadChunkFn?: (
    sessionId: string,
    chunkIndex: number,
    blob: Blob,
    sha256?: string
  ) => Promise<{ data: ChunkUploadResponse }>
  fetchConfirmedChunksFn?: (sessionId: string) => Promise<number[]>
  sleepFn?: (ms: number) => Promise<void>
  baseDelayMs?: number
  maxRetries?: number
}

const defaultSleep = (ms: number) =>
  new Promise<void>((resolve) => {
    setTimeout(resolve, ms)
  })

/**
 * Pure exponential-backoff chunk queue processor.
 * If a network failure occurs, retries up to `maxRetries` with `baseDelayMs * 2^attempt`
 * and supports resuming from the server's last confirmed chunk list.
 */
export async function processChunkQueueWithBackoff(
  sessionId: string,
  queue: QueuedChunkItem[],
  deps: ChunkUploaderDeps = {},
  onChunkConfirmed?: (resp: ChunkUploadResponse) => void
): Promise<number[]> {
  const uploadFn =
    deps.uploadChunkFn ??
    (async (sid, idx, blob, sha) =>
      footballValidationApi.uploadChunk(sid, idx, blob, sha))
  const fetchConfirmedFn =
    deps.fetchConfirmedChunksFn ??
    (async (sid) => {
      const res = await footballValidationApi.getSessionStatus(sid)
      return res.data.confirmed_chunks
    })
  const sleep = deps.sleepFn ?? defaultSleep
  const baseDelayMs = deps.baseDelayMs ?? 300
  const maxRetries = deps.maxRetries ?? 4

  let serverConfirmed = new Set<number>()
  try {
    const initialConfirmed = await fetchConfirmedFn(sessionId)
    serverConfirmed = new Set(initialConfirmed)
  } catch {
    // Offline during initial status check; proceed with local queue state
  }

  const ordered = [...queue].sort((a, b) => a.chunkIndex - b.chunkIndex)

  for (const item of ordered) {
    if (item.confirmed || serverConfirmed.has(item.chunkIndex)) {
      item.confirmed = true
      serverConfirmed.add(item.chunkIndex)
      continue
    }

    if (!item.sha256) {
      item.sha256 = await computeBlobSha256Hex(item.blob)
    }

    let attempt = 0
    while (!item.confirmed) {
      try {
        const response = await uploadFn(
          sessionId,
          item.chunkIndex,
          item.blob,
          item.sha256
        )
        item.confirmed = true
        serverConfirmed.add(item.chunkIndex)
        onChunkConfirmed?.(response.data)
      } catch (err) {
        attempt += 1
        item.attempts = attempt
        if (attempt > maxRetries) {
          throw err
        }
        const backoffMs = baseDelayMs * Math.pow(2, attempt - 1)
        await sleep(backoffMs)
      }
    }
  }

  return Array.from(serverConfirmed).sort((a, b) => a - b)
}

export function useChunkUploader(
  sessionId: string | null,
  deps: ChunkUploaderDeps = {},
  onChunkConfirmed?: (resp: ChunkUploadResponse) => void
) {
  const [confirmedChunks, setConfirmedChunks] = useState<number[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const queueRef = useRef<Map<number, QueuedChunkItem>>(new Map())

  const enqueueChunk = useCallback(
    async (chunkIndex: number, blob: Blob) => {
      const existing = queueRef.current.get(chunkIndex)
      if (!existing) {
        queueRef.current.set(chunkIndex, {
          chunkIndex,
          blob,
          attempts: 0,
          confirmed: false,
        })
      }
      if (!sessionId) return

      setIsUploading(true)
      setUploadError(null)
      try {
        const items = Array.from(queueRef.current.values())
        const confirmed = await processChunkQueueWithBackoff(
          sessionId,
          items,
          deps,
          onChunkConfirmed
        )
        setConfirmedChunks(confirmed)
      } catch (err) {
        const msg =
          err instanceof Error
            ? err.message
            : "Error subiendo fragmento de video. Reintentando al recuperar conexión."
        setUploadError(msg)
      } finally {
        setIsUploading(false)
      }
    },
    [deps, onChunkConfirmed, sessionId]
  )

  const resumePendingChunks = useCallback(async (): Promise<number[]> => {
    if (!sessionId) return []
    setIsUploading(true)
    setUploadError(null)
    try {
      const items = Array.from(queueRef.current.values())
      const confirmed = await processChunkQueueWithBackoff(
        sessionId,
        items,
        deps,
        onChunkConfirmed
      )
      setConfirmedChunks(confirmed)
      return confirmed
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : "No se pudo reanudar la subida de fragmentos."
      setUploadError(msg)
      throw err
    } finally {
      setIsUploading(false)
    }
  }, [deps, onChunkConfirmed, sessionId])

  const resetUploader = useCallback(() => {
    queueRef.current.clear()
    setConfirmedChunks([])
    setIsUploading(false)
    setUploadError(null)
  }, [])

  return {
    confirmedChunks,
    isUploading,
    uploadError,
    enqueueChunk,
    resumePendingChunks,
    resetUploader,
  }
}
