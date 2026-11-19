import { describe, expect, it } from "vitest"
import { isBrowserSupervisionTrialEnabled } from "@/lib/feature-flags"

describe("isBrowserSupervisionTrialEnabled", () => {
  it.each([
    [{ DEV: true, VITE_APP_ENV: "production", VITE_BROWSER_SUPERVISION_TRIAL: "true" }, false],
    [{ DEV: false, VITE_APP_ENV: "production" }, false],
    [{ DEV: true, VITE_APP_ENV: "production" }, false],
    [{ DEV: true }, true],
    [{ DEV: false }, false],
    [{ DEV: false, VITE_APP_ENV: "staging" }, false],
    [{ DEV: false, VITE_APP_ENV: "staging", VITE_BROWSER_SUPERVISION_TRIAL: "true" }, true],
    [{ DEV: true, VITE_BROWSER_SUPERVISION_TRIAL: "false" }, false],
    [{ DEV: true, VITE_BROWSER_SUPERVISION_TRIAL: "" }, true],
  ])("%j -> %s", (env, expected) => {
    expect(isBrowserSupervisionTrialEnabled(env)).toBe(expected)
  })
})
