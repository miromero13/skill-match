import { create } from "zustand"
import type { TheoryProgress } from "@/services/theory-exam-service"

interface TheoryExamState {
  progress: TheoryProgress | null
  setProgress: (progress: TheoryProgress | null) => void
}

// No audio, transcripts or answer keys are persisted in browser storage.
export const useTheoryExamStore = create<TheoryExamState>(set => ({
  progress: null,
  setProgress: progress => set({ progress }),
}))
