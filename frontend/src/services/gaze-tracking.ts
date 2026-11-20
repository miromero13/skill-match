/**
 * Browser-side gaze tracking (S5 / S12): MediaPipe FaceLandmarker in the page at ~15 fps.
 *
 * The browser only produces live signals (a non-blocking "Mirá a la pantalla" hint and the telemetry attached
 * to each audiovisual window). The server re-measures the sampled JPEG frames, is authoritative and flags any
 * disagreement as CLIENT_MISMATCH.
 *
 * The feature formulas below mirror `backend/app/services/integrity/gaze.py` and the pose block of
 * `frame_analyzer.analyze_mediapipe`; `src/test/gaze-tracking.test.ts` pins both sides with the same fixtures.
 * Conventions: normalized landmarks of the *unmirrored* camera frame; gaze_h > 0 toward the image right,
 * gaze_v > 0 down; head pitch > 0 looking down, yaw > 0 toward the image right.
 */

// ---- thresholds shared with the backend (backend/app/services/integrity/thresholds.py) -----------------
export const GAZE_BLINK_SCORE = 0.55
export const GAZE_CLOSED_LID_RATIO = 0.08
export const GAZE_GAIN_H = 2.0
export const GAZE_GAIN_V = 1.5
export const GAZE_BLENDSHAPE_WEIGHT = 0.5
export const MP_MATRIX_WEIGHT = 0.55
export const MP_LANDMARK_WEIGHT = 0.45
export const GAZE_TOLERANCE_MS = 1000
export const GAZE_BLINK_MAX_MS = 800
export const TELEMETRY_MIN_SPACING_MS = 30
export const TELEMETRY_MAX_SAMPLES = 60
export const TRACKER_FPS = 15
/** Mouth readings the server accepts for one voice calibration (backend schemas/browser_supervision.py). */
export const MOUTH_MAX_SAMPLES = 450
export const MOUTH_OPEN_MAX = 2

export interface GazeZone {
  pitch_min: number
  pitch_max: number
  yaw_min: number
  yaw_max: number
  gaze_h_min: number
  gaze_h_max: number
  gaze_v_min: number
  gaze_v_max: number
}

/** Conservative limits used until the trial has a calibrated zone (same as the backend defaults). */
export const DEFAULT_GAZE_ZONE: GazeZone = {
  pitch_min: -15,
  pitch_max: 20,
  yaw_min: -16,
  yaw_max: 16,
  gaze_h_min: -0.6,
  gaze_h_max: 0.6,
  gaze_v_min: -0.5,
  gaze_v_max: 0.6,
}

export interface Point {
  x: number
  y: number
  z?: number
}

export interface GazeMeasurement {
  gazeH: number | null
  gazeV: number | null
  blink: boolean
}

// (corner at the image-left, corner at the image-right, upper lid, lower lid, iris center)
const EYES: ReadonlyArray<readonly [number, number, number, number, number]> = [
  [33, 133, 159, 145, 468],
  [362, 263, 386, 374, 473],
]
const LANDMARK_COUNT = 478

const clip = (value: number) => Math.max(-1, Math.min(1, value))
const degrees = (radians: number) => (radians * 180) / Math.PI
const mean = (values: number[]) => values.reduce((sum, value) => sum + value, 0) / values.length

