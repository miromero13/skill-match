import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { createMicrophoneMonitor } from "@/services/calibration-capture"

type Processing = { playbackTime: number; inputBuffer: { getChannelData: () => Float32Array }; outputBuffer: { getChannelData: () => Float32Array } }
const processors: { onaudioprocess: ((event: Processing) => void) | null; connect: ReturnType<typeof vi.fn>; disconnect: ReturnType<typeof vi.fn> }[] = []
const close = vi.fn().mockResolvedValue(undefined)
const disconnect = vi.fn()

beforeEach(() => {
  vi.useFakeTimers(); vi.clearAllMocks(); processors.length = 0
  vi.stubGlobal("AudioContext", class {
    sampleRate = 48000
    state = "running"
    destination = {}
    resume = async () => {}
    close = close
    createMediaStreamSource = () => ({ connect: vi.fn(), disconnect })
    createAnalyser = () => ({ fftSize: 0, getFloatTimeDomainData: vi.fn() })
    createScriptProcessor = () => {
      const processor = { onaudioprocess: null as ((event: Processing) => void) | null, connect: vi.fn(), disconnect: vi.fn() }
      processors.push(processor)
      return processor
    }
  })
})
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

function feed(value: number) {
  for (let frame = 0; frame < 35; frame++) {
    const output = new Float32Array(4096).fill(1)
    processors.at(-1)!.onaudioprocess?.({
      playbackTime: frame * 4096 / 48000,
      inputBuffer: { getChannelData: () => new Float32Array(4096).fill(value) },
      outputBuffer: { getChannelData: () => output },
    })
    expect(output.every(sample => sample === 0)).toBe(true)
  }
}

describe("microphone recording windows", () => {
  it("records separate 16kHz windows and never plays the microphone back", async () => {
    const monitor = await createMicrophoneMonitor({} as MediaStream)
    const clock = vi.fn()
    const first = monitor.record!(3000, new AbortController().signal, clock)
    feed(0)
    await vi.advanceTimersByTimeAsync(3000)
    const quiet = await first
    const second = monitor.record!(3000, new AbortController().signal)
    feed(0.1)
    await vi.advanceTimersByTimeAsync(3000)
    const spoken = await second
    expect(clock).toHaveBeenCalledTimes(35)
    expect(clock.mock.calls[0][0]).toBeCloseTo(4096 / 48000)
    expect(clock.mock.calls.at(-1)?.[0]).toBeCloseTo(35 * 4096 / 48000)
    expect(quiet).toHaveLength(47786)
    expect(quiet.every(sample => sample === 0)).toBe(true)
    expect(spoken).toHaveLength(47786)
    expect(spoken[0]).toBeCloseTo(0.1)
    expect(processors.every(processor => processor.onaudioprocess === null)).toBe(true)
    await monitor.close()
    expect(close).toHaveBeenCalledOnce()
  })

  it.each(["abort", "close"])("cancels recording on %s without leaving audio callbacks", async operation => {
    const monitor = await createMicrophoneMonitor({} as MediaStream)
    const controller = new AbortController()
    const record = monitor.record!(3000, controller.signal)
    const rejected = expect(record).rejects.toMatchObject({ name: "AbortError" })
    if (operation === "abort") controller.abort()
    else await monitor.close()
    await rejected
    await vi.runAllTimersAsync()
    expect(processors[0].onaudioprocess).toBeNull()
    expect(processors[0].disconnect).toHaveBeenCalledOnce()
    expect(disconnect).toHaveBeenCalled()
    if (operation === "abort") await monitor.close()
  })
})
