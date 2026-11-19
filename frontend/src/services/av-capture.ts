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

/** Averages blocks of `ratio` input samples (the trial's own 16 kHz pipeline does the same) and clamps to [-1, 1]. */
export function downsample(input: Float32Array, ratio: number): number[] {
  const length = Math.floor(input.length / ratio)
  const out: number[] = new Array(length)
  for (let index = 0; index < length; index++) {
    const start = Math.floor(index * ratio)
    const end = Math.min(input.length, Math.floor((index + 1) * ratio))
    let total = 0
    for (let at = start; at < end; at++) total += input[at]
    out[index] = Math.max(-1, Math.min(1, total / Math.max(1, end - start)))
  }
  return out
}

export interface MicrophoneRecorder extends VoiceRecorder {
  /** Releases the processor and the AudioContext; safe to call while recording and more than once. */
  close: () => Promise<void>
}

/**
 * A 16 kHz recorder over a MediaStream for hosts without their own audio pipeline (the pre-exam calibration).
 * The trial page feeds the same `VoiceRecorder` shape from its continuous supervision pipeline.
 */
export async function createMicrophoneRecorder(stream: MediaStream): Promise<MicrophoneRecorder> {
  const context = new AudioContext()
  try {
    await context.resume()
    const source = context.createMediaStreamSource(stream)
    const ratio = context.sampleRate / AUDIO_RATE
    let processor: ScriptProcessorNode | null = null
    let samples: number[] = []
    let startedAt = 0
    const detach = () => {
      if (!processor) return
      processor.onaudioprocess = null
      try { source.disconnect(processor) } catch { /* already disconnected */ }
      processor.disconnect()
      processor = null
    }
    return {
      start() {
        detach()
        samples = []
        startedAt = Date.now()
        // ScriptProcessor keeps compatibility with the trial pipeline; its output is always silent.
        const node = context.createScriptProcessor(2048, 1, 1)
        node.onaudioprocess = (event) => {
          event.outputBuffer.getChannelData(0).fill(0)
          if (samples.length >= MAX_RECORDING_SAMPLES) return
          for (const sample of downsample(event.inputBuffer.getChannelData(0), ratio)) samples.push(sample)
        }
        processor = node
        source.connect(node)
        node.connect(context.destination)
      },
      stop() {
        if (!processor) return null
        detach()
        const result = { samples, startedAt }
        samples = []
        return result
      },
      async close() {
        detach()
        samples = []
        try { source.disconnect() } catch { /* already disconnected */ }
        if (context.state !== "closed") await context.close()
      },
    }
  } catch (error) {
    if (context.state !== "closed") await context.close()
    throw error
  }
}
