import { beforeEach, expect, it, vi } from "vitest"
import { useSkillEvidenceStore as store } from "@/stores/skill-evidence-store"
import { useAuthStore } from "@/stores/auth-store"
import * as service from "@/services/skill-evidence-service"
import type { SkillEvidence } from "@/types/skill-evidence"
import type { APIResponse } from "@/types/api"

vi.mock("@/services/skill-evidence-service")
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }))
const item: SkillEvidence = {
  id: "e1",
  teaching_skill_id: "a",
  title: "Project",
  description: null,
  url: "https://example.com/",
  evidence_type: "OTHER",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
}
const list = (
  items: SkillEvidence[] = [],
  count = items.length
): APIResponse<SkillEvidence[]> => ({
  statuscode: 200,
  message: "Loaded",
  data: items,
  count,
})
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}
beforeEach(() => {
  vi.resetAllMocks()
  store.getState().reset()
  useAuthStore.getState().logout()
})

it("discards slow results after switching skills", async () => {
  const old = deferred<APIResponse<SkillEvidence[]>>()
  vi.mocked(service.getEvidences)
    .mockReturnValueOnce(old.promise)
    .mockResolvedValueOnce(list())
  const first = store.getState().load("a")
  await store.getState().load("b")
  old.resolve(list([item]))
  await first
  expect(store.getState()).toMatchObject({
    skillId: "b",
    items: [],
    total: 0,
    loading: false,
  })
})
it("discards results after logout", async () => {
  useAuthStore.setState({
    isAuthenticated: true,
    user: { id: "a" } as ReturnType<typeof useAuthStore.getState>["user"],
  })
  const old = deferred<APIResponse<SkillEvidence[]>>()
  vi.mocked(service.getEvidences).mockReturnValueOnce(old.promise)
  const request = store.getState().load("a")
  useAuthStore.getState().logout()
  old.resolve(list([item]))
  await request
  expect(store.getState()).toMatchObject({ items: [], skillId: null })
})
it("keeps confirmed creation successful when refreshing fails", async () => {
  store.setState({ skillId: "a" })
  vi.mocked(service.createEvidence).mockResolvedValue({
    statuscode: 201,
    message: "Created",
    data: item,
  })
  vi.mocked(service.getEvidences).mockRejectedValue(
    new Error("Servidor temporalmente inaccesible")
  )
  expect(await store.getState().save(item)).toBe(true)
  expect(store.getState()).toMatchObject({
    items: [item],
    total: 1,
    error: "Servidor temporalmente inaccesible",
    mutating: false,
  })
  expect(service.createEvidence).toHaveBeenCalledTimes(1)
})
it("does not modify records after a rejected mutation", async () => {
  store.setState({ skillId: "a", items: [item], total: 1 })
  vi.mocked(service.updateEvidence).mockRejectedValue(
    new Error("Ya registraste esta evidencia.")
  )
  expect(await store.getState().save(item, item.id)).toBe(false)
  expect(store.getState()).toMatchObject({
    items: [item],
    error: "Ya registraste esta evidencia.",
    mutating: false,
  })
})
it("deletes the last row and goes back one page", async () => {
  store.setState({ skillId: "a", items: [item], page: 2, total: 21 })
  vi.mocked(service.deleteEvidence).mockResolvedValue({
    statuscode: 200,
    message: "Deleted",
    data: null,
  })
  vi.mocked(service.getEvidences).mockResolvedValue(list([], 20))
  expect(await store.getState().remove("e1")).toBe(true)
  expect(service.getEvidences).toHaveBeenCalledWith("a", 1)
  expect(store.getState()).toMatchObject({
    page: 1,
    total: 20,
    mutating: false,
  })
})
it("prevents double submit", async () => {
  store.setState({ skillId: "a" })
  const pending = deferred<APIResponse<SkillEvidence>>()
  vi.mocked(service.createEvidence).mockReturnValue(pending.promise)
  vi.mocked(service.getEvidences).mockResolvedValue(list([item]))
  const first = store.getState().save(item)
  expect(await store.getState().save(item)).toBe(false)
  pending.resolve({ statuscode: 201, message: "Created", data: item })
  await first
  expect(service.createEvidence).toHaveBeenCalledTimes(1)
})
