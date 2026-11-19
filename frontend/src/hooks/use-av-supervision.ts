import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from "react"
import { WINDOW_LIMITS, WindowBuffer } from "@/hooks/av-window-buffer"
import { createAudioCapture, createRecorder, type AudioCapture, type VoiceRecorder } from "@/services/av-capture"
import {
  AVFailureTracker,
  avWindowDurationMs,
  sendAVWindow,
  type AVWindowResponse,
  type IncidentKind,
} from "@/services/browser-supervision"
import { startFaceTracker, type FaceTracker, type GazeZone, type MouthSampleDTO } from "@/services/gaze-tracking"

export type Emit = (event: { kind: IncidentKind; duration_ms?: number }) => void

/** What the last audiovisual window said about the candidate (the server is authoritative). */
export interface AvTelemetry {
  faceCount: number
  headOrientation: AVWindowResponse["head_orientation"]
  identityMatch: boolean | null
  faceCovered: boolean
  mouthCovered: boolean
  cameraBlocked: boolean
  speechDetected: boolean
  mouthMoving: boolean
  mouthSync: boolean | null
  multipleSpeakers: boolean
  voiceMatch: boolean | null
  lipSync: "synced" | "unsynced" | "insufficient" | null
  noiseLevel: number
}

export const EMPTY_TELEMETRY: AvTelemetry = {
  faceCount: 1, headOrientation: "CENTER", identityMatch: null, faceCovered: false, mouthCovered: false,
  cameraBlocked: false, speechDetected: false, mouthMoving: false, mouthSync: null, multipleSpeakers: false,
  voiceMatch: null, lipSync: null, noiseLevel: 0,
}

export function telemetryFromWindow(res: AVWindowResponse): AvTelemetry {
  return {
    faceCount: res.face_count,
    headOrientation: res.head_orientation,
    identityMatch: res.identity_match,
    faceCovered: Boolean(res.occlusion?.face || res.anomalies.includes("FACE_OCCLUDED")),
    mouthCovered: Boolean(res.occlusion?.mouth || res.anomalies.includes("MOUTH_OCCLUDED")),
    cameraBlocked: Boolean(res.camera_blocked || res.anomalies.includes("CAMERA_BLOCKED")),
    speechDetected: res.speech_detected,
    mouthMoving: Boolean(res.mouth_moving),
    mouthSync: res.mouth_sync ?? null,
    multipleSpeakers: Boolean(res.multiple_speakers || res.anomalies.includes("MULTIPLE_SPEAKERS")),
    voiceMatch: res.voice_match ?? null,
    lipSync: res.lip_sync ?? null,
    noiseLevel: res.noise_level,
  }
}

export interface AvStartOptions {
  trialId: string
  tabId: string
  emit: Emit
  /** Zone the browser tracker starts with (the trial's calibrated zone, if any). */
  gazeZone?: GazeZone | null
}

export interface UseAvSupervisionOptions {
  videoRef: RefObject<HTMLVideoElement | null>
  canvasRef: RefObject<HTMLCanvasElement | null>
  /** Windows are posted only while true (the calibration gate); the camera preview and the meter run regardless. */
  windowsEnabled: boolean
  /** A window reported anomalies: refresh the ledger. */
  onAnomalies?: () => void
  /** DEV tuning label sent with each window; omitted from the payload when undefined. */
  label?: string
}

interface Resources {
  stream: MediaStream
  audio: AudioCapture | null
  tracker: FaceTracker | null
  timer: ReturnType<typeof setInterval> | null
  frame: number | null
  unsubscribe: (() => void) | null
}

const TICK_MS = 400
const TICKS_PER_WINDOW = 6
const reason = (error: unknown) => (error instanceof Error ? error.message : "No se pudo completar la operación.")
const stopStream = (stream: MediaStream) => stream.getTracks().forEach((track) => track.stop())
/** Nonlinear perceptual scale so normal speech (RMS ~0.015-0.08) is clearly visible. */
const vuScale = (rms: number) => (rms < 0.002 ? 0 : Math.min(100, Math.round(Math.pow(rms * 14, 0.65) * 100)))

/**
 * Camera, microphone, browser face tracker and the audiovisual window loop of the trial page.
 *
 * Every resource lives in one `Resources` record owned by a generation number: `stop()` (lease lost, close,
 * restart, unmount) bumps the generation and releases everything, and every `await` in `start()` re-checks the
 * generation, so a stream, an audio pipeline or a tracker that arrives late is stopped instead of adopted.
 */
