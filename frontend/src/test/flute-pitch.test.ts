import { describe, expect, it } from "vitest"
import {
  FLUTE_AUDIO_DIM,
  FLUTE_AUDIO_SCHEMA,
  FLUTE_NOTE_FREQUENCIES_HZ,
  FLUTE_PITCH_NOTE_ORDER,
  buildPitchFeatures,
  computePitchAgreement,
  estimatePitchYin,
  extractFluteAudioFeatures,
  gateFluteFrames,
  nearestFluteNote,
  pitchAgreementRejection,
  type FluteNoteName,
} from "@/components/admin/flute/flute-note-specs"

const cents = (a: number, b: number) => 1200 * Math.log2(a / b)

function fluteLike(hz: number, sampleRate: number, length = 2048): Float32Array {
  const out = new Float32Array(length)
  for (let i = 0; i < length; i++) {
    const t = i / sampleRate
    out[i] =
      0.3 * Math.sin(2 * Math.PI * hz * t) +
      0.15 * Math.sin(2 * Math.PI * 2 * hz * t + 0.4) +
      0.08 * Math.sin(2 * Math.PI * 3 * hz * t + 1.1)
  }
  return out
}

function seededNoise(length: number, amplitude: number): Float32Array {
  let seed = 12345
  const out = new Float32Array(length)
  for (let i = 0; i < length; i++) {
    seed = (seed * 1103515245 + 12345) % 2147483648
    out[i] = ((seed / 2147483648) * 2 - 1) * amplitude
  }
  return out
}

function mockAnalyser(waveform: Float32Array): AnalyserNode {
  return {
    fftSize: waveform.length,
    frequencyBinCount: waveform.length / 2,
    getFloatFrequencyData: (arr: Float32Array) => {
      arr.fill(-90)
      arr[25] = -15
      arr[50] = -25
    },
    getFloatTimeDomainData: (arr: Float32Array) => {
      arr.set(waveform.subarray(0, arr.length))
    },
  } as unknown as AnalyserNode
}

describe("flute note frequency table", () => {
  it("uses equal temperament A4=440 in the backend note order", () => {
    expect(FLUTE_PITCH_NOTE_ORDER).toEqual(["DO", "RE", "MI", "FA", "FA#", "SOL", "LA", "SI", "DO6", "RE6", "MI6"])
    expect(FLUTE_NOTE_FREQUENCIES_HZ.LA).toBe(880)
    expect(FLUTE_NOTE_FREQUENCIES_HZ.DO).toBeCloseTo(523.2511, 3)
    expect(FLUTE_NOTE_FREQUENCIES_HZ.MI6).toBeCloseTo(1318.51, 2)
    expect(FLUTE_AUDIO_SCHEMA).toBe("flute-audio-pitch-v1")
    expect(FLUTE_AUDIO_DIM).toBe(62)
  })

  it("maps a frequency to the nearest note with signed cents", () => {
    expect(nearestFluteNote(880)).toEqual({ note: "LA", centsOff: 0 })
    const sharpSol = nearestFluteNote(783.9909 * 2 ** (20 / 1200))
    expect(sharpSol.note).toBe("SOL")
    expect(sharpSol.centsOff).toBeCloseTo(20, 3)
    expect(nearestFluteNote(1174.659 * 2 ** (-30 / 1200)).note).toBe("RE6")
  })
})

describe("YIN pitch estimation", () => {
  for (const sampleRate of [44100, 48000]) {
    for (const note of FLUTE_PITCH_NOTE_ORDER) {
      it(`detects ${note} within ±10 cents at ${sampleRate} Hz`, () => {
        const target = FLUTE_NOTE_FREQUENCIES_HZ[note]
        const { hz, clarity } = estimatePitchYin(fluteLike(target, sampleRate), sampleRate)
        expect(hz).not.toBeNull()
        expect(Math.abs(cents(hz!, target))).toBeLessThanOrEqual(10)
        expect(clarity).toBeGreaterThanOrEqual(0.8)
        expect(nearestFluteNote(hz!).note).toBe(note)
      })
    }
  }

  it("distinguishes SOL from LA and DO6 from RE6", () => {
    const pairs: Array<[FluteNoteName, FluteNoteName]> = [["SOL", "LA"], ["DO6", "RE6"]]
    for (const [a, b] of pairs) {
      const hzA = estimatePitchYin(fluteLike(FLUTE_NOTE_FREQUENCIES_HZ[a], 48000), 48000).hz!
      const hzB = estimatePitchYin(fluteLike(FLUTE_NOTE_FREQUENCIES_HZ[b], 48000), 48000).hz!
      expect(nearestFluteNote(hzA).note).toBe(a)
      expect(nearestFluteNote(hzB).note).toBe(b)
    }
  })

  it("returns null for white noise and silence", () => {
    const noise = estimatePitchYin(seededNoise(2048, 0.3), 48000)
    expect(noise.hz).toBeNull()
    expect(noise.clarity).toBeLessThan(0.8)
    const silence = estimatePitchYin(new Float32Array(2048), 44100)
    expect(silence.hz).toBeNull()
    expect(silence.clarity).toBeGreaterThanOrEqual(0)
    expect(silence.clarity).toBeLessThanOrEqual(1)
  })

  it("treats a quiet but periodic tone as unvoiced (RMS < 0.012)", () => {
    const quiet = fluteLike(880, 48000).map((v) => v * 0.02)
    expect(estimatePitchYin(quiet, 48000).hz).toBeNull()
  })
})