/** Gaze from the iris centers (vs eye corners for h, vs lids for v) blended with the eyeLook* blendshapes. */
export function measureGaze(points: ReadonlyArray<Point>, blendshapes: Readonly<Record<string, number>>): GazeMeasurement {
  const horizontal: number[] = []
  const vertical: number[] = []
  const openings: number[] = []
  if (points.length >= LANDMARK_COUNT) {
    for (const [left, right, upper, lower, iris] of EYES) {
      const ax = points[right].x - points[left].x
      const ay = points[right].y - points[left].y
      const width = Math.hypot(ax, ay)
      if (width < 1e-4) continue
      const ux = ax / width
      const uy = ay / width
      const dx = -uy // in-image perpendicular pointing down for an upright eye
      const dy = ux
      const midX = (points[left].x + points[right].x) / 2
      const midY = (points[left].y + points[right].y) / 2
      horizontal.push(
        clip((GAZE_GAIN_H * ((points[iris].x - midX) * ux + (points[iris].y - midY) * uy)) / (width / 2)),
      )
      const opening = (points[lower].x - points[upper].x) * dx + (points[lower].y - points[upper].y) * dy
      openings.push(opening / width)
      if (opening > 1e-6) {
        const lidX = (points[upper].x + points[lower].x) / 2
        const lidY = (points[upper].y + points[lower].y) / 2
        vertical.push(
          clip((GAZE_GAIN_V * ((points[iris].x - lidX) * dx + (points[iris].y - lidY) * dy)) / (opening / 2)),
        )
      }
    }
  }
  const blink = isBlink(blendshapes, openings)
  if (!horizontal.length || !vertical.length) return { gazeH: null, gazeV: null, blink }
  const geoH = mean(horizontal)
  const geoV = mean(vertical)
  if (Object.keys(blendshapes).some((name) => name.startsWith("eyeLook"))) {
    const bs = (name: string) => blendshapes[name] ?? 0
    // ARKit semantics: the subject's left eye is the image-right one.
    const bsH = (bs("eyeLookOutLeft") + bs("eyeLookInRight") - (bs("eyeLookInLeft") + bs("eyeLookOutRight"))) / 2
    const bsV = (bs("eyeLookDownLeft") + bs("eyeLookDownRight") - (bs("eyeLookUpLeft") + bs("eyeLookUpRight"))) / 2
    const w = GAZE_BLENDSHAPE_WEIGHT
    return { gazeH: (1 - w) * geoH + w * bsH, gazeV: (1 - w) * geoV + w * bsV, blink }
  }
  return { gazeH: geoH, gazeV: geoV, blink }
}

/**
 * Mouth aperture, the same score as `gaze.mouth_open_score` on the server (T8 / S11): the largest of the
 * close-softened jawOpen blendshape, the inner-lip aspect ratio (landmarks 13/14 over the mouth width 78/308,
 * x1.4) and the funnel/pucker blendshapes (x0.55). `src/test/gaze-tracking.test.ts` pins the same fixtures as
 * `backend/tests/test_mouth_open_parity.py`.
 */
export function mouthOpenScore(points: ReadonlyArray<Point>, blendshapes: Readonly<Record<string, number>>): number {
  const jawOpen = blendshapes.jawOpen ?? 0
  const mouthClose = blendshapes.mouthClose ?? 0
  const funnel = (blendshapes.mouthFunnel ?? 0) + 0.5 * (blendshapes.mouthPucker ?? 0)
  let ratio = 0
  if (points.length > 308) {
    const lipVert = Math.hypot(points[14].x - points[13].x, points[14].y - points[13].y)
    const mouthWidth = Math.max(Math.hypot(points[308].x - points[78].x, points[308].y - points[78].y), 1e-4)
    ratio = lipVert / mouthWidth
  }
  return Math.max(jawOpen * Math.max(0.2, 1 - 0.55 * mouthClose), ratio * 1.4, funnel * 0.55)
}

function isBlink(blendshapes: Readonly<Record<string, number>>, openingRatios: number[]) {
  if ("eyeBlinkLeft" in blendshapes || "eyeBlinkRight" in blendshapes) {
    const score = ((blendshapes.eyeBlinkLeft ?? 0) + (blendshapes.eyeBlinkRight ?? 0)) / 2
    return score >= GAZE_BLINK_SCORE
  }
  return openingRatios.length > 0 && openingRatios.every((ratio) => ratio < GAZE_CLOSED_LID_RATIO)
}

/**
 * Head pitch/yaw in degrees: 55 % facial transformation matrix + 45 % landmark geometry, like the server.
 * `matrix` is MediaPipe's flattened 4x4 in column-major order (the third column is the face's forward axis).
 */
