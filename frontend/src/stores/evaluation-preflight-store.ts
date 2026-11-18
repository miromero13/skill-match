import { create } from "zustand"
import { getAuthSessionVersion, useAuthStore } from "@/stores/auth-store"
import {
  getEvaluationPreflight, registerEvaluationConsent,
  type EvaluationConsent, type EvaluationPreflight,
} from "@/services/evaluation-service"

interface PreflightState {
  preflight: EvaluationPreflight | null
  consent: EvaluationConsent | null
  loading: boolean
  saving: boolean
  error: string | null
  load: (id: string) => Promise<void>
  accept: () => Promise<void>
  reset: () => void
}

let epoch = 0
const initial = { preflight: null, consent: null, loading: false, saving: false, error: null }

export const useEvaluationPreflightStore = create<PreflightState>((set, get) => ({
  ...initial,
  reset: () => { epoch++; set(initial) },
  load: async (id) => {
    const requestEpoch = ++epoch
    set({ ...initial, loading: true })
    try {
      const preflight = await getEvaluationPreflight(id)
      if (requestEpoch === epoch) set({ preflight })
    } catch (error) {
      if (requestEpoch === epoch) set({ error: error instanceof Error ? error.message : "No se pudo consultar la preparación." })
    } finally {
      if (requestEpoch === epoch) set({ loading: false })
    }
  },
  accept: async () => {
    const preflight = get().preflight
    if (!preflight || get().saving || get().consent) return
    const requestEpoch = epoch
    set({ saving: true, error: null })
    try {
      const consent = await registerEvaluationConsent(preflight.teaching_skill_id, {
        biometric_consent: true, integrity_consent: true, attempt_rule_accepted: true,
        policy_version: preflight.policy_version,
      })
      if (requestEpoch === epoch) set({ consent })
    } catch (error) {
      if (requestEpoch === epoch) set({ error: error instanceof Error ? error.message : "No se pudo registrar el consentimiento." })
    } finally {
      if (requestEpoch === epoch) set({ saving: false })
    }
  },
}))

let sessionVersion = getAuthSessionVersion()
useAuthStore.subscribe((state, previous) => {
  if (sessionVersion !== getAuthSessionVersion() || state.user?.id !== previous.user?.id ||
      state.user?.role !== previous.user?.role || state.isAuthenticated !== previous.isAuthenticated) {
    sessionVersion = getAuthSessionVersion()
    useEvaluationPreflightStore.getState().reset()
  }
})
