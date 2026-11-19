import { create } from "zustand"
import { passportService } from "@/services/passport-service"
import type { PublicPassport } from "@/types/passport"
import { toast } from "sonner"

interface PassportState {
  currentPassport: PublicPassport | null
  isLoadingPassport: boolean
  passportError: string | null
  isQrModalOpen: boolean

  // Acciones
  loadPassport: (uuid: string) => Promise<PublicPassport | null>
  openQrModal: () => void
  closeQrModal: () => void
  copyShareableLink: () => Promise<boolean>
}

export const usePassportStore = create<PassportState>((set, get) => ({
  currentPassport: null,
  isLoadingPassport: false,
  passportError: null,
  isQrModalOpen: false,

  loadPassport: async (uuid: string) => {
    set({ isLoadingPassport: true, passportError: null })
    try {
      const data = await passportService.getPublicPassport(uuid)
      set({ currentPassport: data, isLoadingPassport: false })
      return data
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "No se pudo cargar el pasaporte."
      set({ passportError: msg, isLoadingPassport: false })
      return null
    }
  },

  openQrModal: () => set({ isQrModalOpen: true }),
  closeQrModal: () => set({ isQrModalOpen: false }),

  copyShareableLink: async () => {
    const passport = get().currentPassport
    const url = passport?.public_shareable_url || window.location.href
    try {
      await navigator.clipboard.writeText(url)
      toast.success("Enlace oficial copiado al portapapeles", {
        description: "Puedes compartirlo en tu CV, perfil de LinkedIn o firma.",
      })
      return true
    } catch {
      toast.error("No se pudo copiar el enlace automáticamente.")
      return false
    }
  },
}))