export function headPose(points: ReadonlyArray<Point>, matrix: ReadonlyArray<number> | null): { pitch: number; yaw: number } {
  const forehead = points[10]
  const chin = points[152]
  const lmPitch = degrees(Math.atan2((chin.z ?? 0) - (forehead.z ?? 0), Math.max(chin.y - forehead.y, 1e-4)))
  const eyeMidX = (points[33].x + points[263].x) / 2
  const eyeDist = Math.max(Math.hypot(points[263].x - points[33].x, points[263].y - points[33].y), 1e-4)
  const lmYaw = degrees(Math.atan2(points[1].x - eyeMidX, eyeDist * 0.75))
  let matrixPitch = lmPitch
  let matrixYaw = lmYaw
  if (matrix && matrix.length === 16) {
    const norm = Math.max(Math.hypot(matrix[8], matrix[9], matrix[10]), 1e-6)
    const fx = matrix[8] / norm
    const fy = matrix[9] / norm
    const fz = matrix[10] / norm
    matrixYaw = degrees(Math.atan2(fx, Math.abs(fz)))
    matrixPitch = degrees(Math.asin(Math.max(-1, Math.min(1, -fy))))
  }
  return {
    pitch: MP_MATRIX_WEIGHT * matrixPitch + MP_LANDMARK_WEIGHT * lmPitch,
    yaw: MP_MATRIX_WEIGHT * matrixYaw + MP_LANDMARK_WEIGHT * lmYaw,
  }
}

// ---- classification (mirror of gaze.classify without the server-only orientation fallback) ----------------

export type GazeLabel = "IN" | "NEUTRAL" | "BLINK" | "HEAD_POSE_DOWN" | "HEAD_POSE_UP" | "HEAD_POSE_SIDE" | "GAZE_AWAY"

export interface GazeReading {
  faceCount: number
  headPitch: number | null
  headYaw: number | null
  gazeH: number | null
  gazeV: number | null
  blink: boolean
  /** Mouth aperture score (`mouthOpenScore`); absent or null when the face could not be measured. */
  mouthOpen?: number | null
}

export function classifyReading(reading: GazeReading, zone: GazeZone | null): GazeLabel {
  if (reading.faceCount !== 1) return "NEUTRAL"
  const { headPitch, headYaw, gazeH, gazeV } = reading
  if (headPitch === null || headYaw === null || gazeH === null) return "NEUTRAL"
  const bounds = zone ?? DEFAULT_GAZE_ZONE
  if (headPitch > bounds.pitch_max) return "HEAD_POSE_DOWN"
  if (headPitch < bounds.pitch_min) return "HEAD_POSE_UP"
  if (headYaw < bounds.yaw_min || headYaw > bounds.yaw_max) return "HEAD_POSE_SIDE"
  if (reading.blink) return "BLINK"
  if (gazeV === null) return "NEUTRAL"
  if (gazeH < bounds.gaze_h_min || gazeH > bounds.gaze_h_max || gazeV < bounds.gaze_v_min || gazeV > bounds.gaze_v_max)
    return "GAZE_AWAY"
  return "IN"
}

/**
 * Live "away" state for the UX hint: away once the head or the eyes have stayed outside the zone for more than
 * `GAZE_TOLERANCE_MS`. Blinks and unmeasurable frames neither start nor break a stretch; eyes closed for longer
 * than `GAZE_BLINK_MAX_MS` count as away. The server decides what is an incident.
 */
export class AwayTracker {
  private awaySince: number | null = null
  private blinkSince: number | null = null

  update(label: GazeLabel, atMs: number): boolean {
    let effective = label
    if (label === "BLINK") {
      this.blinkSince ??= atMs
      if (atMs - this.blinkSince > GAZE_BLINK_MAX_MS) {
        effective = "GAZE_AWAY"
        this.awaySince ??= this.blinkSince // the whole closed stretch counts, like the server's promotion
      }
    } else {
      this.blinkSince = null
    }
    if (effective === "IN") this.awaySince = null
    else if (effective !== "NEUTRAL" && effective !== "BLINK") this.awaySince ??= atMs
    return this.awaySince !== null && atMs - this.awaySince > GAZE_TOLERANCE_MS
  }

  reset() {
    this.awaySince = null
    this.blinkSince = null
  }
}

// ---- telemetry --------------------------------------------------------------------------------------------

/** Wire shape of `gaze_samples` in the audiovisual window payload. */
export interface GazeSampleDTO {
  t_ms: number
  head_pitch: number | null
  head_yaw: number | null
  gaze_h: number | null
  gaze_v: number | null
  blink: boolean
  face_count: number
  /** Mouth aperture score; null when not measured (never 0 for "unknown"). */
  mouth_open: number | null
}

/** Wire shape of `mouth_samples` in the voice calibration payload; `t_ms` counts from the recording start. */
export interface MouthSampleDTO {
  t_ms: number
  mouth_open: number
}

