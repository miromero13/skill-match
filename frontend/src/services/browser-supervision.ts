import { apiClient } from "@/services/api-client"
import type { GazeSampleDTO, GazeZone, MouthSampleDTO } from "@/services/gaze-tracking"

export type IncidentKind =
  | "AWAY"
  | "RETURN"
  | "COPY"
  | "CUT"
  | "PASTE"
  | "DROP"
  | "CONTEXT_MENU"
  | "FULLSCREEN_EXIT"
  | "OFFLINE"
  | "ONLINE"
  | "PAGE_EXIT"
  | "SESSION_OPEN"
  | "SESSION_RESUME"
  | "FACE_ABSENT"
  | "MULTIPLE_FACES"
  | "IDENTITY_MISMATCH"
  | "HEAD_POSE_DOWN"
  | "HEAD_POSE_SIDE"
  | "HEAD_POSE_UP"
  | "GAZE_AWAY"
  | "CLIENT_MISMATCH"
  | "VOICE_DETECTED"
  | "MULTIPLE_SPEAKERS"
  | "HIGH_NOISE"
  | "DEVICE_DISCONNECTED"
  | "STREAM_ERROR"
  | "MODEL_UNAVAILABLE"
  | "VIDEO_MISSING"
  | "AUDIO_MISSING"
  | "WINDOW_GAP"
  | "FACE_OCCLUDED"
  | "MOUTH_OCCLUDED"
  | "CAMERA_BLOCKED"
  | "VOICE_MISMATCH"
  | "VOICE_UNVERIFIED"
  | "LIP_SYNC_MISMATCH"
  | "BACKGROUND_AUDIO"

export interface BrowserIncident {
  event_id: string
  kind: IncidentKind
  observed_at: string
  duration_ms: number
}
export interface LedgerIncident extends BrowserIncident {
  sequence: number
  received_at: string
}
export interface Trial {
  id: string
  mode: "TRIAL"
  created_at: string
  expires_at: string
  closed_at: string | null
  lease_until: string | null
  event_count: number
  /** Calibrated screen zone of this trial; null until the candidate calibrates. */
  gaze_zone?: GazeZone | null
  /** A voiceprint is enrolled for this trial (the embedding itself never leaves the server). */
  voice_enrolled?: boolean
}
export interface BatchResult {
  accepted_ids: string[]
  event_count: number
}
export interface AVWindowPayload {
  tab_id: string
  window_id: string
  observed_at: string
  duration_ms: number
  mode?: "QUIET" | "SPEAKING" | "UNIFIED"
  frames: string[]
  audio_samples?: number[]
  /** Capture offset (ms from `observed_at`, the window start) of each frame, aligned with `frames`. */
  frame_times_ms?: number[]
  /** Browser MediaPipe readings (~15 fps); the server only trusts them when they agree with its own frames. */
  gaze_samples?: GazeSampleDTO[]
  /** Tuning label (DEV only): the backend ignores it unless integrity diagnostics are enabled. */
  label?: string
}
export interface AVWindowResponse {
  window_id: string
  face_count: number
  head_orientation: "CENTER" | "DOWN" | "UP" | "LEFT" | "RIGHT" | "UNKNOWN"
  identity_match: boolean | null
  speech_detected: boolean
  mouth_moving?: boolean
  mouth_sync?: boolean | null
  /** The voice is the enrolled one; null without speech, without a voiceprint or without a verdict. */
  voice_match?: boolean | null
  /** Voice energy vs mouth movement over the window; null without speech. */
  lip_sync?: "synced" | "unsynced" | "insufficient" | null
  multiple_speakers?: boolean
  noise_level: number
  /** Confirmed (continuous >= 1 s) covered face / covered mouth, and blocked or frozen camera. */
  occlusion?: { face: boolean; mouth: boolean }
  camera_blocked?: boolean
  anomalies: string[]
  incidents_created: LedgerIncident[]
}

export const AV_SAMPLE_RATE = 16_000
/** Nominal spacing of audiovisual windows; used when a window carries no audio to measure. */
export const AV_NOMINAL_WINDOW_MS = 2400
/** Consecutive failed audiovisual windows before a local STREAM_ERROR incident is queued. */
export const AV_FAILURE_THRESHOLD = 2

/** The duration a window reports must be the audio it actually carries (server limits: 500-30000 ms). */
export function avWindowDurationMs(sampleCount: number) {
  if (sampleCount <= 0) return AV_NOMINAL_WINDOW_MS
  return Math.min(30_000, Math.max(500, Math.round((sampleCount / AV_SAMPLE_RATE) * 1000)))
}

