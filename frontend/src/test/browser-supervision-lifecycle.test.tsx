import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { BrowserSupervisionPage } from "@/pages/browser-supervision-page"
import { useAuthStore } from "@/stores/auth-store"
import * as api from "@/services/browser-supervision"
import * as gaze from "@/services/gaze-tracking"
import { stubMedia } from "@/test/av-test-support"

vi.mock("@/services/browser-supervision", async (original) => {
  const actual = await original<typeof import("@/services/browser-supervision")>()
  return {
    ...actual,
    startBrowserTrial: vi.fn(), readBrowserTrial: vi.fn(), trialAction: vi.fn(), sendBrowserIncidents: vi.fn(),
    readBrowserLedger: vi.fn(), sendAVWindow: vi.fn(),
  }
})
vi.mock("@/services/gaze-tracking", async (original) => {
  const actual = await original<typeof import("@/services/gaze-tracking")>()
  return { ...actual, startFaceTracker: vi.fn() }
})

const zone: gaze.GazeZone = {
  pitch_min: -9, pitch_max: 13, yaw_min: -13, yaw_max: 13, gaze_h_min: -0.65, gaze_h_max: 0.65, gaze_v_min: -0.45, gaze_v_max: 0.55,
}
/** A trial seeded from a valid pre-exam calibration: supervision may start right away. */
const trial: api.Trial = {
  id: "17008646-a5fd-42aa-9e60-4a42266fc6de", mode: "TRIAL", created_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 86_400_000).toISOString(), closed_at: null,
  lease_until: new Date(Date.now() + 20_000).toISOString(), event_count: 0, gaze_zone: zone, voice_enrolled: true,
}
const tracker = { setZone: vi.fn(), takeSamples: vi.fn(() => []), takeMouthSamples: vi.fn(() => []), stop: vi.fn() }

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  useAuthStore.setState({
    user: { id: "member", fullName: "Member", email: "member@example.test", role: "MEMBER" } as NonNullable<
      ReturnType<typeof useAuthStore.getState>["user"]
    >,
  })
  vi.mocked(gaze.startFaceTracker).mockResolvedValue(tracker)
  vi.mocked(api.startBrowserTrial).mockResolvedValue({ trial, message: "Sesión de prueba preparada." })
  vi.mocked(api.trialAction).mockImplementation(async () => ({ trial, message: "ok" }))
  vi.mocked(api.readBrowserLedger).mockResolvedValue({ statuscode: 200, message: "ok", data: [], count: 0 })
  vi.mocked(api.sendBrowserIncidents).mockImplementation(async (_id, _tab, events) => ({
    accepted_ids: events.map((row) => row.event_id), event_count: events.length,
  }))
  vi.mocked(api.sendAVWindow).mockResolvedValue({
    window_id: "w", face_count: 1, head_orientation: "CENTER", identity_match: true, speech_detected: false,
    noise_level: 0.02, anomalies: [], incidents_created: [],
  })
})
afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

const show = () => render(<MemoryRouter><BrowserSupervisionPage /></MemoryRouter>)
const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms) })
function press() {
  fireEvent.click(screen.getByRole("checkbox", { name: /Acepto los controles/ }))
  fireEvent.click(screen.getByRole("button", { name: "Activar prueba" }))
}
async function activate() {
  press()
  await waitFor(() => expect(screen.getByRole("textbox", { name: "Área supervisada" })).not.toBeDisabled())
  await waitFor(() => expect(gaze.startFaceTracker).toHaveBeenCalled())
}

it("releases tracks, the AudioContext and the face tracker when the lease cannot be renewed", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const media = stubMedia()
  show()
  await activate()
  expect(media.contexts).toHaveLength(1)
  vi.mocked(api.trialAction).mockRejectedValue(new Error("Esta prueba perdió su autorización."))
  await advance(5000)
  expect(screen.getByRole("textbox", { name: "Área supervisada" })).toBeDisabled()
  expect(screen.getByRole("alert")).toHaveTextContent("Esta prueba perdió su autorización.")
  expect(media.stops).toHaveBeenCalledTimes(2)
  expect(media.contexts[0].close).toHaveBeenCalled()
  expect(tracker.stop).toHaveBeenCalled()
  const sent = vi.mocked(api.sendAVWindow).mock.calls.length
  await advance(12_000)
  expect(vi.mocked(api.sendAVWindow).mock.calls.length).toBe(sent)
})

it("releases the capture when the lease watchdog expires without a confirmation", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const media = stubMedia()
  show()
  await activate()
  vi.mocked(api.trialAction).mockImplementation(() => new Promise(() => undefined)) // heartbeat never answers
  await advance(16_000)
  expect(screen.getByRole("alert")).toHaveTextContent("Autorización de pestaña sin confirmar")
  expect(media.stops).toHaveBeenCalledTimes(2)
  expect(media.contexts[0].close).toHaveBeenCalled()
})

it("stops a stream that arrives after the page was unmounted and never posts a window", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const media = stubMedia({ deferredStream: true })
  const view = show()
  press()
  await waitFor(() => expect(media.getUserMedia).toHaveBeenCalled())
  view.unmount()
  await act(async () => { media.resolveStream() })
  await advance(100)
  expect(media.stops).toHaveBeenCalledTimes(2)
  expect(media.contexts).toHaveLength(0)
  expect(gaze.startFaceTracker).not.toHaveBeenCalled()
  await advance(12_000)
  expect(api.sendAVWindow).not.toHaveBeenCalled()
})

it("closes an audio pipeline that finishes building after unmount", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const media = stubMedia({ deferredResume: true })
  const view = show()
  press()
  await waitFor(() => expect(media.contexts).toHaveLength(1))
  view.unmount()
  await act(async () => { media.resolveResume() })
  await advance(100)
  expect(media.stops).toHaveBeenCalledTimes(2)
  expect(media.contexts[0].close).toHaveBeenCalled()
  await advance(12_000)
  expect(api.sendAVWindow).not.toHaveBeenCalled()
})

it("stops a face tracker that finishes loading after unmount", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  stubMedia()
  let finish: (value: typeof tracker) => void = () => undefined
  vi.mocked(gaze.startFaceTracker).mockImplementation(() => new Promise((resolve) => { finish = resolve }))
  const view = show()
  press()
  await waitFor(() => expect(gaze.startFaceTracker).toHaveBeenCalled())
  view.unmount()
  await act(async () => { finish(tracker) })
  expect(tracker.stop).toHaveBeenCalled()
})
