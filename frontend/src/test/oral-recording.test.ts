import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { pcmWave, startOralRecording } from "@/services/oral-recording"

const stop = vi.fn()
const close = vi.fn(async () => undefined)
const disconnect = vi.fn()
let processor: { onaudioprocess: ((event: { inputBuffer: { getChannelData: () => Float32Array }; outputBuffer: { getChannelData: () => Float32Array }; playbackTime: number }) => void) | null; connect: ReturnType<typeof vi.fn>; disconnect: ReturnType<typeof vi.fn> }
let track: { readyState: string; stop: typeof stop; addEventListener: ReturnType<typeof vi.fn>; removeEventListener: ReturnType<typeof vi.fn> }
beforeEach(() => {
  vi.useFakeTimers()
  stop.mockReset(); close.mockClear(); disconnect.mockReset()
  processor = { onaudioprocess: null, connect: vi.fn(), disconnect: vi.fn() }
  track = { readyState: "live", stop, addEventListener: vi.fn(), removeEventListener: vi.fn() }
  vi.stubGlobal("navigator", { mediaDevices: { getUserMedia: vi.fn(async () => ({ getTracks: () => [track], getAudioTracks: () => [track] })) } })
  vi.stubGlobal("AudioContext", class {
    sampleRate = 48000
    state = "running"
    destination = {}
    resume = async () => undefined
    close = close
    createMediaStreamSource = () => ({ connect: vi.fn(), disconnect })
    createScriptProcessor = () => processor
  })
})
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })
it("encodes mono16k PCM with exact WAV header and signed sample bounds", () => {
  const wav = pcmWave(new Float32Array([-1, 0, 1]))
  const view = new DataView(wav.buffer)
  expect(wav.byteLength).toBe(50)
  expect(new TextDecoder().decode(wav.subarray(0, 4))).toBe("RIFF")
  expect(view.getUint32(4, true)).toBe(42)
  expect(view.getUint16(22, true)).toBe(1)
  expect(view.getUint32(24, true)).toBe(16000)
  expect(view.getUint16(34, true)).toBe(16)
  expect(view.getUint32(40, true)).toBe(6)
  expect([44, 46, 48].map(offset => view.getInt16(offset, true))).toEqual([-32768, 0, 32767])
})
it("captures real PCM callbacks, resamples and releases devices on stop", async () => {
  const recording = await startOralRecording(new AbortController().signal)
  processor.onaudioprocess?.({ inputBuffer: { getChannelData: () => new Float32Array(4800).fill(.5) },
    outputBuffer: { getChannelData: () => new Float32Array(4800) }, playbackTime: 0 })
  const encoded = await recording.stop()
  const bytes = Uint8Array.from(atob(encoded), value => value.charCodeAt(0))
  expect(bytes.byteLength).toBe(44 + 1600 * 2)
  expect(stop).toHaveBeenCalledTimes(1)
  expect(close).toHaveBeenCalledTimes(1)
  expect(processor.onaudioprocess).toBeNull()
})
it("cancels and releases the microphone without a response payload", async () => {
  const controller = new AbortController()
  const recording = await startOralRecording(controller.signal)
  controller.abort()
  await expect(recording.stop()).rejects.toThrow()
  expect(stop).toHaveBeenCalledTimes(1)
  expect(close).toHaveBeenCalledTimes(1)
})
it("does not activate a microphone acquired after cancellation", async () => {
  let acquired!: (value: MediaStream) => void
  vi.mocked(navigator.mediaDevices.getUserMedia).mockImplementationOnce(() => new Promise<MediaStream>(resolve => { acquired = resolve }))
  const controller = new AbortController()
  const pending = startOralRecording(controller.signal)
  controller.abort()
  acquired({ getTracks: () => [track] } as unknown as MediaStream)
  await expect(pending).rejects.toThrow()
  expect(stop).toHaveBeenCalledTimes(1)
  expect(close).not.toHaveBeenCalled()
})
