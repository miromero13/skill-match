import { describe, expect, it } from "vitest"
import { encodeHandLandmarks, freshHandFrame, type DetectedHand } from "@/components/admin/flute/flute-hand-features"

const hand: DetectedHand = {
  side: "Left",
  score: 0.95,
  points: Array.from({ length: 21 }, (_, i) => ({
    x: 0.3 + (i % 5) * 0.05,
    y: 0.2 + Math.floor(i / 5) * 0.08,
    z: (i % 3) * 0.01,
  })),
}

describe("flute hand landmarks (palm basis)", () => {
  it("encodes 21 xyz points in fixed handedness slots, never a pixel grid", () => {
    const features = encodeHandLandmarks([hand], 1000, 1000)!
    expect(features).toHaveLength(128)
    expect(features[0]).toBe(1)
    expect(features.slice(64)).toEqual(Array(64).fill(0))
    expect(features.every(Number.isFinite)).toBe(true)
    expect(encodeHandLandmarks([{ ...hand, side: "Right" }], 1000, 1000)![64]).toBe(1)
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
    expect(encodeHandLandmarks([], 1000, 1000)).toEqual(Array(128).fill(0))
    expect(encodeHandLandmarks([hand], 0, 1000)).toBeNull()
    expect(encodeHandLandmarks([{ ...hand, score: 0.2 }], 1000, 1000)).toEqual(Array(128).fill(0))
    expect(encodeHandLandmarks([{ ...hand, points: [{ x: NaN, y: 0, z: 0 }] }], 1000, 1000)![0]).toBe(0)
  })

  it("does not reuse stale detections", () => {
    const frame = { timestamp: 100, features: [], hands: [] }
    expect(freshHandFrame(frame, 200)).toBe(frame)
    expect(freshHandFrame(frame, 600)).toBeNull()
    expect(freshHandFrame(null, 200)).toBeNull()
  })
})