export function useAvSupervision({ videoRef, canvasRef, windowsEnabled, onAnomalies, label }: UseAvSupervisionOptions) {
  const generation = useRef(0)
  const resources = useRef<Resources | null>(null)
  const zone = useRef<GazeZone | null>(null)
  const enabled = useRef(windowsEnabled)
  const anomalies = useRef(onAnomalies)
  const labelRef = useRef(label)
  const [avActive, setAvActive] = useState(false)
  const [telemetry, setTelemetry] = useState<AvTelemetry>(EMPTY_TELEMETRY)
  const [vuLevel, setVuLevel] = useState(0)
  const [deviceError, setDeviceError] = useState("")
  const [avStatus, setAvStatus] = useState("")
  const [lookingAway, setLookingAway] = useState(false)
  const [gazeNotice, setGazeNotice] = useState("")

  useEffect(() => {
    enabled.current = windowsEnabled
    anomalies.current = onAnomalies
    labelRef.current = label
  })

  /** One 320x240 JPEG of the camera, the size the supervision windows and the calibration steps use. */
  const captureFrame = useCallback((): string | null => {
    const canvas = canvasRef.current
    const video = videoRef.current
    if (!canvas || !video || video.videoWidth === 0 || video.videoHeight === 0) return null
    canvas.width = 320
    canvas.height = 240
    const context = canvas.getContext("2d")
    if (!context) return null
    context.drawImage(video, 0, 0, 320, 240)
    return canvas.toDataURL("image/jpeg", 0.6)
  }, [canvasRef, videoRef])

  /** Releases tracks, audio pipeline, tracker and timers, and invalidates every pending `start()` continuation. */
  const stop = useCallback(() => {
    generation.current++
    const held = resources.current
    resources.current = null
    if (held) {
      if (held.frame !== null) cancelAnimationFrame(held.frame)
      if (held.timer) clearInterval(held.timer)
      held.unsubscribe?.()
      void held.audio?.close().catch(() => undefined)
      held.tracker?.stop()
      stopStream(held.stream)
    }
    if (videoRef.current) videoRef.current.srcObject = null
    setLookingAway(false)
    setGazeNotice("")
    setAvStatus("")
    setAvActive(false)
    setVuLevel(0)
  }, [videoRef])

  useEffect(() => stop, [stop])

  const setZone = useCallback((next: GazeZone | null) => {
    zone.current = next
    resources.current?.tracker?.setZone(next)
  }, [])

  /** The recorder of the voice calibration: it listens to the page's own 16 kHz capture (nothing else records). */
  const recording = useRef<VoiceRecorder | null>(null)
  const recorder = useMemo<VoiceRecorder>(
    () => ({
      start() {
        const audio = resources.current?.audio
        recording.current = audio ? createRecorder(audio) : null
        recording.current?.start()
      },
      stop() {
        const result = recording.current?.stop() ?? null
        recording.current = null
        return result
      },
    }),
    [],
  )

  const readMouth = useCallback(
    (startedAt: number, durationMs: number): MouthSampleDTO[] =>
      resources.current?.tracker?.takeMouthSamples(startedAt, durationMs) ?? [],
    [],
  )

  const start = useCallback(
    async (options: AvStartOptions) => {
      stop()
      const mine = generation.current
      const live = () => mine === generation.current
      const { trialId, tabId, emit } = options
      if (!navigator.mediaDevices?.getUserMedia) return
      if (options.gazeZone !== undefined) zone.current = options.gazeZone
      let stream: MediaStream
      try {
        // Raw room audio: supervision must hear what the room hears, so no echo cancellation, suppression or gain.
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
          audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false },
        })
      } catch {
        if (!live()) return
        emit({ kind: "STREAM_ERROR" })
        setDeviceError("No se pudo iniciar la cámara o micrófono. Verificá los permisos del navegador.")
        return
      }
      if (!live()) {
        stopStream(stream)
        return
      }
      const held: Resources = { stream, audio: null, tracker: null, timer: null, frame: null, unsubscribe: null }
      resources.current = held
      const video = videoRef.current
      if (video) {
        video.srcObject = stream
        void Promise.resolve(video.play()).catch(() => undefined)
      }
      for (const track of stream.getTracks()) {
        const device = track.kind === "video" ? "cámara" : "micrófono"
        track.addEventListener("ended", () => {
          if (!live()) return
          emit({ kind: "DEVICE_DISCONNECTED" })
          setDeviceError(`Dispositivo de ${device} desconectado.`)
        })
        track.addEventListener("mute", () => {
          if (!live()) return
          emit({ kind: "DEVICE_DISCONNECTED" })
          setDeviceError(`Pérdida temporal de señal en ${device}.`)
        })
      }

      const buffer = new WindowBuffer()
      let audioProblem = ""
      try {
        const audio = await createAudioCapture(stream, { meter: true })
        if (!live()) {
          void audio.close().catch(() => undefined)
          return
        }
        held.audio = audio
        held.unsubscribe = audio.subscribe((chunk) => {
          if (enabled.current) buffer.addAudio(chunk, Date.now())
        })
        const meter = () => {
          setVuLevel(vuScale(audio.level()))
          held.frame = requestAnimationFrame(meter)
        }
        held.frame = requestAnimationFrame(meter)
      } catch {
        if (!live()) return
        audioProblem = "No se pudo procesar el audio del micrófono. La supervisión registrará la falta de audio."
      }
      setAvActive(true)
      setDeviceError(audioProblem)

      // Browser-side gaze tracking (~15 fps) is a live hint and telemetry; the server re-measures the frames.
      if (video) {
        void startFaceTracker(video, { onAway: (away) => { if (live()) setLookingAway(away) } })
          .then((tracker) => {
            if (!live()) {
              tracker.stop()
              return
            }
            tracker.setZone(zone.current)
            held.tracker = tracker
          })
          .catch(() => {
            if (live()) {
              setGazeNotice("El seguimiento de mirada en tu navegador no está disponible. El servidor igual controla la mirada.")
            }
          })
      }

      const failures = new AVFailureTracker()
      let windowStart = Date.now()
      let ticks = 0
      let inFlight = false
      // One frame every 400 ms; a window leaves every 6 ticks (~2.4 s) and never while the previous one is in flight.
      held.timer = setInterval(() => {
        if (!live()) return
        const now = Date.now()
        if (!enabled.current) {
          buffer.clear()
          windowStart = now
          ticks = 0
          return
        }
        const image = captureFrame()
        if (image) buffer.addFrame(image, now)
        ticks++
        if (ticks < TICKS_PER_WINDOW || inFlight) return
        ticks = 0
        inFlight = true
        const taken = buffer.take()
        const durationMs = avWindowDurationMs(taken.audio.length)
        const startedAt = taken.audioStartedAt !== null ? Math.round(taken.audioStartedAt) : windowStart
        windowStart = now
        // A window without frames or audio is still sent: the server records the missing evidence.
        void sendAVWindow(trialId, {
          tab_id: tabId,
          window_id: crypto.randomUUID(),
          observed_at: new Date(startedAt).toISOString(),
          duration_ms: durationMs,
          mode: "UNIFIED",
          frames: taken.frames.map((frame) => frame.image),
          audio_samples: taken.audio,
          frame_times_ms: taken.frames.map((frame) => Math.min(durationMs, Math.max(0, frame.at - startedAt))),
          gaze_samples: (held.tracker?.takeSamples(startedAt, durationMs) ?? []).slice(-WINDOW_LIMITS.gazeSamples),
          ...(labelRef.current ? { label: labelRef.current } : {}),
        })
          .then((response) => {
            if (!live()) return
            failures.success()
            setAvStatus("")
            setTelemetry(telemetryFromWindow(response))
            if (response.anomalies.length > 0) anomalies.current?.()
          })
          .catch((cause) => {
            if (!live()) return
            const report = failures.failure()
            const count = failures.consecutive
            setAvStatus(
              `La supervisión audiovisual no pudo confirmarse (${count} ventana${count === 1 ? "" : "s"} seguida${
                count === 1 ? "" : "s"
              } sin respuesta): ${reason(cause)}`,
            )
            if (report) emit({ kind: "STREAM_ERROR" })
          })
          .finally(() => {
            inFlight = false
          })
      }, TICK_MS)
    },
    [captureFrame, stop, videoRef],
  )

  return {
    avActive, telemetry, vuLevel, deviceError, avStatus, lookingAway, gazeNotice,
    start, stop, captureFrame, setZone, recorder, readMouth,
  }
}
