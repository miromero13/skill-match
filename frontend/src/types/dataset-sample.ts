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
}
