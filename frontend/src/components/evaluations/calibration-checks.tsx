import { Badge } from "@/components/ui/badge"

/** Spanish labels of every check the engine returns (REQUIRED_CHECKS); an unknown key falls back to itself. */
export const CHECK_LABELS: Record<string, string> = {
  lighting: "Iluminación suficiente",
  sharpness: "Imagen nítida",
  framing: "Encuadre del rostro",
  passive_screen_check: "Sin patrones de pantalla evidentes (heurística)",
  camera_live: "Cámara en vivo",
  single_face: "Una sola persona visible",
  face_uncovered: "Rostro descubierto",
  mouth_uncovered: "Boca descubierta",
  identity: "Coincidencia con el rostro enrolado",
  frontal: "Rostro de frente",
  liveness: "Giro de cabeza solicitado",
  occlusion_reference: "Referencia del rostro sin tapar",
  gaze_zone: "Zona de pantalla calibrada (mirada)",
  background_quiet: "Fondo sin voz durante el silencio",
  microphone: "Voz detectada al leer la frase",
  speech_pause: "Pausa sin voz después de la frase",
  single_speaker: "Una sola voz",
  no_overlap: "Sin voces superpuestas",
  mouth_telemetry: "Lectura de la boca confiable",
  mouth_audio_sync: "Boca sincronizada con la voz",
  voiceprint: "Huella de voz registrada",
}

export const checkLabel = (key: string) => CHECK_LABELS[key] ?? key

/** Every returned check with its verdict; the ones to review come first. */
export function CalibrationChecks({ checks }: { checks: Record<string, boolean> }) {
  const entries = Object.entries(checks).sort(([, a], [, b]) => Number(a) - Number(b))
  return (
    <ul aria-label="Resultado de cada control" className="grid gap-2 sm:grid-cols-2">
      {entries.map(([key, passed]) => (
        <li key={key} className="flex items-start gap-2 text-xs leading-relaxed">
          <Badge variant={passed ? "secondary" : "destructive"}>{passed ? "Correcto" : "Revisar"}</Badge>
          {checkLabel(key)}
        </li>
      ))}
    </ul>
  )
}
