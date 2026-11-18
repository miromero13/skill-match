import { beforeEach, describe, expect, it, vi } from "vitest"
import { useDatasetCaptureStore } from "@/stores/dataset-capture-store"
import * as sampleService from "@/services/dataset-sample-service"

vi.mock("@/services/dataset-sample-service", () => ({
  calculateFileSha256: vi.fn().mockResolvedValue("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
  getDatasetSamples: vi.fn(),
  uploadDatasetSample: vi.fn(),
  deleteDatasetSample: vi.fn(),
}))

describe("useDatasetCaptureStore", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useDatasetCaptureStore.getState().resetRecording()
    useDatasetCaptureStore.setState({
      samples: [],
      totalCount: 0,
      isLoading: false,
      isUploading: false,
      error: null,
      lastUploadMessage: null,
      signedConsent: false,
    })
  })

  it("updates discipline, challenge, and signedConsent", () => {
    const store = useDatasetCaptureStore.getState()
    store.setDiscipline("futbol")
    store.setChallenge("dominadas")
    store.setSignedConsent(true)

    expect(useDatasetCaptureStore.getState().discipline).toBe("futbol")
    expect(useDatasetCaptureStore.getState().challenge).toBe("dominadas")
    expect(useDatasetCaptureStore.getState().signedConsent).toBe(true)
  })

  it("sets recordedBlob and triggers SHA-256 calculation", async () => {
    const store = useDatasetCaptureStore.getState()
    const blob = new Blob(["video data"], { type: "video/mp4" })
    await store.setRecordedBlob(blob, "video.mp4")

    const state = useDatasetCaptureStore.getState()
    expect(state.recordedBlob).toBe(blob)
    expect(state.recordedFileName).toBe("video.mp4")
    expect(state.recordedFileHash).toBe("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
  })

  it("rejects upload when signedConsent is false", async () => {
    const store = useDatasetCaptureStore.getState()
    store.setSignedConsent(false)

    const success = await store.uploadCurrentCapture()
    expect(success).toBe(false)
    expect(useDatasetCaptureStore.getState().error).toContain("consentimiento")
  })

  it("fetches samples and updates totalCount", async () => {
    vi.mocked(sampleService.getDatasetSamples).mockResolvedValue({
      statuscode: 200,
      message: "OK",
      data: [
        {
          id: "test-id",
          discipline: "musica",
          challenge: "piano",
          hardware_info: "mic",
          signed_consent: true,
          file_format: "wav",
          file_size_bytes: 1024,
          file_hash_sha256: "b".repeat(64),
          storage_path: "datasets/musica/test.wav",
          created_at: "2026-11-15T00:00:00Z",
          updated_at: "2026-11-15T00:00:00Z",
        },
      ],
      count: 1,
    })

    const store = useDatasetCaptureStore.getState()
    await store.fetchSamples("musica")

    const state = useDatasetCaptureStore.getState()
    expect(state.samples).toHaveLength(1)
    expect(state.totalCount).toBe(1)
    expect(state.isLoading).toBe(false)
  })

  it("successfully uploads capture and records server message", async () => {
    vi.mocked(sampleService.uploadDatasetSample).mockResolvedValue({
      statuscode: 201,
      message: "Muestra multimedia subida y procesada exitosamente.",
      data: {
        id: "new-sample",
        discipline: "musica",
        challenge: "guitarra",
        hardware_info: "mic",
        signed_consent: true,
        file_format: "wav",
        file_size_bytes: 2048,
        file_hash_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        storage_path: "datasets/musica/new-sample.wav",
        created_at: "2026-11-15T00:00:00Z",
        updated_at: "2026-11-15T00:00:00Z",
      },
    })
    vi.mocked(sampleService.getDatasetSamples).mockResolvedValue({
      statuscode: 200,
      message: "OK",
      data: [],
      count: 0,
    })

    const store = useDatasetCaptureStore.getState()
    store.setSignedConsent(true)
    const blob = new Blob(["audio stream"], { type: "audio/wav" })
    await store.setRecordedBlob(blob, "recording.wav")

    const success = await store.uploadCurrentCapture()
    expect(success).toBe(true)
    expect(useDatasetCaptureStore.getState().lastUploadMessage).toBe(
      "Muestra multimedia subida y procesada exitosamente."
    )
  })
})
