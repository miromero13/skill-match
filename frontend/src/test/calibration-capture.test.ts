import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { buildCalibrationEvidence, captureLivenessFrames, splitPhraseEvidence } from "@/services/calibration-capture"
import type { GazeCalibrationPoint, GazeTarget, VoiceCalibrationRequest } from "@/services/browser-supervision"

const TARGETS: GazeTarget[] = ["CENTER", "TOP_LEFT", "TOP_RIGHT", "BOTTOM_LEFT", "BOTTOM_RIGHT"]
const gaze = (): GazeCalibrationPoint[] => TARGETS.map((target) => ({ target, frames: ["g1", "g2", "g3"] }))
const liveness = Array.from({ length: 12 }, (_, index) => `l${index}`)

/** 3 s of silence + 8 s of phrase and pause at 16 kHz, 125 ms frames and 70 ms mouth readings from the start. */
function recording(overrides: Partial<VoiceCalibrationRequest> = {}): VoiceCalibrationRequest {
  return {
    audio_samples: new Array<number>(11 * 16_000).fill(0.02),
    ambient_ms: 3000,
    mouth_samples: Array.from({ length: 150 }, (_, index) => ({ t_ms: index * 70, mouth_open: 0.2 })),
    frames: Array.from({ length: 88 }, (_, index) => ({ t_ms: index * 125, image: `s${index}` })),
    ...overrides,
  }
}
const build = (voice = recording(), extra: { cameraLabel?: string; frames?: string[]; gazePoints?: GazeCalibrationPoint[] } = {}) =>
  buildCalibrationEvidence({ challengeId: "c-1", frames: liveness, gazePoints: gaze(), voice, cameraLabel: "Webcam", ...extra })

describe("captureLivenessFrames", () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it("grabs 12 frames one second apart and announces CENTER, TURN and RETURN", async () => {
    const phases: { phase: string; frames: number }[] = []
    let grabbed = 0
    const done = captureLivenessFrames(() => `f${grabbed++}`, new AbortController().signal, (phase) => phases.push({ phase, frames: grabbed }))
    await vi.runAllTimersAsync()
    expect(await done).toHaveLength(12)
    expect(phases).toEqual([{ phase: "CENTER", frames: 0 }, { phase: "TURN", frames: 4 }, { phase: "RETURN", frames: 8 }])
  })

  it("fails with a Spanish message when the camera gives no image and stops when aborted", async () => {
    await expect(captureLivenessFrames(() => null, new AbortController().signal)).rejects.toThrow(/cámara/)
    const controller = new AbortController()
    const done = captureLivenessFrames(() => "f", controller.signal)
    const rejected = expect(done).rejects.toMatchObject({ name: "AbortError" })
    controller.abort()
    await rejected
    expect(vi.getTimerCount()).toBe(0)
  })
})

describe("splitPhraseEvidence", () => {
  it("splits the silence from the phrase and moves frames and mouth readings to the phrase clock", () => {
    const parts = splitPhraseEvidence(recording())
    expect(parts.ambient_audio_samples).toHaveLength(48_000)
    expect(parts.audio_samples).toHaveLength(128_000)
    expect(parts.spoken_frames[0]).toEqual({ time_ms: 0, image: "s24" }) // 24 * 125 ms = 3000 ms
    expect(parts.spoken_frames.at(-1)!.time_ms).toBe(87 * 125 - 3000)
    expect(parts.mouth_samples[0].t_ms).toBeGreaterThanOrEqual(0)
    expect(parts.mouth_samples.every((sample) => sample.t_ms <= 8000)).toBe(true)
  })
})

describe("buildCalibrationEvidence (contract A)", () => {
  it("builds the full payload: movement, five gaze targets once each, silence, phrase, frames and mouth", () => {
    const evidence = build()
    expect(Object.keys(evidence).sort()).toEqual([
      "ambient_audio_samples", "audio_samples", "camera_label", "challenge_id", "frames", "gaze_points", "mouth_samples", "spoken_frames",
    ])
    expect(evidence.challenge_id).toBe("c-1")
    expect(evidence.frames).toHaveLength(12)
    expect(evidence.gaze_points.map((point) => point.target).sort()).toEqual([...TARGETS].sort())
    expect(evidence.ambient_audio_samples).toHaveLength(48_000)
    expect(evidence.audio_samples).toHaveLength(128_000)
    expect(evidence.spoken_frames.length).toBeGreaterThanOrEqual(20)
    expect(evidence.mouth_samples.length).toBeGreaterThanOrEqual(8)
    expect(evidence.mouth_samples.every((sample, index) => index === 0 || sample.t_ms - evidence.mouth_samples[index - 1].t_ms >= 30)).toBe(true)
  })

  it("truncates the camera label to 200 characters", () => {
    expect(build(recording(), { cameraLabel: "x".repeat(300) }).camera_label).toHaveLength(200)
  })

  it.each([
    ["a missing gaze target", { gazePoints: gaze().slice(1) }, /cinco puntos|esquinas/],
    ["a repeated gaze target", { gazePoints: gaze().map((point, index) => (index === 1 ? { ...point, target: "CENTER" as const } : point)) }, /cinco puntos|esquinas/],
    ["a gaze point without frames", { gazePoints: gaze().map((point, index) => (index === 2 ? { ...point, frames: [] } : point)) }, /mirada/i],
    ["fewer than 3 liveness frames", { frames: ["a", "b"] }, /movimiento/i],
    ["a liveness frame over 200000 chars", { frames: [...liveness.slice(1), "x".repeat(200_001)] }, /demasiado grande/],
  ])("rejects %s before sending", (_name, extra, message) => {
    expect(() => build(recording(), extra)).toThrow(message)
  })

  it.each([
    ["too short a phrase segment", recording({ audio_samples: new Array<number>(9 * 16_000).fill(0.02) }), /audio/i],
    ["too few spoken frames", recording({ frames: recording().frames.filter((_, index) => index % 4 === 0) }), /video/i],
    ["a gap over 350 ms between frames", recording({ frames: recording().frames.filter((frame) => frame.t_ms < 6000 || frame.t_ms > 6500) }), /video/i],
    ["fewer than 8 mouth readings", recording({ mouth_samples: recording().mouth_samples.slice(0, 5) }), /boca/i],
    ["a spoken frame over 80000 chars", recording({ frames: recording().frames.map((frame, index) => (index === 50 ? { ...frame, image: "x".repeat(80_001) } : frame)) }), /demasiado grande/],
  ])("rejects %s before sending", (_name, voice, message) => {
    expect(() => build(voice)).toThrow(message)
  })
})
