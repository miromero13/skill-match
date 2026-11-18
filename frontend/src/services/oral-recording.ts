export function pcmWave(samples: Float32Array): Uint8Array {
  if (!samples.length || samples.length > 16000 * 90 || samples.some(value => !Number.isFinite(value)))
    throw new Error("La respuesta de audio está vacía o excede el límite permitido.")
  const bytes = new Uint8Array(44 + samples.length * 2)
  const view = new DataView(bytes.buffer)
  const text = (offset: number, value: string) => { for (let index = 0; index < value.length; index++) bytes[offset + index] = value.charCodeAt(index) }
  text(0, "RIFF"); view.setUint32(4, bytes.length - 8, true); text(8, "WAVE"); text(12, "fmt ")
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true)
  view.setUint32(24, 16000, true); view.setUint32(28, 32000, true)
  view.setUint16(32, 2, true); view.setUint16(34, 16, true); text(36, "data")
  view.setUint32(40, samples.length * 2, true)
  samples.forEach((sample, index) => {
    const value = Math.max(-1, Math.min(1, sample))
    view.setInt16(44 + index * 2, Math.round(value * (value < 0 ? 32768 : 32767)), true)
  })
  return bytes
}

export interface OralRecording {
  stop: () => Promise<string>
  cancel: () => void
}

export async function startOralRecording(signal: AbortSignal, onFailure?: (message: string) => void): Promise<OralRecording> {
  signal.throwIfAborted()
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 }, video: false })
  if (signal.aborted) { stream.getTracks().forEach(track => track.stop()); signal.throwIfAborted() }
  let context: AudioContext | undefined
  let closingContext = false
  let cleanup = () => { stream.getTracks().forEach(track => track.stop()) }
  try {
    context = new AudioContext()
    await context.resume()
    signal.throwIfAborted()
    const source = context.createMediaStreamSource(stream)
    const processor = context.createScriptProcessor(4096, 1, 1)
    const chunks: Float32Array[] = []
    let samples = 0
    let stopped = false
    let error: Error | null = null
    let expectedClock: number | null = null
    const fail = (message: string) => {
      if (stopped) return
      error = new Error(message)
      cleanup()
      onFailure?.(message)
    }
    const cancelled = () => fail("La grabación fue cancelada.")
    const ended = () => fail("Se interrumpió el micrófono. La respuesta no se envió.")
    const watchdog = setTimeout(() => fail("La grabación alcanzó el límite de 90 segundos. Volvé a grabar dentro del tiempo disponible."), 90000)
    cleanup = () => {
      if (stopped) return
      stopped = true
      clearTimeout(watchdog)
      signal.removeEventListener("abort", cancelled)
      processor.onaudioprocess = null
      for (const track of stream.getAudioTracks()) {
        track.removeEventListener("ended", ended); track.removeEventListener("mute", ended)
      }
      source.disconnect(); processor.disconnect()
      stream.getTracks().forEach(track => track.stop())
      if (context && context.state !== "closed" && !closingContext) {
        closingContext = true
        void context.close().catch(() => { /* Devices and graph have already been released. */ })
      }
    }
    signal.addEventListener("abort", cancelled, { once: true })
    for (const track of stream.getAudioTracks()) {
      if (track.readyState !== "live") throw new Error("El micrófono no entrega una señal activa.")
      track.addEventListener("ended", ended); track.addEventListener("mute", ended)
    }
    processor.onaudioprocess = event => {
      if (stopped) return
      event.outputBuffer.getChannelData(0).fill(0)
      const input = event.inputBuffer.getChannelData(0)
      const rate = context!.sampleRate
      const duration = input.length / rate
      if (!Number.isFinite(event.playbackTime) || (expectedClock !== null && Math.abs(event.playbackTime - expectedClock) > Math.max(.02, duration * .75))) {
        fail("Se interrumpió el reloj del micrófono. La respuesta no se envió."); return
      }
      expectedClock = event.playbackTime + duration
      const count = Math.floor(input.length * 16000 / rate)
      const output = new Float32Array(count)
      for (let index = 0; index < count; index++) {
        const start = Math.floor(index * rate / 16000), end = Math.min(input.length, Math.floor((index + 1) * rate / 16000))
        let total = 0
        for (let offset = start; offset < end; offset++) total += input[offset]
        output[index] = total / Math.max(1, end - start)
      }
      if (output.some(value => !Number.isFinite(value)) || samples + count > 16000 * 90) {
        fail("La captura de audio excedió los límites permitidos."); return
      }
      chunks.push(output); samples += count
    }
    source.connect(processor); processor.connect(context.destination)
    if (signal.aborted) cancelled()
    return {
      cancel: cancelled,
      stop: async () => {
        if (error) throw error
        if (stopped) throw new Error("La grabación ya terminó.")
        cleanup()
        if (samples < 1600) throw new Error("No se capturó suficiente audio. Intentá responder nuevamente.")
        const joined = new Float32Array(samples)
        let offset = 0
        for (const chunk of chunks) { joined.set(chunk, offset); offset += chunk.length }
        const bytes = pcmWave(joined)
        let binary = ""
        for (let start = 0; start < bytes.length; start += 8192) binary += String.fromCharCode(...bytes.subarray(start, start + 8192))
        return btoa(binary)
      },
    }
  } catch (error) {
    cleanup()
    if (context && context.state !== "closed" && !closingContext) {
      closingContext = true
      await context.close()
    }
    throw error
  }
}
