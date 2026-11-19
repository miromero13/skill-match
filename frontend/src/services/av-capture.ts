import type { VoiceCalibrationFrame, VoiceCalibrationRequest } from "@/services/browser-supervision"
import type { MouthSampleDTO } from "@/services/gaze-tracking"

/**
 * Capture units shared by the trial's voice calibration and the pre-exam calibration (S9): one clock for the
 * 16 kHz audio, the timestamped JPEG frames and the mouth readings of the browser tracker. Everything here is
 * keyed to `startedAt`, the epoch ms at which the recording started; offsets are measured from it.
 */

export const AUDIO_RATE = 16_000
export const VOICE_FRAME_INTERVAL_MS = 120
/** Server limits of `POST /browser-supervision/trials/{id}/voice-calibration` (`frames`, `mouth_samples`). */
export const VOICE_FRAME_LIMITS = { min: 20, max: 130, spacingMs: 40, maxChars: 80_000, maxMs: 12_000 } as const
export const MOUTH_SPACING_MS = 30
const MAX_RECORDING_SAMPLES = AUDIO_RATE * 12

/** Captures 16 kHz mono audio between `start()` and `stop()`; `startedAt` is the epoch ms of the first sample. */
export interface VoiceRecorder {
  start: () => void
  stop: () => { samples: number[]; startedAt: number } | null
}

export interface TimedFrame {
  /** Epoch ms at which the frame was grabbed. */
  at: number
  image: string
}

export interface FrameSampler {
  start: () => void
  /** Stops the timer and returns the frames grabbed since `start()`. */
  stop: () => TimedFrame[]
  dispose: () => void
}

/** Grabs `capture()` every `intervalMs` (and once on start) with the epoch clock the audio recorder uses. */
export function createFrameSampler(
  capture: () => string | null,
  intervalMs = VOICE_FRAME_INTERVAL_MS,
  maxFrames = VOICE_FRAME_LIMITS.max * 2,
): FrameSampler {
  let timer: ReturnType<typeof setInterval> | null = null
  let taken: TimedFrame[] = []
  const grab = () => {
    if (taken.length >= maxFrames) return
    const image = capture()
    if (image) taken.push({ at: Date.now(), image })
  }
  const halt = () => {
    if (timer !== null) clearInterval(timer)
    timer = null
  }
  return {
    start() {
      halt()
      taken = []
      grab()
      timer = setInterval(grab, intervalMs)
    },
    stop() {
      halt()
      grab()
      const result = taken
      taken = []
      return result
    },
    dispose() {
      halt()
      taken = []
    },
  }
}

/**
 * Frames as `{ t_ms, image }` offsets from `startedAt`, inside [0, min(audioMs, 12 s)], at least 40 ms apart and
 * thinned evenly to the server maximum (130).
 */
export function frameEvidence(frames: ReadonlyArray<TimedFrame>, startedAt: number, audioMs: number): VoiceCalibrationFrame[] {
  const limit = Math.min(audioMs, VOICE_FRAME_LIMITS.maxMs)
  const kept: VoiceCalibrationFrame[] = []
  for (const frame of frames) {
    const offset = Math.round(frame.at - startedAt)
    if (offset < 0 || offset > limit) continue
    const previous = kept.at(-1)
    if (previous && offset - previous.t_ms < VOICE_FRAME_LIMITS.spacingMs) continue
    kept.push({ t_ms: offset, image: frame.image })
  }
  if (kept.length <= VOICE_FRAME_LIMITS.max) return kept
  return Array.from({ length: VOICE_FRAME_LIMITS.max }, (_, index) =>
    kept[Math.round((index * (kept.length - 1)) / (VOICE_FRAME_LIMITS.max - 1))])
}

/** Mouth readings inside the audio, strictly increasing and at least 30 ms apart (the server rejects anything else). */
export function mouthEvidence(samples: ReadonlyArray<MouthSampleDTO>, audioMs: number): MouthSampleDTO[] {
  const kept: MouthSampleDTO[] = []
  for (const sample of samples) {
    if (sample.t_ms < 0 || sample.t_ms > audioMs) continue
    const previous = kept.at(-1)
    if (previous && sample.t_ms - previous.t_ms < MOUTH_SPACING_MS) continue
    kept.push(sample)
  }
  return kept
}