/** Counts consecutive audiovisual window failures; a success starts a new streak. */
export class AVFailureTracker {
  private failures = 0
  private reported = false
  private threshold: number
  constructor(threshold = AV_FAILURE_THRESHOLD) {
    this.threshold = threshold
  }
  get consecutive() {
    return this.failures
  }
  /** Returns true exactly once per streak: when the threshold is first reached. */
  failure() {
    this.failures++
    if (this.reported || this.failures < this.threshold) return false
    this.reported = true
    return true
  }
  success() {
    this.failures = 0
    this.reported = false
  }
}

const root = "/browser-supervision/trials"
const silent = { showToastOnError: false }

export async function startBrowserTrial(tabId: string) {
  const response = await apiClient.post<Trial>(root, { tab_id: tabId, accepted: true }, silent)
  return { trial: response.data, message: response.message }
}
export async function readBrowserTrial(id: string) {
  return (await apiClient.get<Trial>(`${root}/${id}`, silent)).data
}
export async function trialAction(id: string, tabId: string, action: "heartbeat" | "release" | "close", keepalive = false) {
  const response = await apiClient.post<Trial>(`${root}/${id}/${action}`, { tab_id: tabId }, { ...silent, keepalive })
  return { trial: response.data, message: response.message }
}
export async function sendBrowserIncidents(id: string, tabId: string, events: BrowserIncident[]) {
  return (await apiClient.post<BatchResult>(`${root}/${id}/events`, { tab_id: tabId, events }, silent)).data
}
export async function sendAVWindow(id: string, payload: AVWindowPayload) {
  const response = await apiClient.post<AVWindowResponse>(`${root}/${id}/av-window`, payload, silent)
  return response.data
}
export type GazeTarget = "CENTER" | "TOP_LEFT" | "TOP_RIGHT" | "BOTTOM_LEFT" | "BOTTOM_RIGHT"
export interface GazeCalibrationPoint {
  target: GazeTarget
  frames: string[]
}
export interface GazeCalibrationResult {
  zone: GazeZone
  frames_used: number
}
/** Sends the frames captured at the center and the four corners; the server computes and stores the zone. */
export async function calibrateGaze(id: string, tabId: string, points: GazeCalibrationPoint[]) {
  const response = await apiClient.post<GazeCalibrationResult>(
    `${root}/${id}/gaze-calibration`,
    { tab_id: tabId, points },
    silent,
  )
  return { result: response.data, message: response.message }
}
/** A JPEG sampled while recording; `t_ms` counts from the start of `audio_samples` (the server measures the mouth on it). */
export interface VoiceCalibrationFrame {
  t_ms: number
  image: string
}
/** Recording of the voice calibration: `ambient_ms` of silence first, then the control phrase read aloud (16 kHz mono). */
export interface VoiceCalibrationRequest {
  audio_samples: number[]
  ambient_ms: number
  /** Mouth aperture readings, `t_ms` counted from the start of `audio_samples`. */
  mouth_samples: MouthSampleDTO[]
  /** 20 to 130 sampled JPEGs, at least 40 ms apart and inside the audio; required by the server. */
  frames: VoiceCalibrationFrame[]
}
export interface VoiceCalibrationResult {
  voice_enrolled: boolean
  voiced_seconds: number
}
/** Enrolls the trial's voiceprint; the server answers only whether it is enrolled, never the embedding. */
export async function calibrateVoice(id: string, tabId: string, request: VoiceCalibrationRequest) {
  const response = await apiClient.post<VoiceCalibrationResult>(
    `${root}/${id}/voice-calibration`,
    { tab_id: tabId, ...request },
    silent,
  )
  return { result: response.data, message: response.message }
}
export async function readBrowserLedger(id: string, after = 0) {
  return apiClient.get<LedgerIncident[]>(`${root}/${id}/events`, { ...silent, params: { after, limit: 200 } })
}

