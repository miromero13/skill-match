import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { createMicrophoneRecorder } from "@/services/av-capture"

type Processing = { inputBuffer: { getChannelData: () => Float32Array }; outputBuffer: { getChannelData: () => Float32Array } }
const processors: { onaudioprocess: ((event: Processing) => void) | null; connect: ReturnType<typeof vi.fn>; disconnect: ReturnType<typeof vi.fn> }[] = []
const close = vi.fn().mockResolvedValue(undefined)

beforeEach(() => {
  vi.clearAllMocks(); processors.length = 0
  vi.stubGlobal("AudioContext", class {
    sampleRate = 48000
    state = "running"
    destination = {}
    resume = async () => {}
    close = close
    createMediaStreamSource = () => ({ connect: vi.fn(), disconnect: vi.fn() })
    createScriptProcessor = () => {
      const processor = { onaudioprocess: null as ((event: Processing) => void) | null, connect: vi.fn(), disconnect: vi.fn() }
      processors.push(processor)
      return processor
    }
  })
})
afterEach(() => vi.unstubAllGlobals())

function feed(value: number, blocks: number) {
  for (let block = 0; block < blocks; block++) {
    const output = new Float32Array(4096).fill(1)
    processors.at(-1)!.onaudioprocess?.({
      inputBuffer: { getChannelData: () => new Float32Array(4096).fill(value) },
      outputBuffer: { getChannelData: () => output },
    })
    expect(output.every(sample => sample === 0)).toBe(true) // the microphone is never played back
  }
}

describe("microphone recorder", () => {
  it("records each window separately at 16 kHz from a 48 kHz context", async () => {
    const recorder = await createMicrophoneRecorder({} as MediaStream)
    recorder.start(); feed(0, 35)
    const quiet = recorder.stop()
    recorder.start(); feed(0.1, 35)
    const spoken = recorder.stop()
    expect(quiet?.samples).toHaveLength(35 * Math.floor(4096 / 3))
    expect(quiet?.samples.every(sample => sample === 0)).toBe(true)
    expect(spoken?.samples).toHaveLength(35 * Math.floor(4096 / 3))
    expect(spoken?.samples[0]).toBeCloseTo(0.1)
    expect(processors.every(processor => processor.onaudioprocess === null)).toBe(true)
    await recorder.close()
    expect(close).toHaveBeenCalledOnce()
  })

  it("stops growing at 12 seconds and returns null when it was never started", async () => {
    const recorder = await createMicrophoneRecorder({} as MediaStream)
    expect(recorder.stop()).toBeNull()
    recorder.start(); feed(0.1, 500)
    expect(recorder.stop()?.samples.length).toBeLessThanOrEqual(16_000 * 12 + 1365)
    await recorder.close()
  })

  it("releases the processor and the AudioContext when closed midway", async () => {
    const recorder = await createMicrophoneRecorder({} as MediaStream)
    recorder.start(); feed(0.1, 3)
    await recorder.close()
    expect(processors[0].onaudioprocess).toBeNull()
    expect(processors[0].disconnect).toHaveBeenCalled()
    expect(recorder.stop()).toBeNull()
    expect(close).toHaveBeenCalledOnce()
  })
})
