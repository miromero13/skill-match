import { create } from "zustand"
import { toast } from "sonner"
import { getAuthSessionVersion, useAuthStore } from "@/stores/auth-store"
import {
  createEvidence,
  deleteEvidence,
  getEvidences,
  updateEvidence,
} from "@/services/skill-evidence-service"
import type { EvidencePayload, SkillEvidence } from "@/types/skill-evidence"

interface EvidenceState {
  skillId: string | null
  items: SkillEvidence[]
  total: number
  page: number
  loading: boolean
  mutating: boolean
  error: string | null
  reset: () => void
  load: (skillId: string, page?: number) => Promise<boolean>
  save: (payload: EvidencePayload, evidenceId?: string) => Promise<boolean>
  remove: (evidenceId: string) => Promise<boolean>
}

const initial = {
  skillId: null,
  items: [],
  total: 0,
  page: 1,
  loading: false,
  mutating: false,
  error: null,
}
let generation = 0
let latestLoad = 0
const message = (error: unknown) =>
  error instanceof Error ? error.message : "No se pudo completar la solicitud."

export const useSkillEvidenceStore = create<EvidenceState>((set, get) => ({
  ...initial,
  reset: () => {
    generation++
    latestLoad++
    set(initial)
  },
  load: async (skillId, page = 1) => {
    if (get().skillId !== skillId) {
      generation++
      set({ ...initial, skillId })
    }
    const epoch = generation
    const request = ++latestLoad
    set({
      skillId,
      page,
      loading: true,
      error: null,
      ...(get().skillId !== skillId ? { items: [], total: 0 } : {}),
    })
    try {
      const response = await getEvidences(skillId, page)
      if (epoch !== generation || request !== latestLoad) return false
      set({ items: response.data, total: response.count ?? 0 })
      return true
    } catch (error) {
      if (epoch === generation && request === latestLoad) {
        set({ error: message(error) })
        toast.error(message(error))
      }
      return false
    } finally {
      if (epoch === generation && request === latestLoad)
        set({ loading: false })
    }
  },
  save: async (payload, evidenceId) => {
    const skillId = get().skillId
    if (!skillId || get().mutating) return false
    const epoch = generation
    set({ mutating: true, error: null })
    try {
      const response = evidenceId
        ? await updateEvidence(skillId, evidenceId, payload)
        : await createEvidence(skillId, payload)
      if (epoch !== generation || get().skillId !== skillId) return false
      set((state) => ({
        items: evidenceId
          ? state.items.map((item) =>
              item.id === evidenceId ? response.data : item
            )
          : state.page === 1
            ? [response.data, ...state.items].slice(0, 20)
            : state.items,
        total: state.total + (evidenceId ? 0 : 1),
      }))
      // Una creación confirmada sigue siendo exitosa aunque falle recargar.
      await get().load(skillId, get().page)
      return epoch === generation && get().skillId === skillId
    } catch (error) {
      if (epoch === generation && get().skillId === skillId)
        set({ error: message(error) })
      return false
    } finally {
      if (epoch === generation) set({ mutating: false })
    }
  },
  remove: async (id) => {
    const skillId = get().skillId
    if (!skillId || get().mutating) return false
    const epoch = generation
    set({ mutating: true, error: null })
    try {
      await deleteEvidence(skillId, id)
      if (epoch !== generation || get().skillId !== skillId) return false
      const page =
        get().items.length === 1 ? Math.max(1, get().page - 1) : get().page
      set((state) => ({
        items: state.items.filter((item) => item.id !== id),
        total: Math.max(0, state.total - 1),
      }))
      await get().load(skillId, page)
      return epoch === generation && get().skillId === skillId
    } catch (error) {
      if (epoch === generation && get().skillId === skillId)
        set({ error: message(error) })
      return false
    } finally {
      if (epoch === generation) set({ mutating: false })
    }
  },
}))

let authVersion = getAuthSessionVersion()
useAuthStore.subscribe((state, previous) => {
  if (
    authVersion !== getAuthSessionVersion() ||
    state.user?.id !== previous.user?.id ||
    state.user?.role !== previous.user?.role ||
    state.isAuthenticated !== previous.isAuthenticated
  ) {
    authVersion = getAuthSessionVersion()
    useSkillEvidenceStore.getState().reset()
  }
})
