export interface DatasetSample {
  id: string
  discipline: string
  challenge: string
  hardware_info: string
  signed_consent: boolean
  file_format: string
  file_size_bytes: number
  file_hash_sha256: string
  storage_path: string
  uploaded_by_id?: string | null
  participant_id?: string | null
  level_label?: string | null
  manual_touch_count?: number | null
  noise_level?: string | null
  surface?: string | null
  split?: string | null
  created_at: string
  updated_at: string
}

export interface DatasetSampleUploadPayload {
  file: File | Blob
  fileName: string
  discipline: string
  challenge: string
  hardware_info: string
  signed_consent: boolean
  file_hash_sha256?: string
  participant_id?: string
  level_label?: string
  manual_touch_count?: number
  noise_level?: string
  surface?: string
  split?: string
}

export interface DatasetSampleContent {
  id: string
  file_format: string
  mime_type: string
  data_url: string | null
  text_preview: string | null
}

export interface FluteDatasetPreviewSample {
  id: string
  note: string
  variation: string
  challenge: string
  measured_hz: number
  hands_required: number
  split: string
  file_format: string
  created_at: string | null
}

export interface FluteDatasetPreviewResponse {
  samples: FluteDatasetPreviewSample[]
  total_count: number
  notes_count: Record<string, number>
  variations_count: Record<string, number>
  notes_covered: number
  total_notes_required: number
}

export interface FluteModelVersionItem {
  id: string
  nombre: string
  version: string
  ruta_onnx: string
  activa: boolean
  metricas: {
    test_samples?: number
    total_samples_count?: number
    real_samples_count?: number
    notes_covered?: number
    notes_count?: Record<string, number>
    rule_baseline_accuracy?: number
    trained_exact_accuracy?: number
    trained_within_one_level_accuracy?: number
    beats_rule_baseline?: boolean
    confusion_matrix?: number[][]
    loss_history?: Array<{ epoch: number; loss: number }>
    latency_ms_per_inference?: number
    skill_id?: string | null
    classes?: string[]
  }
  created_at: string
}
