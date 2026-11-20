import { Capacitor } from "@capacitor/core"
import { Preferences } from "@capacitor/preferences"
import { KeychainAccess, SecureStorage } from "@aparajita/capacitor-secure-storage"
import type { StateStorage } from "zustand/middleware"

// Serialize native persistence: a slow login write must never restore a logged-out session.
let pending: Promise<unknown> = Promise.resolve()
function ordered<T>(operation: () => Promise<T>): Promise<T> {
  const result = pending.then(operation)
  pending = result.catch(() => undefined)
  return result
}

async function storeNative(name: string, value: string) {
  await SecureStorage.set(name, value, false, false, KeychainAccess.whenUnlockedThisDeviceOnly)
}

/** Native: device-bound iOS Keychain / Android Keystore encryption. Web: localStorage. */
export const hybridAuthStorage: StateStorage = {
  getItem: (name) => ordered(async () => {
    if (!Capacitor.isNativePlatform()) return localStorage.getItem(name)
    const value = await SecureStorage.get(name, false, false)
    if (value !== null && typeof value !== "string") throw new Error("Sesión almacenada inválida.")
    if (value !== null) {
      await Preferences.remove({ key: name })
      return value
    }
    const legacy = await Preferences.get({ key: name })
    if (legacy.value !== null) {
      // Preserve the old copy if encryption fails; never fall back to plaintext writes.
      await storeNative(name, legacy.value)
      await Preferences.remove({ key: name })
    }
    return legacy.value
  }),
  setItem: (name, value) => ordered(async () => {
    if (!Capacitor.isNativePlatform()) { localStorage.setItem(name, value); return }
    await storeNative(name, value)
    await Preferences.remove({ key: name })
  }),
  removeItem: (name) => ordered(async () => {
    if (!Capacitor.isNativePlatform()) { localStorage.removeItem(name); return }
    await SecureStorage.remove(name, false)
    await Preferences.remove({ key: name })
  }),
}
