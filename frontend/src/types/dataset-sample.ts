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
