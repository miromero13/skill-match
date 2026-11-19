import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { AUDIO_RATE, createAudioCapture, createRecorder } from "@/services/av-capture"

type Processing = { inputBuffer: { getChannelData: () => Float32Array }; outputBuffer: { getChannelData: () => Float32Array } }
interface FakeNode { port: { onmessage: ((event: { data: Float32Array }) => void) | null }; connect: ReturnType<typeof vi.fn>; disconnect: ReturnType<typeof vi.fn> }
interface FakeProcessor { onaudioprocess: ((event: Processing) => void) | null; connect: ReturnType<typeof vi.fn>; disconnect: ReturnType<typeof vi.fn> }

const nodes: FakeNode[] = []
const processors: FakeProcessor[] = []
const close = vi.fn().mockResolvedValue(undefined)
const addModule = vi.fn()
let rate = 48_000
let withWorklet = true

beforeEach(() => {
  vi.clearAllMocks()
  nodes.length = 0
  processors.length = 0
  rate = 48_000
  withWorklet = true
  addModule.mockResolvedValue(undefined)
  vi.stubGlobal("AudioWorkletNode", class {
    port: FakeNode["port"] = { onmessage: null }
    connect = vi.fn()
    disconnect = vi.fn()
    constructor() { nodes.push(this) }
  })
  vi.stubGlobal("AudioContext", class {
    sampleRate = rate
    state = "running"
    destination = {}
    audioWorklet = withWorklet ? { addModule } : undefined
    resume = async () => {}
    close = close
    createGain = () => ({ gain: { value: 1 }, connect: vi.fn(), disconnect: vi.fn() })
    createMediaStreamSource = () => ({ connect: vi.fn(), disconnect: vi.fn() })
    createScriptProcessor = () => {
      const processor: FakeProcessor = { onaudioprocess: null, connect: vi.fn(), disconnect: vi.fn() }
      processors.push(processor)
      return processor
    }
  })
})
afterEach(() => vi.unstubAllGlobals())

const tone = (frequency: number, count: number, from = 0) =>
  Float32Array.from({ length: count }, (_, index) => 0.5 * Math.sin((2 * Math.PI * frequency * (from + index)) / rate))

function collect(capture: Awaited<ReturnType<typeof createAudioCapture>>) {
  const got: number[] = []
  capture.subscribe((samples) => got.push(...samples))
  return got
}

function peakAt(samples: number[], frequency: number) {
  const from = 1600
  const to = samples.length - 1600
  let a = 0
  let b = 0
  for (let index = from; index < to; index++) {
    a += samples[index] * Math.sin((2 * Math.PI * frequency * index) / AUDIO_RATE)
    b += samples[index] * Math.cos((2 * Math.PI * frequency * index) / AUDIO_RATE)
  }
  return (2 * Math.hypot(a, b)) / (to - from)
}

describe("createAudioCapture", () => {
  it("uses an AudioWorklet module and delivers 16 kHz samples from a 48 kHz context", async () => {
    const capture = await createAudioCapture({} as MediaStream)
    expect(capture.mode).toBe("worklet")
    expect(addModule).toHaveBeenCalledWith("/worklets/capture-processor.js")
    const got = collect(capture)
    for (let block = 0; block < 375; block++) nodes[0].port.onmessage?.({ data: tone(1000, 128, block * 128) })
    expect(Math.abs(got.length - 16_000)).toBeLessThan(80)
    expect(peakAt(got, 1000)).toBeGreaterThan(0.48)
    await capture.close()
  })

  it("falls back to a ScriptProcessor only when the module cannot load, behind the same interface", async () => {
    addModule.mockRejectedValue(new Error("blocked"))
    const capture = await createAudioCapture({} as MediaStream)
    expect(capture.mode).toBe("script-processor")
    const got = collect(capture)
    processors[0].onaudioprocess?.({ inputBuffer: { getChannelData: () => tone(1000, 4096) }, outputBuffer: { getChannelData: () => new Float32Array(4096) } })
    expect(got.length).toBeGreaterThan(1000)
    await capture.close()
  })

  it("never emits samples at the wrong rate from the fallback at 44.1 kHz", async () => {
    rate = 44_100
    withWorklet = false
    const capture = await createAudioCapture({} as MediaStream)
    expect(capture.mode).toBe("script-processor")
    const got = collect(capture)
    let produced = 0
    for (let block = 0; block < 44_100 / 1024; block++) {
      const output = new Float32Array(1024).fill(1)
      processors[0].onaudioprocess?.({ inputBuffer: { getChannelData: () => tone(1000, 1024, block * 1024) }, outputBuffer: { getChannelData: () => output } })
      expect(output.every((sample) => sample === 0)).toBe(true)
      produced += 1024
    }
    expect(produced).toBeGreaterThan(44_000)
    expect(Math.abs(got.length - (produced * AUDIO_RATE) / 44_100)).toBeLessThan(40) // 16 kHz, not the native 44.1 kHz
    expect(peakAt(got, 1000)).toBeGreaterThan(0.48)
    expect(got.every((value) => value >= -1 && value <= 1)).toBe(true)
    await capture.close()
  })

  it("releases the nodes and the context on close and ignores audio that arrives afterwards", async () => {
    const capture = await createAudioCapture({} as MediaStream)
    const got = collect(capture)
    await capture.close()
    await capture.close()
    expect(nodes[0].disconnect).toHaveBeenCalled()
    expect(nodes[0].port.onmessage).toBeNull()
    expect(close).toHaveBeenCalledOnce()
    nodes[0].port.onmessage?.({ data: tone(1000, 1024) })
    expect(got).toHaveLength(0)
  })

  it("closes the context when the pipeline cannot be built", async () => {
    addModule.mockRejectedValue(new Error("blocked"))
    vi.stubGlobal("AudioContext", class {
      sampleRate = 48_000
      state = "running"
      audioWorklet = { addModule }
      resume = async () => {}
      close = close
      createMediaStreamSource = () => { throw new Error("no stream") }
    })
    await expect(createAudioCapture({} as MediaStream)).rejects.toThrow("no stream")
    expect(close).toHaveBeenCalledOnce()
  })
})

describe("createRecorder", () => {
  it("records between start and stop on the epoch clock and stops growing at 12 s", async () => {
    const capture = await createAudioCapture({} as MediaStream)
    const recorder = createRecorder(capture)
    expect(recorder.stop()).toBeNull()
    recorder.start()
    for (let block = 0; block < 1500; block++) nodes[0].port.onmessage?.({ data: tone(300, 480, block * 480) })
    const taken = recorder.stop()
    expect(taken?.startedAt).toBeGreaterThan(0)
    expect(taken?.samples.length).toBeLessThanOrEqual(AUDIO_RATE * 12)
    expect(taken?.samples.length).toBeGreaterThan(AUDIO_RATE * 11.9)
    await capture.close()
  })
})
