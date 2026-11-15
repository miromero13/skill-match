import { create } from "zustand"
import type { DatasetSample } from "@/types/dataset-sample"
import {
  calculateFileSha256,
  deleteDatasetSample,
  getDatasetSamples,
  uploadDatasetSample,
} from "@/services/dataset-sample-service"

interface DatasetCaptureState {
  // Grabación y multimedia
  isRecording: boolean
  recordingDurationSeconds: number
  recordingMode: "video" | "audio" | "code"
  recordedBlob: Blob | null
  recordedFileName: string | null
  recordedFileHash: string | null
  mediaStream: MediaStream | null

  // Metadatos
  discipline: string
  challenge: string
  hardwareInfo: string
  signedConsent: boolean
  codeContent: string

  // Muestras existentes
  samples: DatasetSample[]
  totalCount: number
  isLoading: boolean
  isUploading: boolean
  error: string | null
  lastUploadMessage: string | null

  // Métodos
  setRecordingMode: (mode: "video" | "audio" | "code") => void
  setDiscipline: (discipline: string) => void
  setChallenge: (challenge: string) => void
  setHardwareInfo: (hardwareInfo: string) => void
  setSignedConsent: (signedConsent: boolean) => void
  setCodeContent: (code: string) => void
  setMediaStream: (stream: MediaStream | null) => void
  setRecordedBlob: (blob: Blob | null, fileName: string | null) => Promise<void>
  setRecordingDurationSeconds: (seconds: number) => void
  setIsRecording: (isRecording: boolean) => void
  resetRecording: () => void

  // Operaciones API
  fetchSamples: (discipline?: string) => Promise<void>
  uploadCurrentCapture: () => Promise<boolean>
  deleteSampleById: (id: string) => Promise<void>
  clearLastUploadMessage: () => void
}

export const useDatasetCaptureStore = create<DatasetCaptureState>((set, get) => ({
  isRecording: false,
  recordingDurationSeconds: 0,
  recordingMode: "video",
  recordedBlob: null,
  recordedFileName: null,
  recordedFileHash: null,
  mediaStream: null,

  discipline: "musica",
  challenge: "guitarra-acustica",
  hardwareInfo: typeof navigator !== "undefined" ? navigator.userAgent.slice(0, 80) : "Default Hardware",
  signedConsent: false,
  codeContent: "# Código de prueba piloto\ndef solution():\n    return 42\n",

  samples: [],
  totalCount: 0,
  isLoading: false,
  isUploading: false,
  error: null,
  lastUploadMessage: null,

  setRecordingMode: (mode) => set({ recordingMode: mode }),
  setDiscipline: (discipline) => set({ discipline }),
  setChallenge: (challenge) => set({ challenge }),
  setHardwareInfo: (hardwareInfo) => set({ hardwareInfo }),
  setSignedConsent: (signedConsent) => set({ signedConsent }),
  setCodeContent: (codeContent) => set({ codeContent }),
  setMediaStream: (mediaStream) => set({ mediaStream }),
  setRecordingDurationSeconds: (seconds) => set({ recordingDurationSeconds: seconds }),
  setIsRecording: (isRecording) => set({ isRecording }),

  setRecordedBlob: async (blob, fileName) => {
    if (!blob) {
      set({ recordedBlob: null, recordedFileName: null, recordedFileHash: null })
      return
    }
    const hash = await calculateFileSha256(blob)
    set({
      recordedBlob: blob,
      recordedFileName: fileName || `capture-${Date.now()}.${blob.type.includes("audio") ? "wav" : "mp4"}`,
      recordedFileHash: hash,
    })
  },

  resetRecording: () => {
    const { mediaStream } = get()
    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop())
    }
    set({
      isRecording: false,
      recordingDurationSeconds: 0,
      recordedBlob: null,
      recordedFileName: null,
      recordedFileHash: null,
      mediaStream: null,
    })
  },

  fetchSamples: async (discipline) => {
    set({ isLoading: true, error: null })
    try {
      const response = await getDatasetSamples(1, 100, discipline)
      set({
        samples: response.data || [],
        totalCount: response.count ?? response.data?.length ?? 0,
        isLoading: false,
      })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al cargar muestras"
      set({ error: msg, isLoading: false })
    }
  },

  uploadCurrentCapture: async () => {
    const state = get()
    if (!state.signedConsent) {
      set({ error: "Debe otorgar el consentimiento explícito antes de subir la muestra." })
      return false
    }

    let blobToUpload: Blob | null = state.recordedBlob
    let fileName = state.recordedFileName || `capture-${Date.now()}`

    if (state.recordingMode === "code") {
      blobToUpload = new Blob([state.codeContent], { type: "text/x-python" })
      fileName = fileName.endsWith(".py") ? fileName : `${fileName}.py`
    }

    if (!blobToUpload) {
      set({ error: "No hay ninguna muestra multimedia o código capturado para subir." })
      return false
    }

    set({ isUploading: true, error: null })

    try {
      const hash = state.recordedFileHash || (await calculateFileSha256(blobToUpload))
      const response = await uploadDatasetSample({
        file: blobToUpload,
        fileName,
        discipline: state.discipline,
        challenge: state.challenge,
        hardware_info: state.hardwareInfo,
        signed_consent: state.signedConsent,
        file_hash_sha256: hash,
      })

      set({
        isUploading: false,
        lastUploadMessage: response.message,
      })

      // Limpiar grabación y refrescar lista
      state.resetRecording()
      await state.fetchSamples(state.discipline)
      return true
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error durante la subida"
      set({ error: msg, isUploading: false })
      return false
    }
  },

  deleteSampleById: async (id: string) => {
    try {
      await deleteDatasetSample(id)
      const current = get().samples.filter((s) => s.id !== id)
      set({ samples: current, totalCount: Math.max(0, get().totalCount - 1) })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al eliminar la muestra"
      set({ error: msg })
    }
  },

  clearLastUploadMessage: () => set({ lastUploadMessage: null }),
}))
