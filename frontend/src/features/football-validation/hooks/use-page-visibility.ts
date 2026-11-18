import { useEffect } from "react"
import type { ClientAntiFraudEvent } from "./use-challenge-socket"

export function usePageVisibility(
  enabled: boolean,
  onAntiFraudEvent: (event: ClientAntiFraudEvent) => void
) {
  useEffect(() => {
    if (!enabled || typeof document === "undefined") return

    const handleVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        onAntiFraudEvent("tab_hidden")
      }
    }

    const handleWindowBlur = () => {
      onAntiFraudEvent("focus_lost")
    }

    const handleFullscreenChange = () => {
      if (!document.fullscreenElement) {
        onAntiFraudEvent("fullscreen_exit")
      }
    }

    document.addEventListener("visibilitychange", handleVisibilityChange)
    window.addEventListener("blur", handleWindowBlur)
    document.addEventListener("fullscreenchange", handleFullscreenChange)

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange)
      window.removeEventListener("blur", handleWindowBlur)
      document.removeEventListener("fullscreenchange", handleFullscreenChange)
    }
  }, [enabled, onAntiFraudEvent])
}
