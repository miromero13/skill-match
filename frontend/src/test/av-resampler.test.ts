import { describe, expect, it } from "vitest"
import { AUDIO_RATE, Decimator, resample } from "@/services/av-capture"

function tone(frequency: number, rate: number, seconds: number, amplitude = 0.5) {
  const out = new Float32Array(Math.round(rate * seconds))
  for (let index = 0; index < out.length; index++) out[index] = amplitude * Math.sin((2 * Math.PI * frequency * index) / rate)
  return out
}

/** Amplitude and residual RMS of the best sinusoid at `frequency` over the middle of the signal (edges skipped). */
function fit(samples: ReadonlyArray<number>, frequency: number) {
  const from = Math.floor(samples.length * 0.1)
  const to = Math.floor(samples.length * 0.9)
  let inPhase = 0
  let quadrature = 0
  for (let index = from; index < to; index++) {
    const angle = (2 * Math.PI * frequency * index) / AUDIO_RATE
    inPhase += samples[index] * Math.sin(angle)
    quadrature += samples[index] * Math.cos(angle)
  }
  const count = to - from
  const a = (2 * inPhase) / count
  const b = (2 * quadrature) / count
  let residual = 0
  for (let index = from; index < to; index++) {
    const angle = (2 * Math.PI * frequency * index) / AUDIO_RATE
    residual += (samples[index] - a * Math.sin(angle) - b * Math.cos(angle)) ** 2
  }
  return { amplitude: Math.hypot(a, b), residual: Math.sqrt(residual / count) }
}

describe("Decimator / resample to 16 kHz", () => {
  it.each([48_000, 44_100])("keeps a 1 kHz tone's frequency and amplitude at %i Hz", (rate) => {
    const out = resample(tone(1000, rate, 1), rate)
    const { amplitude, residual } = fit(out, 1000)
    expect(amplitude).toBeGreaterThan(0.48)
    expect(amplitude).toBeLessThan(0.52)
    expect(residual).toBeLessThan(0.01)
  })

  it.each([48_000, 44_100])("strongly attenuates a 10 kHz tone (would alias to 6 kHz) at %i Hz", (rate) => {
    const out = resample(tone(10_000, rate, 1), rate)
    const middle = out.slice(1600, 14_400)
    const peak = Math.max(...middle.map(Math.abs))
    expect(peak).toBeLessThan(0.005) // at least -40 dB below the 0.5 input
  })

  it.each([48_000, 44_100, 32_000, 16_000])("returns as many samples as the duration needs at %i Hz", (rate) => {
    const out = resample(tone(440, rate, 2.5), rate)
    expect(Math.abs(out.length - 2.5 * AUDIO_RATE)).toBeLessThanOrEqual(1)
  })

  it("gives the same result streaming in odd-sized chunks as in one call", () => {
    const input = tone(700, 44_100, 0.5)
    const whole = resample(input, 44_100)
    const decimator = new Decimator(44_100)
    const parts: number[] = []
    for (let at = 0; at < input.length; at += 1023) parts.push(...decimator.push(input.subarray(at, at + 1023)))
    parts.push(...decimator.flush())
    expect(parts).toHaveLength(whole.length)
    parts.forEach((value, index) => expect(value).toBeCloseTo(whole[index], 5))
  })

  it("clamps to [-1, 1], neutralises non-finite input and never emits NaN", () => {
    const loud = tone(500, 48_000, 0.2, 6)
    loud[100] = Number.NaN
    loud[200] = Number.POSITIVE_INFINITY
    const out = resample(loud, 48_000)
    expect(out.every((value) => Number.isFinite(value) && value >= -1 && value <= 1)).toBe(true)
    expect(Math.max(...out)).toBe(1)
  })

  it("passes 16 kHz through untouched and rejects an invalid input rate", () => {
    const input = tone(300, 16_000, 0.1)
    expect(resample(input, 16_000)).toEqual(Array.from(input).map((value) => Math.fround(value)))
    expect(() => new Decimator(0)).toThrow()
    expect(() => new Decimator(Number.NaN)).toThrow()
  })

  it("upsamples a lower rate to exactly the 16 kHz grid", () => {
    const out = resample(tone(500, 8_000, 1), 8_000)
    expect(Math.abs(out.length - AUDIO_RATE)).toBeLessThanOrEqual(1)
    expect(fit(out, 500).amplitude).toBeGreaterThan(0.48)
  })
})
