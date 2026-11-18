import { describe, expect, it, vi } from "vitest"
import {
  footballValidationReducer,
  initialFootballValidationState,
  processChunkQueueWithBackoff,
  type QueuedChunkItem,
} from "@/features/football-validation"

describe("Football Validation Phase 1 — State Machine & Chunk Uploader", () => {
  it("transitions state machine through session lifecycle and chunk confirmations", () => {
    let state = footballValidationReducer(initialFootballValidationState, {
      type: "SESSION_CREATED",
      payload: {
        session_id: "sess-001",
        ws_url: "/api/football/sessions/sess-001/ws",
        semilla: 123456,
        intentos_restantes: 2,
        estado: "created",
        version_modelo: "rules-v1",
        version_config: "0.1.0-phase0:abcdef",
      },
    })
    expect(state.sessionId).toBe("sess-001")
    expect(state.serverState).toBe("created")

    state = footballValidationReducer(state, {
      type: "ENV_CHECK_UPDATED",
      payload: {
        session_id: "sess-001",
        passed: true,
        estado: "env_check",
        failures: [],
      },
    })
    expect(state.serverState).toBe("env_check")

    state = footballValidationReducer(state, {
      type: "CHUNK_CONFIRMED",
      payload: { chunkIndex: 0, estado: "uploading" },
    })
    state = footballValidationReducer(state, {
      type: "CHUNK_CONFIRMED",
      payload: { chunkIndex: 1, estado: "uploading" },
    })
    expect(state.confirmedChunks).toEqual([0, 1])

    state = footballValidationReducer(state, {
      type: "SESSION_FINALIZED",
      payload: {
        session_id: "sess-001",
        estado: "processing",
        assembled_uri: "s3://skillmatch-football/sessions/sess-001/assembled/recording.mp4",
        assembled_sha256: "a".repeat(64),
        assembled_size_bytes: 40960,
        total_chunks: 8,
        task_id: "task-123",
      },
    })
    expect(state.serverState).toBe("processing")
    expect(state.assembledSha256).toBe("a".repeat(64))
  })

  it("uploads 8 chunks (40s video), retries with exponential backoff on network cut, and resumes from last confirmed chunk", async () => {
    const queue: QueuedChunkItem[] = Array.from({ length: 8 }, (_, idx) => ({
      chunkIndex: idx,
      blob: new Blob([`chunk-payload-${idx}`], { type: "video/mp4" }),
      sha256: `${idx}`.repeat(64).slice(0, 64),
      attempts: 0,
      confirmed: false,
    }))

    const sleepDelays: number[] = []
    const uploadedIndices: number[] = []
    let failChunk4Twice = 2

    // Simulate server already having chunks 0, 1, 2 confirmed before resume
    const fetchConfirmedChunksFn = vi.fn(async () => [0, 1, 2])

    const uploadChunkFn = vi.fn(
      async (sessionId: string, chunkIndex: number, blob: Blob, sha256?: string) => {
        if (chunkIndex === 4 && failChunk4Twice > 0) {
          failChunk4Twice -= 1
          throw new Error("Simulated network cut during chunk 4")
        }
        uploadedIndices.push(chunkIndex)
        return {
          data: {
            session_id: sessionId,
            chunk_index: chunkIndex,
            sha256: sha256 ?? "0".repeat(64),
            size_bytes: blob.size,
            storage_uri: `s3://skillmatch-football/sessions/${sessionId}/chunks/${chunkIndex}.mp4`,
            idempotent_replay: false,
            estado: "uploading" as const,
          },
        }
      }
    )

    const sleepFn = vi.fn(async (ms: number) => {
      sleepDelays.push(ms)
    })

    const confirmed = await processChunkQueueWithBackoff("sess-40s", queue, {
      fetchConfirmedChunksFn,
      uploadChunkFn,
      sleepFn,
      baseDelayMs: 100,
      maxRetries: 4,
    })

    // Chunks 0, 1, 2 were already confirmed on server -> only 3, 4, 5, 6, 7 uploaded
    expect(uploadedIndices).toEqual([3, 4, 5, 6, 7])
    // Chunk 4 failed twice -> backoff delays 100ms, 200ms
    expect(sleepDelays).toEqual([100, 200])
    expect(confirmed).toEqual([0, 1, 2, 3, 4, 5, 6, 7])
  })
})
