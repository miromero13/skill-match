import { beforeEach, describe, expect, it, vi } from "vitest"
import { apiClient } from "@/services/api-client"
import {
  calculateFileSha256,
  deleteDatasetSample,
  getDatasetSamples,
  uploadDatasetSample,
} from "@/services/dataset-sample-service"

vi.mock("@/services/api-client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

describe("dataset-sample-service", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("calculates exact SHA-256 for a given blob", async () => {
    const text = "hello skillmatch dataset"
    const blob = new Blob([text], { type: "text/plain" })
    const hash = await calculateFileSha256(blob)
    expect(hash).toHaveLength(64)
    expect(hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it("calls getDatasetSamples with expected params", async () => {
    await getDatasetSamples(1, 25, "musica")
    expect(apiClient.get).toHaveBeenCalledWith("/ai/datasets/samples", {
      params: {
        page: 1,
        page_size: 25,
        discipline: "musica",
      },
    })
  })

  it("calls uploadDatasetSample with multipart FormData and toast config", async () => {
    const blob = new Blob(["sample audio"], { type: "audio/wav" })
    await uploadDatasetSample({
      file: blob,
      fileName: "test.wav",
      discipline: "musica",
      challenge: "guitarra",
      hardware_info: "Scarlett Solo",
      signed_consent: true,
      file_hash_sha256: "a".repeat(64),
    })

    expect(apiClient.post).toHaveBeenCalledWith(
      "/ai/datasets/samples/upload",
      expect.any(FormData),
      { showToastOnSuccess: true }
    )
  })

  it("calls deleteDatasetSample with sample ID", async () => {
    const sampleId = "0237a3cc-3ba8-4f47-b1c4-7ecdc4b1f052"
    await deleteDatasetSample(sampleId)
    expect(apiClient.delete).toHaveBeenCalledWith(
      `/ai/datasets/samples/${sampleId}`,
      { showToastOnSuccess: true }
    )
  })
})