describe("pitch feature block", () => {
  it("encodes voiced, clarity, octaves above C5 and note affinities", () => {
    const vec = buildPitchFeatures(880, 0.95)
    expect(vec).toHaveLength(14)
    expect(vec[0]).toBe(1)
    expect(vec[1]).toBeCloseTo(0.95, 6)
    expect(vec[2]).toBeCloseTo(Math.log2(880 / 523.2511), 6)
    const laIdx = FLUTE_PITCH_NOTE_ORDER.indexOf("LA")
    expect(vec[3 + laIdx]).toBeCloseTo(1, 6)
    const siIdx = FLUTE_PITCH_NOTE_ORDER.indexOf("SI")
    expect(vec[3 + siIdx]).toBeCloseTo(Math.exp(-0.5 * (cents(880, 987.7666) / 35) ** 2), 6)
  })

  it("zeros pitch dims when unvoiced but keeps clarity", () => {
    expect(buildPitchFeatures(null, 0.4)).toEqual([0, 0.4, ...Array(12).fill(0)])
  })
})

describe("extractFluteAudioFeatures (flute-audio-pitch-v1)", () => {
  it("returns 62 finite values with the pitch block appended", () => {
    const vec = extractFluteAudioFeatures(mockAnalyser(fluteLike(783.9909, 48000)), 48000)
    expect(vec).toHaveLength(62)
    expect(vec.every(Number.isFinite)).toBe(true)
    expect(vec[48]).toBe(1)
    expect(vec[49]).toBeGreaterThanOrEqual(0.8)
    expect(Math.abs(1200 * vec[50] - cents(783.9909, 523.2511))).toBeLessThanOrEqual(10)
    expect(vec[51 + FLUTE_PITCH_NOTE_ORDER.indexOf("SOL")]).toBeGreaterThan(0.9)
  })

  it("marks silence as unvoiced with zeroed pitch dims", () => {
    const vec = extractFluteAudioFeatures(mockAnalyser(new Float32Array(2048)), 44100)
    expect(vec).toHaveLength(62)
    expect(vec.every(Number.isFinite)).toBe(true)
    expect(vec[48]).toBe(0)
    expect(vec.slice(50)).toEqual(Array(12).fill(0))
  })
})

function audioFrame(hz: number | null): number[] {
  return [...Array(48).fill(0.1), ...buildPitchFeatures(hz, hz === null ? 0.2 : 0.95)]
}

describe("silence gating and pitch agreement", () => {
  it("drops unvoiced frames only for flute takes and caps at 120 frames", () => {
    const frames = [audioFrame(880), audioFrame(null), audioFrame(880)].map((audio_features) => ({ audio_features }))
    expect(gateFluteFrames(frames, "flauta")).toHaveLength(2)
    expect(gateFluteFrames(frames, "voz")).toHaveLength(3)
    expect(gateFluteFrames(frames, "ruido")).toHaveLength(3)
    const many = Array.from({ length: 200 }, () => ({ audio_features: audioFrame(880) }))
    expect(gateFluteFrames(many, "flauta")).toHaveLength(120)
    expect(gateFluteFrames(many, "voz")).toHaveLength(120)
  })

  it("measures the fraction of voiced frames on the labeled note (±60 cents)", () => {
    const frames = [audioFrame(784), audioFrame(784), audioFrame(880), audioFrame(null)]
    expect(computePitchAgreement(frames, "SOL")).toEqual({ voicedFrames: 3, matchingFrames: 2, agreement: 2 / 3 })
    expect(computePitchAgreement([audioFrame(null)], "SOL")).toEqual({ voicedFrames: 0, matchingFrames: 0, agreement: 0 })
  })

  it("rejects takes below 30% agreement or with fewer than 3 voiced frames", () => {
    expect(pitchAgreementRejection({ voicedFrames: 8, matchingFrames: 1, agreement: 0.125 }, "SOL"))
      .toBe("La altura detectada no corresponde a la nota SOL (coincidencia 13%). Repetí la toma.")
    expect(pitchAgreementRejection({ voicedFrames: 2, matchingFrames: 2, agreement: 1 }, "LA"))
      .toBe("No se detectó una altura estable de flauta para la nota LA (2 fotogramas con sonido). Repetí la toma.")
    expect(pitchAgreementRejection({ voicedFrames: 10, matchingFrames: 3, agreement: 0.3 }, "LA")).toBeNull()
  })
})