/** One recording (silence, then the phrase) in the shape of the trial's voice calibration, bounds enforced. */
export function assembleVoiceRequest(
  recording: { samples: number[]; startedAt: number },
  frames: ReadonlyArray<TimedFrame>,
  mouth: ReadonlyArray<MouthSampleDTO>,
  ambientMs: number,
): VoiceCalibrationRequest {
  const audioMs = Math.floor((recording.samples.length * 1000) / AUDIO_RATE)
  const wire = frameEvidence(frames, recording.startedAt, audioMs)
  if (wire.length < VOICE_FRAME_LIMITS.min) {
    throw new Error("No se obtuvo video sincronizado suficiente. Mantené la página visible y repetí la calibración.")
  }
  if (wire.some((frame) => frame.image.length > VOICE_FRAME_LIMITS.maxChars)) {
    throw new Error("La imagen de voz es demasiado grande. Usá una cámara de menor resolución y repetí la calibración.")
  }
  return {
    audio_samples: recording.samples,
    ambient_ms: ambientMs,
    mouth_samples: mouthEvidence(mouth, audioMs),
    frames: wire,
  }
}

const FILTER_PHASES = 256
const FILTER_LOBES = 16
const clamp = (value: number) => (Number.isFinite(value) ? Math.max(-1, Math.min(1, value)) : 0)

/**
 * Streaming sample-rate converter to 16 kHz for any input rate: a Blackman-windowed sinc low-pass (cut-off at 45% of
 * the lower rate, so about 7.2 kHz for 16 kHz output) evaluated at the exact fractional input position of every output
 * sample (256 pre-computed phases). Aliasing is suppressed by more than 70 dB, the DC gain is exactly 1, output sample
 * `n` sits at input time `n * inputRate / 16000` (no delay), values are clamped to [-1, 1] and non-finite input counts
 * as silence. A rate equal to the output rate is passed through (only clamped).
 */
export class Decimator {
  private readonly step: number
  private readonly half: number
  private readonly table: Float32Array[] = []
  private readonly passthrough: boolean
  private history = new Float32Array(0)
  private base = 0
  private produced = 0
  private received = 0

  constructor(inputRate: number, outputRate = AUDIO_RATE) {
    if (!Number.isFinite(inputRate) || inputRate <= 0 || !Number.isFinite(outputRate) || outputRate <= 0) {
      throw new RangeError("La frecuencia de muestreo del audio no es válida.")
    }
    this.step = inputRate / outputRate
    this.passthrough = inputRate === outputRate
    const cutoff = (0.45 * Math.min(inputRate, outputRate)) / inputRate // cycles per input sample
    this.half = Math.ceil(FILTER_LOBES / (2 * cutoff))
    for (let phase = 0; phase < FILTER_PHASES; phase++) {
      const taps = new Float32Array(2 * this.half)
      let sum = 0
      for (let index = 0; index < taps.length; index++) {
        const distance = index - this.half + 1 - phase / FILTER_PHASES
        const x = 2 * cutoff * distance
        const sinc = x === 0 ? 1 : Math.sin(Math.PI * x) / (Math.PI * x)
        const angle = (Math.PI * distance) / this.half
        taps[index] = 2 * cutoff * sinc * (0.42 + 0.5 * Math.cos(angle) + 0.08 * Math.cos(2 * angle))
        sum += taps[index]
      }
      for (let index = 0; index < taps.length; index++) taps[index] /= sum
      this.table.push(taps)
    }
  }

  /** Converts the next chunk of input; outputs that still need future input wait for the next call. */
  push(chunk: ArrayLike<number>): number[] {
    if (this.passthrough) return Array.from({ length: chunk.length }, (_, index) => clamp(chunk[index]))
    this.received += chunk.length
    const input = new Float32Array(this.history.length + chunk.length)
    input.set(this.history)
    for (let index = 0; index < chunk.length; index++) {
      input[this.history.length + index] = Number.isFinite(chunk[index]) ? chunk[index] : 0
    }
    return this.run(input, Number.POSITIVE_INFINITY)
  }

