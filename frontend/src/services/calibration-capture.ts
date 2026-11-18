export interface MicrophoneMonitor {
  samples: () => number[]
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
    return {
      samples: () => { analyser.getFloatTimeDomainData(samples); return Array.from(samples) },
      close: async () => { source.disconnect(); if (context.state !== "closed") await context.close() },
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

export async function captureCalibrationEvidence(
  video: HTMLVideoElement, microphone: MicrophoneMonitor, signal: AbortSignal,
): Promise<{ frames: string[]; audio_samples: number[] }> {
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
  let bestAudio: number[] = []
  let bestEnergy = -1
  // Nine frames over 2.8 seconds leave transport time within the five-second challenge.
  for (let index = 0; index < 9; index++) {
    signal.throwIfAborted()
    context.drawImage(video, 0, 0, canvas.width, canvas.height)
    frames.push(canvas.toDataURL("image/jpeg", 0.65))
    const audio = microphone.samples()
    const energy = audio.reduce((sum, value) => sum + value * value, 0)
    if (energy > bestEnergy) { bestEnergy = energy; bestAudio = audio }
    if (index < 8) await delay(350, signal)
  }
  return { frames, audio_samples: bestAudio }
}