export interface TimedReading extends GazeReading {
  at: number // epoch ms
}

const round = (value: number | null, digits: number) => (value === null ? null : Number(value.toFixed(digits)))

/** Samples inside [startMs, startMs + durationMs], as offsets from the window start, thinned to the server limits. */
export function samplesForWindow(readings: ReadonlyArray<TimedReading>, startMs: number, durationMs: number): GazeSampleDTO[] {
  const out: GazeSampleDTO[] = []
  for (const reading of readings) {
    const offset = Math.round(reading.at - startMs)
    if (offset < 0 || offset > durationMs) continue
    const previous = out.at(-1)
    if (previous && offset - previous.t_ms < TELEMETRY_MIN_SPACING_MS) continue
    out.push({
      t_ms: offset,
      head_pitch: round(reading.headPitch, 2),
      head_yaw: round(reading.headYaw, 2),
      gaze_h: round(reading.gazeH, 3),
      gaze_v: round(reading.gazeV, 3),
      blink: reading.blink,
      face_count: Math.min(10, reading.faceCount),
      mouth_open: reading.mouthOpen == null ? null : round(Math.min(MOUTH_OPEN_MAX, Math.max(0, reading.mouthOpen)), 3),
    })
    if (out.length >= TELEMETRY_MAX_SAMPLES) break
  }
  return out
}

/** Single-face mouth readings inside [startMs, startMs + durationMs] as offsets from `startMs`, within the server limits. */
export function mouthSamplesForWindow(readings: ReadonlyArray<TimedReading>, startMs: number, durationMs: number): MouthSampleDTO[] {
  const out: MouthSampleDTO[] = []
  for (const reading of readings) {
    const offset = Math.round(reading.at - startMs)
    if (offset < 0 || offset > durationMs || reading.faceCount !== 1 || reading.mouthOpen == null) continue
    const previous = out.at(-1)
    if (previous && offset - previous.t_ms < TELEMETRY_MIN_SPACING_MS) continue
    out.push({ t_ms: offset, mouth_open: Number(Math.min(MOUTH_OPEN_MAX, Math.max(0, reading.mouthOpen)).toFixed(3)) })
    if (out.length >= MOUTH_MAX_SAMPLES) break
  }
  return out
}

// ---- MediaPipe runtime (self-hosted assets: scripts/install-vision-assets.mjs) --------------------------

export const VISION_ASSET_BASE = "/mediapipe"

interface FaceResult {
  faceLandmarks: Point[][]
  faceBlendshapes?: { categories: { categoryName: string; score: number }[] }[]
  facialTransformationMatrixes?: { data: number[] }[]
}

export interface FaceLandmarkerLike {
  detectForVideo(video: HTMLVideoElement, timestampMs: number): FaceResult
  close(): void
}

/** Turns one FaceLandmarker result into a reading (exported for tests). */
export function readingFromResult(result: FaceResult, at: number): TimedReading {
  const faceCount = result.faceLandmarks.length
  if (faceCount !== 1) {
    return { at, faceCount, headPitch: null, headYaw: null, gazeH: null, gazeV: null, blink: false, mouthOpen: null }
  }
  const points = result.faceLandmarks[0]
  const blendshapes: Record<string, number> = {}
  for (const category of result.faceBlendshapes?.[0]?.categories ?? []) blendshapes[category.categoryName] = category.score
  const gaze = measureGaze(points, blendshapes)
  const pose = headPose(points, result.facialTransformationMatrixes?.[0]?.data ?? null)
  return {
    at,
    faceCount,
    headPitch: pose.pitch,
    headYaw: pose.yaw,
    gazeH: gaze.gazeH,
    gazeV: gaze.gazeV,
    blink: gaze.blink,
    mouthOpen: mouthOpenScore(points, blendshapes),
  }
}

export interface EyeOverlay {
  leftCorner: Point
  rightCorner: Point
  upperLid: Point
  lowerLid: Point
  iris: Point
}

export interface IrisOverlay {
  eyes: [EyeOverlay, EyeOverlay]
  gazeH: number | null
  gazeV: number | null
  blink: boolean
}

