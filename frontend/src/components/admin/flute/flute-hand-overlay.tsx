import { useEffect, useRef, useState, type RefObject } from "react"
import { HandLandmarker, FilesetResolver } from "@mediapipe/tasks-vision"
import { countDetectedHands, encodeHandLandmarks, type DetectedHand, type HandFrame } from "./flute-hand-features"

/**
 * MediaPipe HandLandmarker labels handedness assuming a mirrored (selfie) image. The raw
 * camera/video frames passed to detectForVideo are NOT mirrored, so its "Left" is the user's
 * RIGHT hand and vice versa. Returns the user's real hand (slot 0 "Left" = upper hand on the
 * recorder, holes 1-3), or null for unknown categories.
 */
export function userHandFromMediapipe(categoryName: string): DetectedHand["side"] | null {
  if (categoryName === "Left") return "Right"
  if (categoryName === "Right") return "Left"
  return null
}

const BONES = [[0, 1, 2, 3, 4], [0, 5, 6, 7, 8], [5, 9, 10, 11, 12], [9, 13, 14, 15, 16], [13, 17, 18, 19, 20], [0, 17]]

export function FluteHandOverlay({ videoRef, onFrame }: {
  videoRef: RefObject<HTMLVideoElement | null>
  onFrame: (frame: HandFrame | null) => void
}) {
  const callback = useRef(onFrame)
  useEffect(() => { callback.current = onFrame }, [onFrame])
  const [hands, setHands] = useState<DetectedHand[]>([])
  const [size, setSize] = useState({ width: 1280, height: 720 })
  const [status, setStatus] = useState("Cargando detector local de dedos…")

  useEffect(() => {
    let disposed = false
    let detector: HandLandmarker | null = null
    let timer: ReturnType<typeof setInterval> | undefined
    let lastTime = -1
    const start = async () => {
      try {
        const base = import.meta.env.BASE_URL
        const files = await FilesetResolver.forVisionTasks(`${base}mediapipe/wasm`)
        const loaded = await HandLandmarker.createFromOptions(files, {
          baseOptions: { modelAssetPath: `${base}models/hand-landmarker/hand_landmarker.task`, delegate: "CPU" },
          runningMode: "VIDEO", numHands: 2,
          minHandDetectionConfidence: 0.7, minHandPresenceConfidence: 0.7, minTrackingConfidence: 0.7,
        })
        if (disposed) { loaded.close(); return }
        detector = loaded
        timer = setInterval(() => {
          const video = videoRef.current
          if (!video || video.readyState < 2 || video.paused) {
            callback.current(null)
            setHands([])
            setStatus("Esperando video en movimiento para analizar los dedos…")
            return
          }
          if (video.currentTime === lastTime) return
          lastTime = video.currentTime
          try {
            const timestamp = performance.now()
            const result = loaded.detectForVideo(video, timestamp)
            const detected: DetectedHand[] = result.landmarks.flatMap((points, i) => {
              const category = result.handedness[i]?.[0]
              const side = category ? userHandFromMediapipe(category.categoryName) : null
              if (!category || !side) return []
              return [{ side, score: category.score, points }]
            })
            setSize({ width: video.videoWidth, height: video.videoHeight })
            setHands(detected)
            const features = encodeHandLandmarks(detected, video.videoWidth, video.videoHeight)
            callback.current(features ? { features, hands: detected, timestamp } : null)
            const handCount = features ? countDetectedHands(features) : 0
            setStatus(handCount === 0
              ? "Dedos no detectados con confianza · no evaluable"
              : `${handCount} mano(s) · 21 articulaciones por mano · análisis local`)
          } catch {
            callback.current(null)
            setHands([])
            setStatus("No se pudo analizar el video. Reinicia la cámara; no se evaluará la postura.")
            if (timer) clearInterval(timer)
          }
        }, 100)
      } catch {
        if (!disposed) setStatus("No se pudo cargar el detector local. Revisa los archivos del modelo y WASM.")
      }
    }
    void start()
    return () => { disposed = true; if (timer) clearInterval(timer); detector?.close(); callback.current(null) }
  }, [videoRef])

  return <>
    <svg className="pointer-events-none absolute inset-0 h-full w-full"
      viewBox={`0 0 ${size.width} ${size.height}`} preserveAspectRatio="xMidYMid meet"
      aria-label="Articulaciones de los dedos detectadas automáticamente">
      {hands.filter(h => h.score >= 0.7).map(hand => <g key={hand.side} stroke={hand.side === "Left" ? "#34d399" : "#38bdf8"}>
        {BONES.map((bone, i) => <polyline key={i} points={bone.map(index => `${hand.points[index].x * size.width},${hand.points[index].y * size.height}`).join(" ")} fill="none" strokeWidth={3} />)}
        {hand.points.map((point, i) => <circle key={i} cx={point.x * size.width} cy={point.y * size.height} r={[4, 8, 12, 16, 20].includes(i) ? 7 : 4} fill={[4, 8, 12, 16, 20].includes(i) ? "#fff" : "#111"} strokeWidth={2} />)}
      </g>)}
    </svg>
    <div className="pointer-events-none absolute bottom-10 left-2 right-2 z-20 space-y-1 rounded bg-black/85 p-2 text-xs text-white">
      <p role="status">{status}</p>
      <p>Blanco: puntas de dedos. Posiciones relativas a cada palma, sin centrar la flauta ni calibrar.</p>
    </div>
  </>
}