  /** Emits the tail (the stream is treated as followed by silence); call once at the end of a one-shot conversion. */
  flush(): number[] {
    if (this.passthrough) return []
    const input = new Float32Array(this.history.length + this.half + 1)
    input.set(this.history)
    return this.run(input, this.received)
  }

  private run(input: Float32Array, limit: number): number[] {
    const out: number[] = []
    const end = this.base + input.length
    for (;;) {
      const at = this.produced * this.step
      if (at >= limit) break
      let centre = Math.floor(at)
      let phase = Math.round((at - centre) * FILTER_PHASES)
      if (phase === FILTER_PHASES) { centre++; phase = 0 }
      if (centre + this.half >= end) break
      const taps = this.table[phase]
      let total = 0
      for (let index = 0; index < taps.length; index++) {
        const position = centre - this.half + 1 + index - this.base
        if (position >= 0) total += input[position] * taps[index]
      }
      out.push(clamp(total))
      this.produced++
    }
    const keepFrom = Math.max(this.base, Math.floor(this.produced * this.step) - this.half)
    this.history = input.slice(keepFrom - this.base)
    this.base = keepFrom
    return out
  }
}

/** One-shot conversion of a whole recording to 16 kHz (see `Decimator`); the output covers the input duration. */
export function resample(input: ArrayLike<number>, inputRate: number): number[] {
  const decimator = new Decimator(inputRate)
  return [...decimator.push(input), ...decimator.flush()]
}

export type AudioCaptureMode = "worklet" | "script-processor"

/** One microphone pipeline: every consumer receives 16 kHz mono samples in [-1, 1], whatever the context rate. */
export interface AudioCapture {
  readonly mode: AudioCaptureMode
  /** Calls `listener` with each new run of 16 kHz samples; returns the unsubscribe function. */
  subscribe: (listener: (samples: number[]) => void) => () => void
  /** RMS (0..1) of the latest raw audio for a level meter; 0 unless the capture was created with `meter`. */
  level: () => number
  /** Releases the nodes and the AudioContext; safe while capturing and more than once. */
  close: () => Promise<void>
}

const WORKLET_URL = "/worklets/capture-processor.js"
const SCRIPT_BLOCK = 2048

type Teardown = () => void
const quietly = (action: () => void) => { try { action() } catch { /* already disconnected */ } }

async function attachWorklet(context: AudioContext, source: MediaStreamAudioSourceNode, ingest: (chunk: Float32Array) => void): Promise<Teardown | null> {
  if (!context.audioWorklet || typeof AudioWorkletNode === "undefined") return null
  try { await context.audioWorklet.addModule(WORKLET_URL) } catch { return null }
  const node = new AudioWorkletNode(context, "skillmatch-capture", { numberOfInputs: 1, numberOfOutputs: 1, channelCount: 1, channelCountMode: "explicit" })
  node.port.onmessage = (event: MessageEvent<Float32Array>) => ingest(event.data)
  // The node never writes its output, so reaching the destination only keeps it scheduled; the gain is zero anyway.
  const sink = typeof context.createGain === "function" ? context.createGain() : null
  if (sink) sink.gain.value = 0
  source.connect(node)
  node.connect(sink ?? context.destination)
  sink?.connect(context.destination)
  return () => {
    node.port.onmessage = null
    quietly(() => source.disconnect(node))
    quietly(() => node.disconnect())
    if (sink) quietly(() => sink.disconnect())
  }
}

/** Compatibility path for browsers without AudioWorklet (or where the module cannot load): same output, same interface. */
function attachScriptProcessor(context: AudioContext, source: MediaStreamAudioSourceNode, ingest: (chunk: Float32Array) => void): Teardown | null {
  if (typeof context.createScriptProcessor !== "function") return null
  const node = context.createScriptProcessor(SCRIPT_BLOCK, 1, 1)
  node.onaudioprocess = (event) => {
    event.outputBuffer.getChannelData(0).fill(0) // the microphone is never played back
    ingest(event.inputBuffer.getChannelData(0))
  }
  source.connect(node)
  node.connect(context.destination)
  return () => {
    node.onaudioprocess = null
    quietly(() => source.disconnect(node))
    quietly(() => node.disconnect())
  }
}

