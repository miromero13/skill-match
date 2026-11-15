import { beforeEach, expect, it, vi } from "vitest"
import { apiClient } from "@/services/api-client"
import {
  createEvidence,
  deleteEvidence,
  getEvidences,
  updateEvidence,
} from "@/services/skill-evidence-service"

vi.mock("@/services/api-client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))
const payload = {
  title: "Project",
  description: null,
  url: "https://example.com/",
  evidence_type: "OTHER" as const,
}
beforeEach(() => vi.clearAllMocks())

it("uses the teaching offer ID and explicit pagination", async () => {
  await getEvidences("offer", 2)
  expect(apiClient.get).toHaveBeenCalledWith(
    "/users/me/teaching-skills/offer/evidences",
    { params: { page: 2, page_size: 20 }, showToastOnError: false }
  )
})
it("sends complete bodies and one toast owner through the shared client", async () => {
  const options = { showToastOnError: true, showToastOnSuccess: true }
  await createEvidence("offer", payload)
  await updateEvidence("offer", "evidence", payload)
  await deleteEvidence("offer", "evidence")
  expect(apiClient.post).toHaveBeenCalledWith(
    "/users/me/teaching-skills/offer/evidences",
    payload,
    options
  )
  expect(apiClient.put).toHaveBeenCalledWith(
    "/users/me/teaching-skills/offer/evidences/evidence",
    payload,
    options
  )
  expect(apiClient.delete).toHaveBeenCalledWith(
    "/users/me/teaching-skills/offer/evidences/evidence",
    options
  )
})
