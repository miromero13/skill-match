import { useCallback, useEffect, useRef, useState } from "react"

export const FOOTBALL_CAPTURE_CONSTRAINTS: MediaStreamConstraints = {
  audio: {
    echoCancellation: false,
    noiseSuppression: false,
    autoGainControl: false,
    channelCount: 1,
    sampleRate: 48000,
  },
  video: {
    width: 1280,
    height: 720,
    frameRate: { ideal: 30 },
  },
}

export interface UseMediaCaptureOptions {
  chunkDurationMs?: number
  onChunkAvailable?: (chunkIndex: number, blob: Blob) => void
}

export function useMediaCapture(options: UseMediaCaptureOptions = {}) {
  const { chunkDurationMs = 5000, onChunkAvailable } = options
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [isRecording, setIsRecording] = useState(false)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunkCounterRef = useRef<number>(0)
  const timerRef = useRef<number | null>(null)
  const onChunkRef = useRef(onChunkAvailable)

  useEffect(() => {
    onChunkRef.current = onChunkAvailable
  }, [onChunkAvailable])

  const requestPermissionsAndStream = useCallback(async () => {
    setError(null)
    if (
      typeof navigator === "undefined" ||
      !navigator.mediaDevices?.getUserMedia
    ) {
      const msg =
        "El navegador o dispositivo móvil no soporta captura multimedia (getUserMedia)."
      setError(msg)
      throw new Error(msg)
    }
    const mediaStream = await navigator.mediaDevices.getUserMedia(
      FOOTBALL_CAPTURE_CONSTRAINTS
    )
    setStream(mediaStream)
    return mediaStream
  }, [])

  const startRecording = useCallback(async () => {
    setError(null)
    const activeStream = stream ?? (await requestPermissionsAndStream())
    chunkCounterRef.current = 0
    setElapsedSeconds(0)

    const preferredMime =
      typeof MediaRecorder !== "undefined" &&
      MediaRecorder.isTypeSupported("video/mp4")
        ? "video/mp4"
        : "video/webm"

    const recorder = new MediaRecorder(activeStream, { mimeType: preferredMime })
    recorderRef.current = recorder

    recorder.ondataavailable = (event: BlobEvent) => {
      if (event.data && event.data.size > 0) {
        const idx = chunkCounterRef.current
        chunkCounterRef.current += 1
        onChunkRef.current?.(idx, event.data)
      }
    }

    recorder.start(chunkDurationMs)
    setIsRecording(true)

    timerRef.current = window.setInterval(() => {
      setElapsedSeconds((prev) => prev + 1)
    }, 1000)
  }, [chunkDurationMs, requestPermissionsAndStream, stream])

  const stopRecording = useCallback(() => {
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop()
    }
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
    setIsRecording(false)
  }, [])

  const releaseStream = useCallback(() => {
    stopRecording()
    if (stream) {
      stream.getTracks().forEach((t) => t.stop())
      setStream(null)
    }
  }, [stopRecording, stream])

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) {
        window.clearInterval(timerRef.current)
      }
    }
  }, [])

  return {
    stream,
    isRecording,
    elapsedSeconds,
    error,
    requestPermissionsAndStream,
    startRecording,
    stopRecording,
    releaseStream,
  }
}
