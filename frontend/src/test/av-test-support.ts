import { vi, type Mock } from "vitest"

type Processing = { inputBuffer: { getChannelData: () => Float32Array }; outputBuffer: { getChannelData: () => Float32Array } }

export interface FakeContext {
  state: string
  close: Mock<() => Promise<void>>
  rate: number
}

/**
 * Browser media stand-ins for the trial page tests: one stream per getUserMedia call (every track stop is
 * counted), every AudioContext created (with its close spy) and the ScriptProcessor callback to feed audio.
 * `deferred` makes getUserMedia / AudioContext.resume wait until the test resolves them.
 */
export function stubMedia(options: { deferredStream?: boolean; deferredResume?: boolean; rate?: number } = {}) {
  const stops = vi.fn()
  const contexts: FakeContext[] = []
  const processors: { onaudioprocess: ((event: Processing) => void) | null }[] = []
  const analyserFill: { value: ((target: Float32Array) => void) | null } = { value: null }
  const stream = {
    getTracks: () => [
      { kind: "video", stop: stops, addEventListener: vi.fn(), removeEventListener: vi.fn() },
      { kind: "audio", stop: stops, addEventListener: vi.fn(), removeEventListener: vi.fn() },
    ],
  }
  let release: (value: typeof stream) => void = () => undefined
  const getUserMedia = vi.fn((): Promise<typeof stream> =>
    options.deferredStream ? new Promise((resolve) => { release = resolve }) : Promise.resolve(stream))
  Object.defineProperty(navigator, "mediaDevices", { value: { getUserMedia }, configurable: true })
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined)
  Object.defineProperty(HTMLVideoElement.prototype, "videoWidth", { value: 640, configurable: true })
  Object.defineProperty(HTMLVideoElement.prototype, "videoHeight", { value: 480, configurable: true })
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ drawImage: vi.fn() } as never)
  let counter = 0
  vi.spyOn(HTMLCanvasElement.prototype, "toDataURL").mockImplementation(() => `data:image/jpeg;base64,F${counter++}`)
  let resumeRelease: () => void = () => undefined
  vi.stubGlobal("AudioContext", class {
    sampleRate = options.rate ?? 16_000
    state = "running"
    destination = {}
    private readonly info: FakeContext
    constructor() {
      this.info = { state: "running", rate: this.sampleRate, close: vi.fn(() => { this.state = "closed"; this.info.state = "closed"; return Promise.resolve() }) }
      contexts.push(this.info)
    }
    close = () => this.info.close()
    resume = () => (options.deferredResume ? new Promise<void>((resolve) => { resumeRelease = resolve }) : Promise.resolve())
    createMediaStreamSource = () => ({ connect: vi.fn(), disconnect: vi.fn() })
    createAnalyser = () => ({
      fftSize: 1024, connect: vi.fn(), disconnect: vi.fn(),
      getFloatTimeDomainData: (target: Float32Array) => analyserFill.value?.(target),
    })
    createScriptProcessor = () => {
      const node = { onaudioprocess: null as ((event: Processing) => void) | null, connect: vi.fn(), disconnect: vi.fn() }
      processors.push(node)
      return node
    }
  })
  return {
    getUserMedia,
    contexts,
    stops,
    resolveStream: () => release(stream),
    resolveResume: () => resumeRelease(),
    /** Feeds `samples` of constant audio to the newest ScriptProcessor, at the context's rate. */
    feed: (samples: number, value = 0) =>
      processors.at(-1)?.onaudioprocess?.({
        inputBuffer: { getChannelData: () => new Float32Array(samples).fill(value) },
        outputBuffer: { getChannelData: () => new Float32Array(samples) },
      }),
    analyserFill,
  }
}
