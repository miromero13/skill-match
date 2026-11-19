import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { captureCalibrationEvidence } from "@/services/calibration-capture"

const drawImage = vi.fn()
const toDataURL = vi.fn()

beforeEach(() => {
  vi.useFakeTimers()
  drawImage.mockClear()
  toDataURL.mockReset().mockReturnValue("data:image/jpeg;base64,captured-frame")
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ drawImage } as unknown as CanvasRenderingContext2D)
  vi.spyOn(HTMLCanvasElement.prototype, "toDataURL").mockImplementation(toDataURL)
})
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })

function camera() {
  const video = document.createElement("video")
  Object.defineProperties(video, { videoWidth: { value: 640 }, videoHeight: { value: 480 } })
  return video
}

describe("calibration capture guidance", () => {
  it("captures slower motion then automatically records quiet background and prompted speech", async () => {
    const phases: { phase: string; frames: number; time: number }[] = []
    const started = Date.now()
    const video = camera()
    const record = vi.fn().mockImplementation(async (_milliseconds: number, _signal: AbortSignal, onClock?: (seconds: number) => void) => {
      if (!onClock) {
        await new Promise(resolve => setTimeout(resolve, 3000))
        return Array(48000).fill(0) as number[]
      }
      for (let tick = 1; tick <= 80; tick++) {
        await new Promise(resolve => setTimeout(resolve, 100))
        onClock(tick / 10)
      }
      return Array(128000).fill(0.1) as number[]
    })
    const capture = captureCalibrationEvidence(video, { samples: () => [0.1], record, close: async () => {} }, new AbortController().signal,
      phase => phases.push({ phase, frames: drawImage.mock.calls.length, time: Date.now() - started }))
    await vi.runAllTimersAsync()
    const evidence = await capture
    expect(phases).toEqual([
      { phase: "CENTER", frames: 0, time: 0 },
      { phase: "TURN", frames: 4, time: 3000 },
      { phase: "RETURN", frames: 8, time: 7000 },
      { phase: "AMBIENT", frames: 12, time: 11000 },
      { phase: "SPEAK", frames: 12, time: 14000 },
      { phase: "PAUSE", frames: 52, time: 18000 },
    ])
    expect(evidence.frames).toHaveLength(12)
    expect(evidence.ambient_audio_samples).toEqual(Array(48000).fill(0))
    expect(evidence.audio_samples).toEqual(Array(128000).fill(0.1))
    expect(evidence.spoken_frames).toHaveLength(80)
    expect(evidence.spoken_frames[0]).toEqual({ time_ms: 100, image: "data:image/jpeg;base64,captured-frame" })
    expect(evidence.spoken_frames.at(-1)?.time_ms).toBe(8000)
    expect(record).toHaveBeenCalledTimes(2)
    expect(Date.now() - started).toBe(22000)
    expect(drawImage).toHaveBeenCalledWith(video, 0, 0, 640, 480)
    expect(toDataURL).toHaveBeenCalledWith("image/jpeg", 0.65)
  })

  it("still captures without a guidance callback and never uses the old loudest-sample shortcut", async () => {
    const samples = vi.fn(() => [1])
    const record = vi.fn().mockImplementation(async (_milliseconds: number, _signal: AbortSignal, onClock?: (seconds: number) => void) => {
      if (onClock) for (let tick = 1; tick <= 80; tick++) onClock(tick / 10)
      return onClock ? [0.1] : [0]
    })
    const capture = captureCalibrationEvidence(camera(), { samples, record, close: async () => {} }, new AbortController().signal)
    await vi.runAllTimersAsync()
    const evidence = await capture
    expect(evidence.frames).toEqual(Array(12).fill("data:image/jpeg;base64,captured-frame"))
    expect(evidence.ambient_audio_samples).toEqual([0])
    expect(evidence.audio_samples).toEqual([0.1])
    expect(evidence.spoken_frames).toHaveLength(80)
    expect(drawImage).toHaveBeenCalledTimes(92)
    expect(samples).not.toHaveBeenCalled()
  })

  it("aborts motion without starting microphone recording", async () => {
    const controller = new AbortController()
    const record = vi.fn()
    const capture = captureCalibrationEvidence(camera(), { samples: () => [], record, close: async () => {} }, controller.signal,
      phase => { if (phase === "TURN") controller.abort() })
    const rejected = expect(capture).rejects.toMatchObject({ name: "AbortError" })
    await vi.runAllTimersAsync()
    await rejected
    expect(record).not.toHaveBeenCalled()
    expect(drawImage).toHaveBeenCalledTimes(4)
  })
})
