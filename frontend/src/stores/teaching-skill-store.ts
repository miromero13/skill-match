import { create } from "zustand"
import { getAuthSessionVersion, useAuthStore } from "@/stores/auth-store"
import { useSkillEvidenceStore } from "@/stores/skill-evidence-store"

import {
    deleteTeachingSkill,
    getTeachingCatalog,
    getTeachingSkills,
    saveTeachingSkill,
} from "@/services/teaching-skill-service"

import type {
    AvailableSkill,
    TeachingSkill,
    TeachingSkillPayload,
} from "@/types/teaching-skills"
//import type { Payload } from "recharts/types/component/DefaultTooltipContent"

interface TeachingSkillState {
    items: TeachingSkill[]
    catalog: AvailableSkill[]
    page: number
    total: number
    loading: boolean
    saving: boolean
    failed: boolean
    load: (page?: number) => Promise<void>
    save: (Payload: TeachingSkillPayload, id?: string) => Promise<boolean>
    remove: (id: string) => Promise<void>
}

let sessionEpoch = 0
export const useTeachingSkillStore = create<TeachingSkillState>((set, get) => ({
    items: [],
    catalog: [],
    page: 1,
    total: 0,
    loading: false,
    saving: false,
    failed: false,

    load: async (page = 1) => {
        if (get().loading) return
        const epoch = sessionEpoch
        set({ loading: true, failed: false })

        try {
            const [response, catalog] = await Promise.all([
                getTeachingSkills(page),
                getTeachingCatalog(),
            ])

            if (epoch !== sessionEpoch) return
            set({
                items: response.data,
                total: response.count ?? 0,
                catalog,
                page,
            })
        } catch {
            if (epoch === sessionEpoch) set({ items: [], catalog: [], failed: true })
        } finally {
            if (epoch === sessionEpoch) set({ loading: false })
        }
    },

    save: async (payload, id) => {
        if (get().saving) return false
        const epoch = sessionEpoch
        set({ saving: true })

        try {
            await saveTeachingSkill(payload, id)
            if (epoch !== sessionEpoch) return false
            await get().load(get().page)
            return true
        } catch {
            return false
        } finally {
            if (epoch === sessionEpoch) set({ saving: false })
        }
    },

    remove: async (id) => {
        if (get().saving) return
        const epoch = sessionEpoch
        set({ saving: true })

        try {
            await deleteTeachingSkill(id)
            if (epoch !== sessionEpoch) return
            if (useSkillEvidenceStore.getState().skillId === id) useSkillEvidenceStore.getState().reset()
            const nextPage = get().items.length === 1 && get().page > 1
                ? get().page - 1
                : get().page
            await get().load(nextPage)
        } finally {
            if (epoch === sessionEpoch) set({ saving: false })
        }
    },
}))

let authVersion = getAuthSessionVersion()
useAuthStore.subscribe((state, previous) => {
    if (authVersion !== getAuthSessionVersion() || state.user?.id !== previous.user?.id || state.user?.role !== previous.user?.role || state.isAuthenticated !== previous.isAuthenticated) {
        authVersion = getAuthSessionVersion()
        sessionEpoch++
        useTeachingSkillStore.setState({ items: [], catalog: [], page: 1, total: 0, loading: false, saving: false, failed: false })
    }
})




/* al cerra sesion limpia este conjunto store junto con los demas datos de la cuenta para evitar mostrar datos de una sesion anterior */