/**
 * The one capture pipeline of the trial page, the voice calibration and the pre-exam calibration: AudioWorklet
 * capture (ScriptProcessor only as a fallback) into a `Decimator` that produces 16 kHz mono for any context rate.
 */
export async function createAudioCapture(stream: MediaStream, options: { meter?: boolean } = {}): Promise<AudioCapture> {
  const Context = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!Context) throw new Error("Este navegador no permite capturar audio.")
  const context = new Context()
  const listeners = new Set<(samples: number[]) => void>()
  const teardown: Teardown[] = []
  let closing: Promise<void> | null = null
  let analyser: AnalyserNode | null = null
  let meterBuffer: Float32Array<ArrayBuffer> | null = null
  try {
    const decimator = new Decimator(context.sampleRate)
    const ingest = (chunk: Float32Array) => {
      if (closing || listeners.size === 0) return
      const out = decimator.push(chunk)
      if (out.length) for (const listener of [...listeners]) listener(out)
    }
    await context.resume().catch(() => undefined)
    const source = context.createMediaStreamSource(stream)
    if (options.meter && typeof context.createAnalyser === "function") {
      analyser = context.createAnalyser()
      analyser.fftSize = 1024
      meterBuffer = new Float32Array(analyser.fftSize)
      source.connect(analyser)
      teardown.push(() => quietly(() => source.disconnect(analyser!)))
    }
    let mode: AudioCaptureMode = "worklet"
    let detach = await attachWorklet(context, source, ingest)
    if (!detach) {
      mode = "script-processor"
      detach = attachScriptProcessor(context, source, ingest)
    }
    if (!detach) throw new Error("Este navegador no permite procesar el audio del micrófono.")
    teardown.push(detach, () => quietly(() => source.disconnect()))
    return {
      mode,
      subscribe(listener) {
        listeners.add(listener)
        return () => { listeners.delete(listener) }
      },
      level() {
        if (closing || !analyser || !meterBuffer || typeof analyser.getFloatTimeDomainData !== "function") return 0
        analyser.getFloatTimeDomainData(meterBuffer)
        let total = 0
        for (const value of meterBuffer) total += value * value
        return Math.sqrt(total / meterBuffer.length)
      },
      close() {
        closing ??= (async () => {
          listeners.clear()
          teardown.splice(0).forEach((action) => action())
          if (context.state !== "closed") await context.close()
        })()
        return closing
      },
    }
  } catch (error) {
    teardown.splice(0).forEach((action) => action())
    if (context.state !== "closed") await context.close().catch(() => undefined)
    throw error
  }
}

/** A recorder over a capture: 16 kHz samples between `start()` and `stop()`, at most 12 s, `startedAt` in epoch ms. */
export function createRecorder(capture: AudioCapture): VoiceRecorder {
  let samples: number[] | null = null
  let startedAt = 0
  let unsubscribe: (() => void) | null = null
  const halt = () => { unsubscribe?.(); unsubscribe = null }
  return {
    start() {
      halt()
      const mine: number[] = []
      samples = mine
      startedAt = Date.now()
      unsubscribe = capture.subscribe((chunk) => {
        for (let index = 0; index < chunk.length && mine.length < MAX_RECORDING_SAMPLES; index++) mine.push(chunk[index])
      })
    },
    stop() {
      if (!unsubscribe || !samples) return null
      halt()
      const result = { samples, startedAt }
      samples = null
      return result
    },
  }
}

export interface MicrophoneRecorder extends VoiceRecorder {
  /** Releases the pipeline and the AudioContext; safe to call while recording and more than once. */
  close: () => Promise<void>
}

/** A 16 kHz recorder that owns its own capture, for hosts without a continuous pipeline (the pre-exam calibration). */
export async function createMicrophoneRecorder(stream: MediaStream): Promise<MicrophoneRecorder> {
  const capture = await createAudioCapture(stream)
  const recorder = createRecorder(capture)
  return {
    ...recorder,
    async close() {
      recorder.stop()
      await capture.close()
    },
  }
}