const kinds: IncidentKind[] = [
  "AWAY",
  "RETURN",
  "COPY",
  "CUT",
  "PASTE",
  "DROP",
  "CONTEXT_MENU",
  "FULLSCREEN_EXIT",
  "OFFLINE",
  "ONLINE",
  "PAGE_EXIT",
  "SESSION_OPEN",
  "SESSION_RESUME",
  "FACE_ABSENT",
  "MULTIPLE_FACES",
  "IDENTITY_MISMATCH",
  "HEAD_POSE_DOWN",
  "HEAD_POSE_SIDE",
  "HEAD_POSE_UP",
  "GAZE_AWAY",
  "CLIENT_MISMATCH",
  "VOICE_DETECTED",
  "MULTIPLE_SPEAKERS",
  "HIGH_NOISE",
  "DEVICE_DISCONNECTED",
  "STREAM_ERROR",
  "MODEL_UNAVAILABLE",
  "VIDEO_MISSING",
  "AUDIO_MISSING",
  "WINDOW_GAP",
  "FACE_OCCLUDED",
  "MOUTH_OCCLUDED",
  "CAMERA_BLOCKED",
  "VOICE_MISMATCH",
  "VOICE_UNVERIFIED",
  "LIP_SYNC_MISMATCH",
  "BACKGROUND_AUDIO",
]
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
function validIncident(value: unknown): value is BrowserIncident {
  if (!value || typeof value !== "object") return false
  const row = value as Record<string, unknown>
  return (
    Object.keys(row).sort().join() === "duration_ms,event_id,kind,observed_at" &&
    typeof row.event_id === "string" &&
    uuid.test(row.event_id) &&
    typeof row.kind === "string" &&
    kinds.includes(row.kind as IncidentKind) &&
    typeof row.observed_at === "string" &&
    Number.isFinite(Date.parse(row.observed_at)) &&
    /(?:Z|[+-]\d{2}:\d{2})$/.test(row.observed_at) &&
    typeof row.duration_ms === "number" &&
    Number.isInteger(row.duration_ms) &&
    row.duration_ms >= 0 &&
    row.duration_ms <= 86_400_000
  )
}

/** Local queue capacity. Ordinary events stop at `QUEUE_CAP - 1`; the last slot is reserved for one overflow marker. */
export const QUEUE_CAP = 500
const OVERFLOW_WARNING =
  "La cola llegó a 500 incidentes y se descartan los nuevos hasta sincronizar; quedó registrado un fallo técnico. Reconectá y sincronizá antes de continuar."

/**
 * Persist before send; server acknowledgements are the only removal authority.
 *
 * Overflow policy: a full queue can no longer hold an incident that says "events were dropped", so ordinary events
 * are accepted only up to `QUEUE_CAP - 1`. The first event refused at that point writes one local overflow marker
 * into the reserved last slot — an existing allowed kind, `STREAM_ERROR` ("Fallo técnico en la captura") — and
 * raises the visible warning; later refusals add nothing more. The marker is armed again once a sync leaves room.
 */
export class IncidentQueue {
  private overflowMarked = false
  private events: BrowserIncident[]
  private sending: Promise<void> | null = null
  private key: string
  private send: (events: BrowserIncident[]) => Promise<BatchResult>
  private warning: (message: string) => void
  constructor(key: string, send: (events: BrowserIncident[]) => Promise<BatchResult>, warning: (message: string) => void) {
    this.key = key
    this.send = send
    this.warning = warning
    const saved: unknown = JSON.parse(localStorage.getItem(key) ?? "[]")
    if (!Array.isArray(saved) || saved.length > QUEUE_CAP || !saved.every(validIncident))
      throw new Error("La cola local de incidentes no es válida. No se enviará contenido desconocido.")
    this.events = saved
    this.overflowMarked = saved.length >= QUEUE_CAP
  }
  get size() {
    return this.events.length
  }
  private persist() {
    try {
      localStorage.setItem(this.key, JSON.stringify(this.events))
      return true
    } catch {
      this.warning("No se pudo guardar la cola local. La prueba debe pausarse para no perder incidentes.")
      return false
    }
  }
  private push(kind: IncidentKind, durationMs: number) {
    this.events.push({
      event_id: crypto.randomUUID(),
      kind,
      duration_ms: durationMs,
      observed_at: new Date().toISOString(),
    })
    return this.persist()
  }
  add(input: { kind: IncidentKind; duration_ms?: number }) {
    if (this.events.length >= QUEUE_CAP - 1) {
      if (!this.overflowMarked && this.events.length === QUEUE_CAP - 1) {
        this.overflowMarked = true
        this.push("STREAM_ERROR", 0)
      }
      this.warning(OVERFLOW_WARNING)
      return false
    }
    return this.push(input.kind, input.duration_ms ?? 0)
  }
  flush(): Promise<void> {
    if (this.sending) return this.sending
    this.sending = this.drain().finally(() => {
      this.sending = null
    })
    return this.sending
  }
  private async drain() {
    while (this.events.length) {
      const batch = this.events.slice(0, 50)
      const result = await this.send(batch)
      const acknowledged = new Set(result.accepted_ids)
      if (!batch.every((row) => acknowledged.has(row.event_id)))
        throw new Error("El servidor no confirmó todo el lote; se conserva para reintentar.")
      this.events = this.events.filter((row) => !acknowledged.has(row.event_id))
      if (this.events.length < QUEUE_CAP - 1) this.overflowMarked = false
      if (!this.persist()) throw new Error("No se pudo actualizar la cola local.")
    }
  }
}

