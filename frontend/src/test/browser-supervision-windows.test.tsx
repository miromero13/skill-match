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
const manyGaze: gaze.GazeSampleDTO[] = Array.from({ length: 100 }, (_, index) => ({
  t_ms: index * 40, head_pitch: 0, head_yaw: 0, gaze_h: 0, gaze_v: 0, blink: false, face_count: 1, mouth_open: 0.1,
}))
const tracker = { setZone: vi.fn(), takeSamples: vi.fn(() => manyGaze), takeMouthSamples: vi.fn(() => []), stop: vi.fn() }

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


const tick = () => advance(400)
const framesOf = (call: number) => vi.mocked(api.sendAVWindow).mock.calls[call][1].frames
const frameNumber = (image: string) => Number(image.split("F")[1])

it("never runs two window requests at once and sends the newest bounded evidence afterwards", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const media = stubMedia()
  let answer: (value: Awaited<ReturnType<typeof api.sendAVWindow>>) => void = () => undefined
  vi.mocked(api.sendAVWindow).mockImplementationOnce(() => new Promise((resolve) => { answer = resolve }))
  show()
  await activate()
  for (let index = 0; index < 8; index++) { media.feed(6400, 0.1); await tick() }
  expect(api.sendAVWindow).toHaveBeenCalledTimes(1)
  for (let index = 0; index < 60; index++) { media.feed(6400, index < 30 ? 0.1 : 0.9); await tick() } // 24 s while in flight
  expect(api.sendAVWindow).toHaveBeenCalledTimes(1)
  await act(async () => {
    answer({ window_id: "w", face_count: 1, head_orientation: "CENTER", identity_match: true, speech_detected: false, noise_level: 0, anomalies: [], incidents_created: [] })
  })
  media.feed(6400, 0.9)
  await tick()
  expect(api.sendAVWindow).toHaveBeenCalledTimes(2)
  const first = vi.mocked(api.sendAVWindow).mock.calls[0][1]
  const second = vi.mocked(api.sendAVWindow).mock.calls[1][1]
  expect(first.frames.length).toBeLessThanOrEqual(12)
  expect(second.frames.length).toBeLessThanOrEqual(12)
  expect(second.audio_samples?.length ?? 0).toBeLessThanOrEqual(160_000)
  expect(second.audio_samples?.every((value) => Math.abs(value - 0.9) < 1e-6)).toBe(true) // the newest 10 s, not the oldest
  expect(second.duration_ms).toBeLessThanOrEqual(30_000)
  expect(second.gaze_samples?.length ?? 0).toBeLessThanOrEqual(60)
  const lastOfFirst = frameNumber(framesOf(0).at(-1)!)
  expect(frameNumber(framesOf(1).at(-1)!)).toBeGreaterThan(lastOfFirst + 20) // evidence from after the long wait
  expect(frameNumber(framesOf(1)[0])).toBeGreaterThan(lastOfFirst + 20) // no backlog of old frames
})

it("bounds the gaze telemetry of a window to what the server accepts", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const media = stubMedia()
  show()
  await activate()
  for (let index = 0; index < 8; index++) { media.feed(6400, 0.1); await tick() }
  expect(vi.mocked(api.sendAVWindow).mock.calls[0][1].gaze_samples?.length).toBeLessThanOrEqual(60)
})

it("does not use the analyser as audio: no native-rate samples reach the 16 kHz window", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const media = stubMedia({ rate: 48_000 })
  media.analyserFill.value = (target) => target.fill(0.3)
  show()
  await activate()
  for (let index = 0; index < 8; index++) await tick() // the processor never delivers anything
  expect(api.sendAVWindow).toHaveBeenCalled()
  const payload = vi.mocked(api.sendAVWindow).mock.calls[0][1]
  expect(payload.audio_samples ?? []).toEqual([])
})

it("converts a 48 kHz microphone to 16 kHz before it reaches the window", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const media = stubMedia({ rate: 48_000 })
  show()
  await activate()
  for (let index = 0; index < 8; index++) { media.feed(19_200, 0.4); await tick() } // 0.4 s of audio per tick
  const payload = vi.mocked(api.sendAVWindow).mock.calls[0][1]
  const seconds = (payload.audio_samples?.length ?? 0) / 16_000
  expect(Math.abs(seconds - payload.duration_ms / 1000)).toBeLessThan(0.05)
  expect(payload.audio_samples?.at(-1)).toBeCloseTo(0.4, 2)
})
