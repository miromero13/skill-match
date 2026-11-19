import { AUDIO_RATE } from "@/services/av-capture"
import type { CalibrationEvidence } from "@/services/evaluation-service"
import type { GazeCalibrationPoint, VoiceCalibrationRequest } from "@/services/browser-supervision"

/**
 * What only the pre-exam calibration needs: the head-movement capture and the assembly of its single request.
 * Gaze, voice, audio and frame capture are the shared units of `av-capture` and the integrity components.
 */

export type LivenessPhase = "CENTER" | "TURN" | "RETURN"

const LIVENESS_FRAMES = 12
const MAX_JPEG_CHARS = 200_000
const MAX_SPOKEN_CHARS = 80_000

function delay(milliseconds: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException("Capture cancelled", "AbortError")); return }
    const cancel = () => { clearTimeout(timer); reject(new DOMException("Capture cancelled", "AbortError")) }
    const timer = setTimeout(() => { signal.removeEventListener("abort", cancel); resolve() }, milliseconds)
    signal.addEventListener("abort", cancel, { once: true })
  })
}

/**
 * Twelve frames one second apart: centre (0-3), turn (4-7), back to centre (8-11). `grab` keeps the camera's
 * original orientation (CSS mirrors only the preview).
 */
export async function captureLivenessFrames(
  grab: () => string | null, signal: AbortSignal, onPhase?: (phase: LivenessPhase) => void,
): Promise<string[]> {
  const frames: string[] = []
  signal.throwIfAborted()
  onPhase?.("CENTER")
  for (let index = 0; index < LIVENESS_FRAMES; index++) {
    signal.throwIfAborted()
    const frame = grab()
    if (!frame) throw new Error("Esperá a que la cámara muestre imagen antes de capturar el movimiento.")
    frames.push(frame)
    if (index === 3) onPhase?.("TURN")
    if (index === 7) onPhase?.("RETURN")
    if (index < LIVENESS_FRAMES - 1) await delay(1000, signal)
  }
  return frames
}

export interface PhraseEvidence {
  ambient_audio_samples: number[]
  audio_samples: number[]
  spoken_frames: { time_ms: number; image: string }[]
  mouth_samples: { t_ms: number; mouth_open: number }[]
}

/**
 * The shared voice recording is silence then phrase on one clock; the engine wants the silence apart and every
 * other timestamp counted from the start of the phrase audio.
 */
export function splitPhraseEvidence(recording: VoiceCalibrationRequest): PhraseEvidence {
  const cutSamples = Math.round((recording.ambient_ms * AUDIO_RATE) / 1000)
  const cutMs = recording.ambient_ms
  return {
    ambient_audio_samples: recording.audio_samples.slice(0, cutSamples),
    audio_samples: recording.audio_samples.slice(cutSamples),
    spoken_frames: recording.frames.filter((frame) => frame.t_ms >= cutMs)
      .map((frame) => ({ time_ms: frame.t_ms - cutMs, image: frame.image })),
    mouth_samples: recording.mouth_samples.filter((sample) => sample.t_ms >= cutMs)
      .map((sample) => ({ t_ms: sample.t_ms - cutMs, mouth_open: sample.mouth_open })),
  }
}

const GAZE_TARGET_COUNT = 5
const median = (values: number[]) => {
  const sorted = [...values].sort((a, b) => a - b)
  return sorted[Math.floor(sorted.length / 2)]
}

function assertMovement(frames: string[]) {
  if (frames.length < 3 || frames.length > 12) {
    throw new Error("No se capturaron suficientes imágenes del movimiento de cabeza. Repetí la calibración.")
  }
  if (frames.some((frame) => frame.length > MAX_JPEG_CHARS)) {
    throw new Error("Una imagen del movimiento es demasiado grande. Usá una cámara de menor resolución y repetí la calibración.")
  }
}

function assertGaze(points: GazeCalibrationPoint[]) {
  if (points.length !== GAZE_TARGET_COUNT || new Set(points.map((point) => point.target)).size !== GAZE_TARGET_COUNT) {
    throw new Error("Hace falta exactamente un punto de mirada por cada esquina y uno en el centro: cinco puntos.")
  }
  if (points.some((point) => point.frames.length < 1 || point.frames.length > 6)) {
    throw new Error("Faltan imágenes en un punto de la calibración de mirada. Repetí la calibración.")
  }
  if (points.some((point) => point.frames.some((frame) => frame.length > MAX_JPEG_CHARS))) {
    throw new Error("Una imagen de la mirada es demasiado grande. Usá una cámara de menor resolución y repetí la calibración.")
  }
}

function assertPhrase(parts: PhraseEvidence) {
  const { ambient_audio_samples: ambient, audio_samples: audio, spoken_frames: frames, mouth_samples: mouth } = parts
  if (ambient.length < 32_000 || ambient.length > 64_000) {
    throw new Error("El audio del silencio debe durar entre 2 y 4 segundos. Repetí la calibración.")
  }
  if (audio.length < 112_000 || audio.length > 160_000) {
    throw new Error("El audio de la frase y la pausa debe durar entre 7 y 10 segundos. Repetí la calibración.")
  }
  const speechMs = Math.floor((audio.length * 1000) / AUDIO_RATE)
  if (frames.length < 20 || frames.length > 100 || frames.some((frame) => frame.image.length > MAX_SPOKEN_CHARS)) {
    throw new Error(frames.length >= 20 && frames.length <= 100
      ? "La imagen de voz es demasiado grande. Usá una cámara de menor resolución y repetí la calibración."
      : "No se obtuvo video sincronizado suficiente. Mantené la página visible y repetí la calibración.")
  }
  const times = frames.map((frame) => frame.time_ms)
  const gaps = times.slice(1).map((time, index) => time - times[index])
  // The same timeline the engine requires: starts with the phrase, reaches the end, no holes.
  if (times[0] > 250 || times[times.length - 1] < speechMs - 300 || times[times.length - 1] > speechMs
    || Math.min(...gaps) < 40 || Math.max(...gaps) > 350 || median(gaps) > 200) {
    throw new Error("El video de la frase se interrumpió. Mantené la pestaña visible, sin cambiar de ventana, y repetí la calibración.")
  }
  if (mouth.length < 8 || mouth.length > 450) {
    throw new Error("No se detectó el movimiento de tu boca. Mirá a la cámara con el rostro descubierto y repetí la calibración.")
  }
}

/** Assembles contract A from the guided captures, enforcing every server bound before anything is sent. */
export function buildCalibrationEvidence(input: {
  challengeId: string
  frames: string[]
  gazePoints?: GazeCalibrationPoint[]
  voice: VoiceCalibrationRequest
  cameraLabel: string
}): CalibrationEvidence {
  assertMovement(input.frames)
  if (input.gazePoints?.length) assertGaze(input.gazePoints)
  const parts = splitPhraseEvidence(input.voice)
  const speechMs = Math.floor((parts.audio_samples.length * 1000) / AUDIO_RATE)
  parts.mouth_samples = parts.mouth_samples.filter((sample) => sample.t_ms <= speechMs)
  parts.spoken_frames = parts.spoken_frames.filter((frame) => frame.time_ms <= speechMs)
  assertPhrase(parts)
  return {
    challenge_id: input.challengeId,
    frames: input.frames,
    gaze_points: input.gazePoints ?? [],
    ...parts,
    camera_label: input.cameraLabel.slice(0, 200),
  }
}
