export interface BrowserSupervisionTrialEnv {
  DEV: boolean
  VITE_APP_ENV?: string
  VITE_BROWSER_SUPERVISION_TRIAL?: string
}

/** Trial-only SM-43 page: never in production; explicit flag wins; otherwise dev builds only. */
export function isBrowserSupervisionTrialEnabled(env: BrowserSupervisionTrialEnv): boolean {
  if (env.VITE_APP_ENV === "production") return false
  if (env.VITE_BROWSER_SUPERVISION_TRIAL === "true") return true
  if (env.VITE_BROWSER_SUPERVISION_TRIAL === "false") return false
  return env.DEV
}

export const browserSupervisionTrialEnabled = isBrowserSupervisionTrialEnabled(import.meta.env)
