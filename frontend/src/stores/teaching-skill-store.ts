import { create } from "zustand"

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
        set({ loading: true, failed: false })

        try {
            const [response, catalog] = await Promise.all([
                getTeachingSkills(page),
                getTeachingCatalog(),
            ])

            set({
                items: response.data,
                total: response.count ?? 0,
                catalog,
                page,
            })
        } catch {
            set({ items: [], catalog: [], failed: true })
        } finally {
            set({ loading: false })
        }
    },

    save: async (payload, id) => {
        if (get().saving) return false
        set({ saving: true })

        try {
            await saveTeachingSkill(payload, id)
            await get().load(get().page)
            return true
        } catch {
            return false
        } finally {
            set({ saving: false })
        }
    },

    remove: async (id) => {
        if (get().saving) return
        set({ saving: true })

        try {
            await deleteTeachingSkill(id)
            const nextPage = get().items.length === 1 && get().page > 1
                ? get().page - 1
                : get().page
            await get().load(nextPage)
        } finally {
            set({ saving: false })
        }
    },
}))




/* al cerra sesion limpia este conjunto store junto con los demas datos de la cuenta para evitar mostrar datos de una sesion anterior */
