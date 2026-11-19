export const FLUTE_VISUAL_SCHEMA = "hand-landmarks-palm-v2" as const
export const FLUTE_VISUAL_DIM = 128
export interface Landmark { x: number; y: number; z: number }
export interface DetectedHand { side: "Left" | "Right"; score: number; points: Landmark[] }
export interface HandFrame {
  features: number[]
  hands: DetectedHand[]
  timestamp: number
}

const subtract = (a: Landmark, b: Landmark): Landmark => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z })
const dot = (a: Landmark, b: Landmark) => a.x * b.x + a.y * b.y + a.z * b.z
const multiply = (a: Landmark, scale: number): Landmark => ({ x: a.x * scale, y: a.y * scale, z: a.z * scale })
const length = (a: Landmark) => Math.hypot(a.x, a.y, a.z)

/** Two handedness slots: presence + 21 xyz points in each hand's own frame.
 * Origin: wrist. Axes: palm MCP joints (5, 9, 17). Scale: palm size.
 * No screen position, flute axis, target note, or user calibration is used. */
export function encodeHandLandmarks(
  hands: DetectedHand[], width: number, height: number
): number[] | null {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return null
  const features = Array<number>(FLUTE_VISUAL_DIM).fill(0)
  for (const [slot, side] of (["Left", "Right"] as const).entries()) {
    const hand = hands.filter(h => h.side === side && h.score >= 0.7)
      .sort((a, b) => b.score - a.score)[0]
    if (!hand || hand.points.length !== 21 || hand.points.some(p =>
      ![p.x, p.y, p.z].every(Number.isFinite) || p.x < 0 || p.x > 1 || p.y < 0 || p.y > 1)) continue
    // MediaPipe normalized z uses the same scale as image x.
    const points = hand.points.map(p => ({ x: p.x * width, y: p.y * height, z: p.z * width }))
    const across = subtract(points[5], points[17])
    const along = subtract(points[9], points[0])
    const palmWidth = length(across)
    const palmLength = length(along)
    if (palmWidth < 1 || palmLength < 1) continue
    const xAxis = multiply(across, 1 / palmWidth)
    const orthogonal = subtract(along, multiply(xAxis, dot(along, xAxis)))
    const orthogonalLength = length(orthogonal)
    if (orthogonalLength < palmLength * 0.1) continue // Degenerate/uncertain palm, not incorrect fingering.
    const yAxis = multiply(orthogonal, 1 / orthogonalLength)
    const zAxis = {
      x: xAxis.y * yAxis.z - xAxis.z * yAxis.y,
      y: xAxis.z * yAxis.x - xAxis.x * yAxis.z,
      z: xAxis.x * yAxis.y - xAxis.y * yAxis.x,
    }
    const scale = (palmWidth + palmLength) / 2
    const offset = slot * 64
    features[offset] = 1
    points.forEach((point, i) => {
      const relative = subtract(point, points[0])
      features[offset + 1 + i * 3] = dot(relative, xAxis) / scale
      features[offset + 2 + i * 3] = dot(relative, yAxis) / scale
      features[offset + 3 + i * 3] = dot(relative, zAxis) / scale
    })
  }
  return features
}

export function freshHandFrame(frame: HandFrame | null, now = performance.now()): HandFrame | null {
  return frame && now - frame.timestamp >= 0 && now - frame.timestamp < 500 ? frame : null
}
