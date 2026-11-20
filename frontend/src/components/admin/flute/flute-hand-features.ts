export const FLUTE_VISUAL_SCHEMA = "hand-landmarks-palm-v5" as const
export const FLUTE_HAND_SLOT_DIM = 25
export const FLUTE_VISUAL_DIM = FLUTE_HAND_SLOT_DIM * 2 // 50
export const LEFT_HAND_PRESENCE_IDX = 0
export const RIGHT_HAND_PRESENCE_IDX = FLUTE_HAND_SLOT_DIM

export interface Landmark { x: number; y: number; z: number }
export interface DetectedHand { side: "Left" | "Right"; score: number; points: Landmark[] }
export interface HandFrame {
  features: number[]
  hands: DetectedHand[]
  timestamp: number
}

// Each finger: [base(MCP/CMC), middle(PIP/MCP), joint(DIP/IP), tip]
const FINGER_CHAINS: ReadonlyArray<readonly [number, number, number, number]> = [
  [1, 2, 3, 4],     // Thumb
  [5, 6, 7, 8],     // Index
  [9, 10, 11, 12],  // Middle
  [13, 14, 15, 16], // Ring
  [17, 18, 19, 20], // Pinky
]

const ADJACENT_TIP_PAIRS: ReadonlyArray<readonly [number, number]> = [
  [4, 8],   // Thumb - Index
  [8, 12],  // Index - Middle
  [12, 16], // Middle - Ring
  [16, 20], // Ring - Pinky
]

const subtract = (a: Landmark, b: Landmark): Landmark => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z })
const dot = (a: Landmark, b: Landmark) => a.x * b.x + a.y * b.y + a.z * b.z
const multiply = (a: Landmark, scale: number): Landmark => ({ x: a.x * scale, y: a.y * scale, z: a.z * scale })
const length = (a: Landmark) => Math.hypot(a.x, a.y, a.z)

function fingerCurlCosine(a: Landmark, b: Landmark, c: Landmark): number {
  const v1 = subtract(b, a)
  const v2 = subtract(c, b)
  const denom = length(v1) * length(v2)
  if (denom < 1e-6) return 0
  return Math.max(-1, Math.min(1, dot(v1, v2) / denom))
}

export function countDetectedHands(visualFeatures: readonly number[]): number {
  const left = visualFeatures[LEFT_HAND_PRESENCE_IDX] === 1 ? 1 : 0
  const right = visualFeatures[RIGHT_HAND_PRESENCE_IDX] === 1 ? 1 : 0
  return left + right
}

/** Two handedness slots (Left, Right), 25 rotation/position-invariant finger features per hand (50 total):
 * - [0]: presence flag (0 or 1)
 * - [1..5]: 5 finger flexion cosines (straight ≈ 1, curled/covering hole < 0.5)
 * - [6..10]: 5 normalized fingertip-to-palm-center distances
 * - [11..15]: 5 normalized fingertip-to-MCP distances (finger extension)
 * - [16..19]: 4 normalized adjacent fingertip distances (finger spread)
 * - [20..24]: 5 normalized fingertip palm-plane heights (lifted vs pressed) */
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
    if (orthogonalLength < palmLength * 0.1) continue

    const yAxis = multiply(orthogonal, 1 / orthogonalLength)
    const zAxis: Landmark = {
      x: xAxis.y * yAxis.z - xAxis.z * yAxis.y,
      y: xAxis.z * yAxis.x - xAxis.x * yAxis.z,
      z: xAxis.x * yAxis.y - xAxis.y * yAxis.x,
    }
    const palmCenter: Landmark = {
      x: (points[0].x + points[5].x + points[9].x + points[17].x) / 4,
      y: (points[0].y + points[5].y + points[9].y + points[17].y) / 4,
      z: (points[0].z + points[5].z + points[9].z + points[17].z) / 4,
    }
    const scale = (palmWidth + palmLength) / 2
    const offset = slot * FLUTE_HAND_SLOT_DIM
    features[offset] = 1

    FINGER_CHAINS.forEach(([base, mid, joint, tip], idx) => {
      const curl1 = fingerCurlCosine(points[base], points[mid], points[joint])
      const curl2 = fingerCurlCosine(points[mid], points[joint], points[tip])
      features[offset + 1 + idx] = (curl1 + curl2) / 2
      features[offset + 6 + idx] = length(subtract(points[tip], palmCenter)) / scale
      features[offset + 11 + idx] = length(subtract(points[tip], points[base])) / scale
      features[offset + 20 + idx] = dot(subtract(points[tip], palmCenter), zAxis) / scale
    })

    ADJACENT_TIP_PAIRS.forEach(([a, b], idx) => {
      features[offset + 16 + idx] = length(subtract(points[a], points[b])) / scale
    })
  }
  return features
}

export function freshHandFrame(frame: HandFrame | null, now = performance.now()): HandFrame | null {
  return frame && now - frame.timestamp >= 0 && now - frame.timestamp < 500 ? frame : null
}