/** Extracts normalized iris & eye landmarks for live video overlay when a single 478-landmark face is present. */
export function overlayFromResult(result: FaceResult): IrisOverlay | null {
  if (result.faceLandmarks.length !== 1) return null
  const points = result.faceLandmarks[0]
  if (points.length < LANDMARK_COUNT) return null
  const blendshapes: Record<string, number> = {}
  for (const category of result.faceBlendshapes?.[0]?.categories ?? []) blendshapes[category.categoryName] = category.score
  const gaze = measureGaze(points, blendshapes)
  const [e0, e1] = EYES
  return {
    eyes: [
      { leftCorner: points[e0[0]], rightCorner: points[e0[1]], upperLid: points[e0[2]], lowerLid: points[e0[3]], iris: points[e0[4]] },
      { leftCorner: points[e1[0]], rightCorner: points[e1[1]], upperLid: points[e1[2]], lowerLid: points[e1[3]], iris: points[e1[4]] },
    ],
    gazeH: gaze.gazeH,
    gazeV: gaze.gazeV,
    blink: gaze.blink,
  }
}

export interface FaceTrackerOptions {
  /** Called when the live "away" state changes (UX only). */
  onAway?: (away: boolean) => void
  /** Called on each processed frame with normalized iris/eye coordinates for live video overlay. */
  onOverlay?: (overlay: IrisOverlay | null) => void
  fps?: number
  /** Injected for tests; defaults to the self-hosted MediaPipe FaceLandmarker. */
  landmarker?: FaceLandmarkerLike
}

export interface FaceTracker {
  setZone(zone: GazeZone | null): void
  takeSamples(startMs: number, durationMs: number): GazeSampleDTO[]
  /** Mouth readings of [startMs, startMs + durationMs] for the voice calibration (the buffer keeps ~12 s). */
  takeMouthSamples(startMs: number, durationMs: number): MouthSampleDTO[]
  stop(): void
}

const BUFFER_MS = 12_000

async function createLandmarker(): Promise<FaceLandmarkerLike> {
  const { FaceLandmarker, FilesetResolver } = await import("@mediapipe/tasks-vision")
  const fileset = await FilesetResolver.forVisionTasks(`${VISION_ASSET_BASE}/wasm`)
  return FaceLandmarker.createFromOptions(fileset, {
    baseOptions: { modelAssetPath: `${VISION_ASSET_BASE}/face_landmarker.task` },
    runningMode: "VIDEO",
    numFaces: 3,
    minFaceDetectionConfidence: 0.45,
    minFacePresenceConfidence: 0.45,
    outputFaceBlendshapes: true,
    outputFacialTransformationMatrixes: true,
  }) as unknown as Promise<FaceLandmarkerLike>
}

/** Starts tracking `video` at ~15 fps. Rejects when the self-hosted assets or the model are unavailable. */
export async function startFaceTracker(video: HTMLVideoElement, options: FaceTrackerOptions = {}): Promise<FaceTracker> {
  const landmarker = options.landmarker ?? (await createLandmarker())
  const away = new AwayTracker()
  let zone: GazeZone | null = null
  let isAway = false
  let readings: TimedReading[] = []
  let lastVideoTime = -1
  const timer = setInterval(() => {
    if (video.readyState < 2 || video.videoWidth === 0 || video.currentTime === lastVideoTime) return
    lastVideoTime = video.currentTime
    try {
      const now = Date.now()
      const result = landmarker.detectForVideo(video, performance.now())
      const reading = readingFromResult(result, now)
      if (options.onOverlay) options.onOverlay(overlayFromResult(result))
      readings.push(reading)
      readings = readings.filter((item) => now - item.at <= BUFFER_MS)
      const next = away.update(classifyReading(reading, zone), now)
      if (next !== isAway) {
        isAway = next
        options.onAway?.(next)
      }
    } catch {
      // A failed frame is skipped; the server still measures the JPEG frames.
    }
  }, 1000 / (options.fps ?? TRACKER_FPS))
  return {
    setZone(next) {
      zone = next
      away.reset()
    },
    takeSamples: (startMs, durationMs) => samplesForWindow(readings, startMs, durationMs),
    takeMouthSamples: (startMs, durationMs) => mouthSamplesForWindow(readings, startMs, durationMs),
    stop() {
      clearInterval(timer)
      landmarker.close()
    },
  }
}
