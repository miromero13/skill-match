import { useState } from "react"
import { AlertCircle, CheckCircle2 } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { GazeCalibrationStep } from "@/components/integrity/gaze-calibration-step"
import { VoiceCalibrationStep, type VoiceRecorder } from "@/components/integrity/voice-calibration-step"
import type { VoiceCalibrationRequest, GazeCalibrationPoint, Trial } from "@/services/browser-supervision"
import type { MouthSampleDTO } from "@/services/gaze-tracking"

/** A trial is calibrated when the server holds both its screen zone and its voiceprint. */
export const isCalibrated = (trial: Pick<Trial, "gaze_zone" | "voice_enrolled"> | null | undefined) =>
  Boolean(trial?.gaze_zone && trial.voice_enrolled)

export interface CalibrationGateProps {
  trial: Trial
  captureFrame: () => string | null
  recorder: VoiceRecorder
  readMouth: (startedAt: number, durationMs: number) => MouthSampleDTO[]
  submitGaze: (points: GazeCalibrationPoint[]) => Promise<{ message: string }>
  submitVoice: (request: VoiceCalibrationRequest) => Promise<{ message: string }>
}

/**
 * Hard gate of the trial (decision L10): supervision starts only after the gaze zone and the voiceprint are
 * calibrated, in that order. A trial the server already reports as calibrated (seeded from a valid pre-exam
 * calibration) skips it; a trial that starts uncalibrated keeps both steps on screen, with their results, once done.
 */
export function CalibrationGate({ trial, captureFrame, recorder, readMouth, submitGaze, submitVoice }: CalibrationGateProps) {
  const [guided] = useState(() => !isCalibrated(trial))
  if (!guided) return null
  const calibrated = isCalibrated(trial)
  const step = trial.gaze_zone ? 2 : 1
  return (
    <section data-testid="calibration-gate" aria-label="Calibración obligatoria" className="space-y-4">
      <Alert className={calibrated ? "" : "border-amber-500/50"}>
        {calibrated ? <CheckCircle2 /> : <AlertCircle />}
        <AlertDescription>
          {calibrated
            ? "Calibración completa. La supervisión continua está activa."
            : step === 1
              ? "Paso 1 de 2: calibrá tu mirada. La supervisión no empieza hasta que completes la mirada y la voz. Mantené tu rostro dentro de la cámara y seguí cada punto solo con la vista, sin mover la cabeza. Si falla, podés reintentar."
              : "Paso 2 de 2: calibrá tu voz. Quedate en silencio unos segundos y después leé la frase en voz alta, mirando a la cámara. La supervisión empieza apenas termine. Si falla, podés reintentar."}
        </AlertDescription>
      </Alert>
      <GazeCalibrationStep captureFrame={captureFrame} submit={submitGaze} />
      {trial.gaze_zone && (
        <VoiceCalibrationStep recorder={recorder} captureFrame={captureFrame} readMouth={readMouth} submit={submitVoice} />
      )}
    </section>
  )
}
