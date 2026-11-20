import { AUDIO_RATE, type TimedFrame } from "@/services/av-capture"

/**
 * What one audiovisual window may carry (backend `AVWindowRequest`: 12 frames, 160000 audio samples, 60 gaze
 * samples, 30 s). The buffer never holds more than that: while a window request is in flight the evidence keeps
 * arriving and the oldest part is dropped, so memory stays bounded and the newest evidence is what gets sent.
 */
export const WINDOW_LIMITS = { frames: 12, audioSamples: 160_000, gazeSamples: 60, durationMs: 30_000 } as const

export interface TakenWindow {
  frames: TimedFrame[]
  audio: number[]
  /** Epoch ms of the first audio sample kept, or null when there is no audio. */
  audioStartedAt: number | null
}

export class WindowBuffer {
  private frames: TimedFrame[] = []
  private audio: number[] = []
  private audioStart: number | null = null

  addFrame(image: string, at: number) {
    this.frames.push({ image, at })
    if (this.frames.length > WINDOW_LIMITS.frames) this.frames.splice(0, this.frames.length - WINDOW_LIMITS.frames)
  }

  /** `now` is the epoch ms at which `samples` (16 kHz) finished arriving. */
  addAudio(samples: ReadonlyArray<number>, now: number) {
    if (this.audio.length === 0) this.audioStart = now - (samples.length * 1000) / AUDIO_RATE
    for (let index = 0; index < samples.length; index++) this.audio.push(samples[index])
    const overflow = this.audio.length - WINDOW_LIMITS.audioSamples
    if (overflow > 0) {
      this.audio.splice(0, overflow)
      this.audioStart = (this.audioStart ?? now) + (overflow * 1000) / AUDIO_RATE
    }
  }

  /** Hands over everything collected and starts again empty. */
  take(): TakenWindow {
    const taken = { frames: this.frames, audio: this.audio, audioStartedAt: this.audio.length ? this.audioStart : null }
    this.clear()
    return taken
  }

  clear() {
    this.frames = []
    this.audio = []
    this.audioStart = null
  }
}
