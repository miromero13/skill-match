import { beforeEach, expect, it, vi } from "vitest"
import { useTeachingSkillStore as store } from "@/stores/teaching-skill-store"
import { useAuthStore, type UserProfile } from "@/stores/auth-store"
import * as service from "@/services/teaching-skill-service"
import type { TeachingSkill } from "@/types/teaching-skills"
import type { APIResponse } from "@/types/api"

vi.mock("@/services/teaching-skill-service")
const member: UserProfile = {
  id: "a",
  fullName: "Test",
  email: "test@example.invalid",
  role: "MEMBER",
  skillPointsBalance: 0,
  reputationScore: 0,
  trustLevel: 0,
  isVerified: false,
}
const offer: TeachingSkill = {
  id: "offer",
  skill_id: "catalog",
  skill_name: "Python",
  declared_level: "BEGINNER",
  years_of_experience: 1,
  description: null,
  accepts_points: false,
  hourly_points_rate: null,
  status: "DECLARADA",
}
beforeEach(() => {
  vi.resetAllMocks()
  useAuthStore.getState().login(member, "token")
  vi.mocked(service.getTeachingCatalog).mockResolvedValue([])
})

it("clears skills and rejects stale loads after session changes", async () => {
  let resolve!: (value: APIResponse<TeachingSkill[]>) => void
  vi.mocked(service.getTeachingSkills).mockReturnValue(
    new Promise((done) => {
      resolve = done
    })
  )
  const load = store.getState().load()
  useAuthStore.getState().logout()
  useAuthStore.getState().login(member, "new-session")
  resolve({ statuscode: 200, message: "Loaded", data: [offer], count: 1 })
  await load
  expect(store.getState()).toMatchObject({
    items: [],
    total: 0,
    saving: false,
    loading: false,
  })
})

it("preserves HU-14 saves and deletion pagination", async () => {
  vi.mocked(service.getTeachingSkills).mockResolvedValue({
    statuscode: 200,
    message: "Loaded",
    data: [offer],
    count: 1,
  })
  vi.mocked(service.saveTeachingSkill).mockResolvedValue({
    statuscode: 200,
    message: "Saved",
    data: offer,
  })
  expect(await store.getState().save(offer, offer.id)).toBe(true)
  expect(service.saveTeachingSkill).toHaveBeenCalledWith(offer, offer.id)
  store.setState({ items: [offer], page: 2, total: 21 })
  await store.getState().remove(offer.id)
  expect(service.deleteTeachingSkill).toHaveBeenCalledWith(offer.id)
  expect(service.getTeachingSkills).toHaveBeenLastCalledWith(1)
  expect(store.getState().saving).toBe(false)
})