/** Only browser-reported signals, never proof of fraud or a global keyboard trap. */
export class BrowserMonitor {
  private cleanups: (() => void)[] = []
  private awayAt: number | null = null
  private fullscreen = false
  private lastAction: { kind: IncidentKind; at: number } | null = null
  private area: HTMLElement
  private emit: (event: { kind: IncidentKind; duration_ms?: number }) => void
  private notice: (message: string) => void
  constructor(
    area: HTMLElement,
    emit: (event: { kind: IncidentKind; duration_ms?: number }) => void,
    notice: (message: string) => void,
  ) {
    this.area = area
    this.emit = emit
    this.notice = notice
  }
  private listen(target: EventTarget, type: string, action: EventListener) {
    target.addEventListener(type, action)
    this.cleanups.push(() => target.removeEventListener(type, action))
  }
  private away() {
    if (this.awayAt !== null) return
    this.awayAt = performance.now()
    this.emit({ kind: "AWAY" })
    this.notice("Se registró una salida del área de prueba. No se aplica una sanción automática.")
  }
  private returned() {
    if (document.visibilityState === "hidden" || this.awayAt === null) return
    this.emit({
      kind: "RETURN",
      duration_ms: Math.min(86_400_000, Math.max(0, Math.round(performance.now() - this.awayAt))),
    })
    this.awayAt = null
  }
  private blocked(event: Event, kind: IncidentKind) {
    event.preventDefault()
    const now = performance.now()
    if (this.lastAction?.kind === kind && now - this.lastAction.at < 150) return
    this.lastAction = { kind, at: now }
    this.emit({ kind })
    this.notice("Acción bloqueada dentro del área supervisada y registrada como incidente de prueba.")
  }
  start() {
    if (this.cleanups.length) return
    this.fullscreen = Boolean(document.fullscreenElement)
    this.listen(document, "visibilitychange", () => {
      if (document.visibilityState === "hidden") this.away()
      else if (document.hasFocus()) this.returned()
    })
    this.listen(window, "blur", () => this.away())
    this.listen(window, "focus", () => this.returned())
    for (const [type, kind] of Object.entries({
      copy: "COPY",
      cut: "CUT",
      paste: "PASTE",
      drop: "DROP",
      contextmenu: "CONTEXT_MENU",
    } as const))
      this.listen(this.area, type, (event) => this.blocked(event, kind))
    this.listen(this.area, "dragover", (event) => event.preventDefault())
    this.listen(this.area, "keydown", (event) => {
      const key = event as KeyboardEvent
      if (key.altKey) return
      const letter = key.key.toLowerCase()
      const kind =
        key.ctrlKey || key.metaKey
          ? ({ c: "COPY", x: "CUT", v: "PASTE" } as const)[letter as "c" | "x" | "v"]
          : undefined
      if (kind) this.blocked(key, kind)
      else if (key.key === "Insert" && (key.shiftKey || key.ctrlKey)) this.blocked(key, key.shiftKey ? "PASTE" : "COPY")
      else if (key.key === "Delete" && key.shiftKey) this.blocked(key, "CUT")
    })
    this.listen(document, "fullscreenchange", () => {
      const current = Boolean(document.fullscreenElement)
      if (this.fullscreen && !current) {
        this.emit({ kind: "FULLSCREEN_EXIT" })
        this.notice("Se registró la salida de pantalla completa.")
      }
      this.fullscreen = current
    })
    this.listen(window, "offline", () => {
      this.emit({ kind: "OFFLINE" })
      this.notice("Sin conexión. Los incidentes pendientes se conservan localmente.")
    })
    this.listen(window, "online", () => this.emit({ kind: "ONLINE" }))
    this.listen(window, "pagehide", () => this.emit({ kind: "PAGE_EXIT" }))
    if (document.visibilityState === "hidden") this.away()
  }
  stop() {
    this.cleanups.splice(0).forEach((cleanup) => cleanup())
    this.awayAt = null
  }
}
