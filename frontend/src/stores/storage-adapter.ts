import { Capacitor } from "@capacitor/core"
import { Preferences } from "@capacitor/preferences"
import type { StateStorage } from "zustand/middleware"

/**
 * Storage híbrido para persistencia de Zustand (HU-09 / RF-USR-04):
 * - En plataformas móviles nativas (iOS / Android vía Capacitor): Utiliza Preferences seguro de Capacitor.
 * - En navegador web: Utiliza localStorage estándar.
 */
export const hybridAuthStorage: StateStorage = {
  getItem: async (name: string): Promise<string | null> => {
    if (Capacitor.isNativePlatform()) {
      const { value } = await Preferences.get({ key: name })
      return value
    }
    return localStorage.getItem(name)
  },

  setItem: async (name: string, value: string): Promise<void> => {
    if (Capacitor.isNativePlatform()) {
      await Preferences.set({ key: name, value })
      return
    }
    localStorage.setItem(name, value)
  },

  removeItem: async (name: string): Promise<void> => {
    if (Capacitor.isNativePlatform()) {
      await Preferences.remove({ key: name })
      return
    }
    localStorage.removeItem(name)
  },
}
