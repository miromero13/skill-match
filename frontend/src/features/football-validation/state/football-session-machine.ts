export type FootballSessionState =
  | "created"
  | "env_check"
  | "liveness"
  | "calibration"
  | "recording"
  | "uploading"
  | "processing"
  | "scored"
  | "needs_review"
  | "failed"

export type ChallengeSegmentType = "LOW" | "HIGH" | "SLOW" | "FAST"

export interface ChallengeSegment {
  indice: number
  tipo: ChallengeSegmentType
  inicio_servidor_ms: number
  duracion_ms: number
  cumplimiento?: number | null
  latencia_reaccion_ms?: number | null
}

export interface CreateValidationSessionResponse {
  session_id: string
  ws_url: string
  semilla: number
  intentos_restantes: number
  estado: FootballSessionState
  version_modelo: string
  version_config: string
}

export interface ValidationSessionStatusResponse {
  id: string
  user_id: string
  skill_id?: string | null
  estado: FootballSessionState
  semilla: number
  creada_en: string
  finalizada_en?: string | null
  version_modelo: string
  version_config: string
  segments: ChallengeSegment[]
  confirmed_chunks: number[]
}

export interface EnvCheckPayload {
  brightness: number
  noise_db: number
  face_detected: boolean
  ball_detected: boolean
  latency_ms: number
}

export interface EnvCheckResponse {
  session_id: string
  passed: boolean
  estado: FootballSessionState
  failures: string[]
}

export interface LivenessPayload {
  challenge_passed: boolean
  gesture_code: string
  confidence: number
}

export interface LivenessResponse {
  session_id: string
  passed: boolean
  estado: FootballSessionState
}

export interface CalibrationPayload {
  client_touch_timestamp_ms: number
  estimated_ball_radius_px?: number
}

export interface CalibrationResponse {
  session_id: string
  client_touch_timestamp_ms: number
  estado: FootballSessionState
}

export interface ChunkUploadResponse {
  session_id: string
  chunk_index: number
  sha256: string
  size_bytes: number
  storage_uri: string
  idempotent_replay: boolean
  estado: FootballSessionState
}

export interface FinalizeSessionPayload {
  expected_chunks?: number
  duration_seconds?: number
  fps?: number
}

export interface FinalizeSessionResponse {
  session_id: string
  estado: FootballSessionState
  assembled_uri: string
  assembled_sha256: string
  assembled_size_bytes: number
  total_chunks: number
  task_id?: string | null
}

export interface FraudIncidentItem {
  tipo: string
  severidad: string
  t_ms: number
  detalle?: string | null
}

export interface ValidationMetricsPayload {
  toques: number
  racha: number
  toques_por_minuto: number
  altura_media: number
  regularidad: number
  cumplimiento_por_tramo: ChallengeSegment[]
}

export interface ValidationResultPayload {
  session_id: string
  estado: FootballSessionState
  nivel: "Principiante" | "Intermedio" | "Avanzado" | "Experto" | string
  probabilidades: Record<string, number>
  confianza: number
  metricas: ValidationMetricsPayload
  coherencia_audio_video: number
  puntaje_riesgo: number
  incidencias: FraudIncidentItem[]
  retroalimentacion: {
    fortalezas: string[]
    mejoras: string[]
  }
  requiere_revision: boolean
  version_modelo: string
  version_config: string
}

export interface FootballValidationMachineState {
  sessionId: string | null
  wsUrl: string | null
  seed: number | null
  remainingAttempts: number | null
  serverState: FootballSessionState
  segments: ChallengeSegment[]
  confirmedChunks: number[]
  envFailures: string[]
  assembledSha256: string | null
  assembledUri: string | null
  errorMessage: string | null
}

export type FootballValidationAction =
  | { type: "SESSION_CREATED"; payload: CreateValidationSessionResponse }
  | { type: "STATUS_SYNCED"; payload: ValidationSessionStatusResponse }
  | { type: "ENV_CHECK_UPDATED"; payload: EnvCheckResponse }
  | { type: "STATE_UPDATED"; payload: { estado: FootballSessionState } }
  | { type: "CHUNK_CONFIRMED"; payload: { chunkIndex: number; estado: FootballSessionState } }
  | { type: "SESSION_FINALIZED"; payload: FinalizeSessionResponse }
  | { type: "SET_ERROR"; payload: string | null }
  | { type: "RESET" }

export const initialFootballValidationState: FootballValidationMachineState = {
  sessionId: null,
  wsUrl: null,
  seed: null,
  remainingAttempts: null,
  serverState: "created",
  segments: [],
  confirmedChunks: [],
  envFailures: [],
  assembledSha256: null,
  assembledUri: null,
  errorMessage: null,
}

export function footballValidationReducer(
  state: FootballValidationMachineState,
  action: FootballValidationAction
): FootballValidationMachineState {
  switch (action.type) {
    case "SESSION_CREATED":
      return {
        ...state,
        sessionId: action.payload.session_id,
        wsUrl: action.payload.ws_url,
        seed: action.payload.semilla,
        remainingAttempts: action.payload.intentos_restantes,
        serverState: action.payload.estado,
        confirmedChunks: [],
        envFailures: [],
        errorMessage: null,
      }
    case "STATUS_SYNCED":
      return {
        ...state,
        sessionId: action.payload.id,
        seed: action.payload.semilla,
        serverState: action.payload.estado,
        segments: action.payload.segments,
        confirmedChunks: action.payload.confirmed_chunks,
        errorMessage: null,
      }
    case "ENV_CHECK_UPDATED":
      return {
        ...state,
        serverState: action.payload.estado,
        envFailures: action.payload.failures,
        errorMessage:
          action.payload.failures.length > 0
            ? action.payload.failures.join(" ")
            : null,
      }
    case "STATE_UPDATED":
      return {
        ...state,
        serverState: action.payload.estado,
        errorMessage: null,
      }
    case "CHUNK_CONFIRMED": {
      const nextConfirmed = state.confirmedChunks.includes(
        action.payload.chunkIndex
      )
        ? state.confirmedChunks
        : [...state.confirmedChunks, action.payload.chunkIndex].sort(
            (a, b) => a - b
          )
      return {
        ...state,
        serverState: action.payload.estado,
        confirmedChunks: nextConfirmed,
      }
    }
    case "SESSION_FINALIZED":
      return {
        ...state,
        serverState: action.payload.estado,
        assembledSha256: action.payload.assembled_sha256,
        assembledUri: action.payload.assembled_uri,
        errorMessage: null,
      }
    case "SET_ERROR":
      return {
        ...state,
        errorMessage: action.payload,
      }
    case "RESET":
      return initialFootballValidationState
    default:
      return state
  }
}
