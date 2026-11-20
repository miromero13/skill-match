import { describe, expect, it } from "vitest"
import {
  FLUTE_VISUAL_DIM,
  FLUTE_VISUAL_SCHEMA,
  LEFT_HAND_PRESENCE_IDX,
  RIGHT_HAND_PRESENCE_IDX,
  encodeHandLandmarks,
  freshHandFrame,
  type DetectedHand,
} from "@/components/admin/flute/flute-hand-features"
import {
  FLUTE_AUDIO_DIM,
  extractFluteAudioFeatures,
} from "@/components/admin/flute/flute-note-specs"

const hand: DetectedHand = {
  side: "Left",
  score: 0.95,
  points: Array.from({ length: 21 }, (_, i) => ({
    x: 0.3 + (i % 5) * 0.05,
    y: 0.2 + Math.floor(i / 5) * 0.08,
    z: (i % 3) * 0.01,
  })),
}

describe("flute hand landmarks (palm basis + finger flexion)", () => {
  it("uses the v5 schema (user-handedness slots, same 50-dim layout)", () => {
    expect(FLUTE_VISUAL_SCHEMA).toBe("hand-landmarks-palm-v5")
    expect(FLUTE_VISUAL_DIM).toBe(50)
  })

  it("encodes 21 xyz points + 10 finger flexion/distance features in fixed handedness slots", () => {
    const features = encodeHandLandmarks([hand], 1000, 1000)!
    expect(features).toHaveLength(FLUTE_VISUAL_DIM)
    expect(features[LEFT_HAND_PRESENCE_IDX]).toBe(1)
    expect(features.slice(RIGHT_HAND_PRESENCE_IDX)).toEqual(Array(RIGHT_HAND_PRESENCE_IDX).fill(0))
    expect(features.every(Number.isFinite)).toBe(true)
    expect(encodeHandLandmarks([{ ...hand, side: "Right" }], 1000, 1000)![RIGHT_HAND_PRESENCE_IDX]).toBe(1)
  })

  it("is invariant to hand translation across the screen", () => {
    const moved = {
      ...hand,
      points: hand.points.map(p => ({ x: p.x + 0.15, y: p.y + 0.1, z: p.z })),
    }
    const expected = encodeHandLandmarks([hand], 1000, 1000)!
    const actual = encodeHandLandmarks([moved], 1000, 1000)!
    actual.forEach((value, i) => expect(value).toBeCloseTo(expected[i], 4))
  })

  it("changes when fingers change and excludes low confidence or invalid landmarks", () => {
    const bent = { ...hand, points: hand.points.map((p, i) => i === 8 ? { ...p, x: 0.6 } : p) }
    expect(encodeHandLandmarks([bent], 1000, 1000)).not.toEqual(encodeHandLandmarks([hand], 1000, 1000))
    expect(encodeHandLandmarks([], 1000, 1000)).toEqual(Array(FLUTE_VISUAL_DIM).fill(0))
    expect(encodeHandLandmarks([hand], 0, 1000)).toBeNull()
    expect(encodeHandLandmarks([{ ...hand, score: 0.2 }], 1000, 1000)).toEqual(Array(FLUTE_VISUAL_DIM).fill(0))
    expect(encodeHandLandmarks([{ ...hand, points: [{ x: NaN, y: 0, z: 0 }] }], 1000, 1000)![0]).toBe(0)
  })

  it("does not reuse stale detections", () => {
    const frame = { timestamp: 100, features: [], hands: [] }
    expect(freshHandFrame(frame, 200)).toBe(frame)
    expect(freshHandFrame(frame, 600)).toBeNull()
    expect(freshHandFrame(null, 200)).toBeNull()
  })
})

describe("flute audio extractor (timbre + pitch)", () => {
  it("extracts 62 finite log-Mel + MFCC + timbre + pitch features from an AnalyserNode", () => {
    const mockAnalyser = {
      fftSize: 2048,
      frequencyBinCount: 1024,
      getFloatFrequencyData: (arr: Float32Array) => {
        arr.fill(-90)
        // Simulate flute timbre harmonics without measuring Hz
        arr[40] = -15
        arr[80] = -25
        arr[120] = -35
      },
      getFloatTimeDomainData: (arr: Float32Array) => {
        for (let i = 0; i < arr.length; i++) arr[i] = Math.sin(i * 0.1) * 0.2
      },
    } as unknown as AnalyserNode

    const vec = extractFluteAudioFeatures(mockAnalyser, 44100)
    expect(vec).toHaveLength(FLUTE_AUDIO_DIM)
    expect(vec.every(Number.isFinite)).toBe(true)
    expect(FLUTE_AUDIO_DIM).toBe(62)
    expect(vec[45]).toBeGreaterThan(0.05) // RMS > 0
    expect(vec[48]).toBe(1) // sin(0.1 i) at 44.1 kHz ≈ 702 Hz → voiced
  })
})
