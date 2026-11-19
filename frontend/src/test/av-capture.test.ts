import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  assembleVoiceRequest,
  createFrameSampler,
  createMicrophoneRecorder,
  downsample,
  frameEvidence,
  type TimedFrame,
} from "@/services/av-capture"

const frames = (count: number, stepMs: number, startedAt = 1000): TimedFrame[] =>
  Array.from({ length: count }, (_, index) => ({ at: startedAt + index * stepMs, image: `f${index}` }))
const mouth = (count: number, stepMs: number) =>
  Array.from({ length: count }, (_, index) => ({ t_ms: index * stepMs, mouth_open: 0.2 }))
const audio = (seconds: number) => new Array<number>(seconds * 16_000).fill(0.01)

describe("frameEvidence", () => {
  it("returns offsets from the recording start, inside the audio and at least 40 ms apart", () => {
    const stamped = [...frames(30, 30), { at: 1000 + 5000, image: "after-audio" }]
    const wire = frameEvidence(stamped, 1000, 1000)
    expect(wire[0]).toEqual({ t_ms: 0, image: "f0" })
    expect(wire.every((frame) => frame.t_ms >= 0 && frame.t_ms <= 1000)).toBe(true)
    expect(wire.every((frame, index) => index === 0 || frame.t_ms - wire[index - 1].t_ms >= 40)).toBe(true)
    expect(wire.map((frame) => frame.image)).not.toContain("after-audio")
  })

  it("drops frames captured before the recording started and never exceeds 130 frames", () => {
    const wire = frameEvidence([{ at: 900, image: "early" }, ...frames(400, 45)], 1000, 12_000)
    expect(wire.map((frame) => frame.image)).not.toContain("early")
    expect(wire.length).toBeLessThanOrEqual(130)
    expect(wire.every((frame, index) => index === 0 || frame.t_ms - wire[index - 1].t_ms >= 40)).toBe(true)
  })
})

describe("assembleVoiceRequest", () => {
  const recording = { samples: audio(9), startedAt: 1000 }

  it("builds the B payload: ambient_ms, audio, mouth samples and 20-130 server frames", () => {
    const request = assembleVoiceRequest(recording, frames(70, 125), mouth(60, 140), 2000)
    expect(request.ambient_ms).toBe(2000)
    expect(request.audio_samples).toHaveLength(144_000)
    expect(request.frames).toHaveLength(70)
    expect(request.frames[1]).toEqual({ t_ms: 125, image: "f1" })
    expect(request.mouth_samples).toHaveLength(60)
  })

  it("drops mouth samples that fall outside the audio and keeps the spacing of at least 30 ms", () => {
    const request = assembleVoiceRequest(recording, frames(70, 125), [...mouth(40, 140), { t_ms: 9500, mouth_open: 0.3 }], 2000)
    expect(request.mouth_samples.every((sample) => sample.t_ms <= 9000)).toBe(true)
    expect(request.mouth_samples.every((sample, index) => index === 0 || sample.t_ms - request.mouth_samples[index - 1].t_ms >= 30)).toBe(true)
  })

  it("rejects with a Spanish message when fewer than 20 frames were captured", () => {
    expect(() => assembleVoiceRequest(recording, frames(19, 125), mouth(60, 140), 2000)).toThrow(/video/i)
  })

  it("rejects frames above the 80000 character limit instead of sending them", () => {
    const heavy = frames(70, 125).map((frame, index) => (index === 3 ? { ...frame, image: "x".repeat(80_001) } : frame))
    expect(() => assembleVoiceRequest(recording, heavy, mouth(60, 140), 2000)).toThrow(/demasiado grande/)
  })
})

describe("downsample", () => {
  it("averages blocks down to 16 kHz and clamps to [-1, 1]", () => {
    const input = new Float32Array(480).fill(0.5)
    input[0] = 4
    const out = downsample(input, 3)
    expect(out).toHaveLength(160)
    expect(out[0]).toBe(1)
    expect(out[1]).toBeCloseTo(0.5)
  })
})

describe("createFrameSampler", () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it("captures on one clock until stopped and stops the timer on stop", () => {
    let counter = 0
    const capture = vi.fn(() => `img${counter++}`)
    const sampler = createFrameSampler(capture, 100)
    sampler.start()
    vi.advanceTimersByTime(1000)
    const taken = sampler.stop()
    expect(taken.length).toBeGreaterThanOrEqual(10)
    expect(taken[0].at).toBeLessThanOrEqual(taken[1].at)
    const calls = capture.mock.calls.length
    vi.advanceTimersByTime(1000)
    expect(capture.mock.calls.length).toBe(calls)
    expect(vi.getTimerCount()).toBe(0)
  })

  it("skips null frames and clears everything on dispose", () => {
    const sampler = createFrameSampler(() => null, 100)
    sampler.start()
    vi.advanceTimersByTime(500)
    sampler.dispose()
    expect(sampler.stop()).toEqual([])
    expect(vi.getTimerCount()).toBe(0)
  })
})

describe("createMicrophoneRecorder", () => {
  type Processing = { inputBuffer: { getChannelData: () => Float32Array }; outputBuffer: { getChannelData: () => Float32Array } }
  const processors: { onaudioprocess: ((event: Processing) => void) | null; connect: ReturnType<typeof vi.fn>; disconnect: ReturnType<typeof vi.fn> }[] = []
  const close = vi.fn().mockResolvedValue(undefined)
  const sourceDisconnect = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    processors.length = 0
    vi.stubGlobal("AudioContext", class {
      sampleRate = 48000
      state = "running"
      destination = {}
      resume = async () => {}
      close = close
      createMediaStreamSource = () => ({ connect: vi.fn(), disconnect: sourceDisconnect })
      createScriptProcessor = () => {
        const processor = { onaudioprocess: null as ((event: Processing) => void) | null, connect: vi.fn(), disconnect: vi.fn() }
        processors.push(processor)
        return processor
      }
    })
  })
  afterEach(() => vi.unstubAllGlobals())

  const feed = (value: number) => {
    const output = new Float32Array(4096).fill(1)
    processors.at(-1)!.onaudioprocess?.({
      inputBuffer: { getChannelData: () => new Float32Array(4096).fill(value) },
      outputBuffer: { getChannelData: () => output },
    })
    return output
  }

  it("records 16 kHz samples between start and stop with the epoch of the first sample, never playing back", async () => {
    const recorder = await createMicrophoneRecorder({} as MediaStream)
    recorder.start()
    const output = feed(0.25)
    feed(0.25)
    const taken = recorder.stop()
    expect(output.every((sample) => sample === 0)).toBe(true)
    expect(taken?.samples).toHaveLength(2 * Math.floor(4096 / 3))
    expect(taken?.samples[0]).toBeCloseTo(0.25)
    expect(taken?.startedAt).toBeGreaterThan(0)
    expect(processors[0].onaudioprocess).toBeNull()
    expect(processors[0].disconnect).toHaveBeenCalled()
  })

  it("releases the processor and the AudioContext on close, even while recording", async () => {
    const recorder = await createMicrophoneRecorder({} as MediaStream)
    recorder.start()
    await recorder.close()
    expect(processors[0].onaudioprocess).toBeNull()
    expect(sourceDisconnect).toHaveBeenCalled()
    expect(close).toHaveBeenCalledOnce()
    expect(recorder.stop()).toBeNull()
  })
})
