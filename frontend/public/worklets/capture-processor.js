/**
 * AudioWorklet of the shared capture pipeline (src/services/av-capture.ts). It only forwards the raw microphone
 * channel to the page in blocks of 1024 samples at the context's own rate; the page converts them to 16 kHz.
 * It never writes to its output, so the microphone is not played back.
 */
class CaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.block = new Float32Array(1024)
    this.filled = 0
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0]
    if (!channel) return true
    let offset = 0
    while (offset < channel.length) {
      const take = Math.min(this.block.length - this.filled, channel.length - offset)
      this.block.set(channel.subarray(offset, offset + take), this.filled)
      this.filled += take
      offset += take
      if (this.filled === this.block.length) {
        this.port.postMessage(this.block, [this.block.buffer])
        this.block = new Float32Array(1024)
        this.filled = 0
      }
    }
    return true
  }
}

registerProcessor("skillmatch-capture", CaptureProcessor)
