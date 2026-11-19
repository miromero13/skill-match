export interface MicrophoneMonitor {
  samples: () => number[]
  record?: (milliseconds: number, signal: AbortSignal, onClock?: (seconds: number) => void) => Promise<number[]>
  close: () => Promise<void>
}

export async function createMicrophoneMonitor(stream: MediaStream): Promise<MicrophoneMonitor> {
  const context = new AudioContext()
  try {
    await context.resume()
    const source = context.createMediaStreamSource(stream)
    const analyser = context.createAnalyser()
    analyser.fftSize = 1024
    source.connect(analyser)
    const samples = new Float32Array(analyser.fftSize)
    let cancelRecording: (() => void) | null = null
    return {
      samples: () => { analyser.getFloatTimeDomainData(samples); return Array.from(samples) },
      record: async (milliseconds, signal, onClock) => {
        signal.throwIfAborted()
        if (cancelRecording || milliseconds < 1000 || milliseconds > 10000) throw new Error("No se pudo iniciar la ventana de audio.")
        // ScriptProcessor is used for compatibility; output is always silent.
        const processor = context.createScriptProcessor(1024, 1, 1)
        return new Promise<number[]>((resolve, reject) => {
          const chunks: Float32Array[] = []
          let count = 0
          let timer: ReturnType<typeof setTimeout> | undefined
          let finished = false
          let expectedClock: number | null = null
          const cleanup = () => {
            clearTimeout(timer)
            signal.removeEventListener("abort", cancel)
            processor.onaudioprocess = null
            try { source.disconnect(processor) } catch { /* It may already be disconnected on exit. */ }
            processor.disconnect()
            cancelRecording = null
          }
          const cancel = () => {
            if (finished) return
            finished = true; cleanup()
            reject(new DOMException("Capture cancelled", "AbortError"))
          }
          cancelRecording = cancel
          processor.onaudioprocess = event => {
            event.outputBuffer.getChannelData(0).fill(0)
            if (finished || signal.aborted) return
            const input = event.inputBuffer.getChannelData(0)
            const blockDuration = input.length / context.sampleRate
            try {
              if (!Number.isFinite(event.playbackTime) || (expectedClock !== null
                && Math.abs(event.playbackTime - expectedClock) > Math.max(.01, blockDuration * .75))) {
                throw new Error("Se interrumpió el reloj de audio. Mantené la página visible y repetí la comprobación.")
              }
              expectedClock = event.playbackTime + blockDuration
              if (count + input.length <= context.sampleRate * (milliseconds / 1000 + .1)) {
                chunks.push(new Float32Array(input)); count += input.length
                onClock?.(count / context.sampleRate)
              }
            } catch (error) {
              finished = true; cleanup(); reject(error)
            }
          }
          try {
            source.connect(processor)
            processor.connect(context.destination)
          } catch (error) {
            finished = true; cleanup(); reject(error); return
          }
          signal.addEventListener("abort", cancel, { once: true })
          timer = setTimeout(() => {
            if (finished) return
            finished = true; cleanup()
            const raw = new Float32Array(count)
            let offset = 0
            for (const chunk of chunks) { raw.set(chunk, offset); offset += chunk.length }
            const ratio = context.sampleRate / 16000
            const output = Array.from({ length: Math.floor(count / ratio) }, (_, index) => {
              const start = Math.floor(index * ratio), end = Math.min(count, Math.floor((index + 1) * ratio))
              let total = 0
              for (let sample = start; sample < end; sample++) total += raw[sample]
              return Math.max(-1, Math.min(1, total / Math.max(1, end - start)))
            })
            resolve(output)
          }, milliseconds)
          if (signal.aborted) cancel()
        })
      },
      close: async () => { cancelRecording?.(); source.disconnect(); if (context.state !== "closed") await context.close() },
    }
  } catch (error) {
    if (context.state !== "closed") await context.close()
    throw error
  }
}

function delay(milliseconds: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException("Capture cancelled", "AbortError")); return }
    const cancel = () => { clearTimeout(timer); reject(new DOMException("Capture cancelled", "AbortError")) }
    const timer = setTimeout(() => { signal.removeEventListener("abort", cancel); resolve() }, milliseconds)
    signal.addEventListener("abort", cancel, { once: true })
  })
}

export type CalibrationCapturePhase = "CENTER" | "TURN" | "RETURN" | "AMBIENT" | "SPEAK" | "PAUSE"

export async function captureCalibrationEvidence(
  video: HTMLVideoElement, microphone: MicrophoneMonitor, signal: AbortSignal,
  onPhase?: (phase: CalibrationCapturePhase) => void,
): Promise<{ frames: string[]; audio_samples: number[]; ambient_audio_samples: number[]; spoken_frames: { time_ms: number; image: string }[] }> {
  if (!video.videoWidth || !video.videoHeight) throw new Error("Esperá a que la cámara muestre imagen antes de capturar.")
  const canvas = document.createElement("canvas")
  canvas.width = Math.min(640, video.videoWidth)
  canvas.height = Math.round(video.videoHeight * canvas.width / video.videoWidth)
  if (canvas.width < 320 || canvas.height < 240 || canvas.height > 960) {
    throw new Error("La cámara no entrega la resolución mínima de 320×240 para la calibración.")
  }
  const context = canvas.getContext("2d")
  if (!context) throw new Error("No se pudo preparar la captura de cámara.")
  const frames: string[] = []
  // Keep the original evidence window and notify before each upcoming group of frames.
  // CSS mirrors only the preview; these frames retain the camera's original orientation.
  signal.throwIfAborted()
  onPhase?.("CENTER")
  for (let index = 0; index < 12; index++) {
    signal.throwIfAborted()
    context.drawImage(video, 0, 0, canvas.width, canvas.height)
    frames.push(canvas.toDataURL("image/jpeg", 0.65))
    if (index === 3) onPhase?.("TURN")
    if (index === 7) onPhase?.("RETURN")
    if (index < 11) await delay(1000, signal)
  }
  signal.throwIfAborted()
  if (!microphone.record) throw new Error("El navegador no pudo preparar la grabación de voz. Volvé a habilitar el micrófono.")
  onPhase?.("AMBIENT")
  const ambient_audio_samples = await microphone.record(3000, signal)
  signal.throwIfAborted()
  onPhase?.("SPEAK")
  const spoken_frames: { time_ms: number; image: string }[] = []
  let lastFrame = 0
  let pausing = false
  const audio_samples = await microphone.record(8000, signal, elapsed => {
    signal.throwIfAborted()
    if (elapsed - lastFrame >= .095) {
      if (spoken_frames.length >= 100) throw new Error("La captura de voz excedió el límite de imágenes. Repetí la comprobación.")
      context.drawImage(video, 0, 0, canvas.width, canvas.height)
      const image = canvas.toDataURL("image/jpeg", .55)
      if (image.length > 80000) throw new Error("La imagen de voz es demasiado grande. Usá una cámara de menor resolución y repetí la comprobación.")
      spoken_frames.push({ time_ms: Math.round(elapsed * 1000), image })
      lastFrame = elapsed
    }
    if (elapsed >= 4 && !pausing) { pausing = true; onPhase?.("PAUSE") }
  })
  signal.throwIfAborted()
  if (spoken_frames.length < 20) throw new Error("No se obtuvo video sincronizado suficiente. Mantené la página visible y repetí la comprobación.")
  return { frames, audio_samples, ambient_audio_samples, spoken_frames }
}
