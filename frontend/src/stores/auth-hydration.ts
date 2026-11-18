import { useSyncExternalStore } from "react"

type Hydration = "loading" | "ready" | "error"
let status: Hydration = "loading"
const listeners = new Set<() => void>()
const subscribe = (listener: () => void) => {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}
function publish(next: Hydration) {
  status = next
  listeners.forEach((listener) => listener())
}

/** Zustand also calls this completion on a secure-storage error; never unlock routes early. */
export function onAuthRehydrate() {
  publish("loading")
  return (_state: unknown, error?: unknown) => publish(error ? "error" : "ready")
}
export function useAuthHydration(): Hydration {
  return useSyncExternalStore(subscribe, () => status, () => "loading")
}
