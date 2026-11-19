import { describe, expect, it } from "vitest"
import {
  AwayTracker,
  DEFAULT_GAZE_ZONE,
  classifyReading,
  headPose,
  measureGaze,
  mouthOpenScore,
  mouthSamplesForWindow,
  readingFromResult,
  samplesForWindow,
  type GazeReading,
  type GazeZone,
  type Point,
  type TimedReading,
} from "@/services/gaze-tracking"

/*
 * Same synthetic landmarks and expected numbers as backend/tests/gaze_fixtures.py + test_gaze_measurement.py:
 * the browser and the server must compute the same gaze features from the same landmarks.
 */
const EYE_WIDTH = 0.06
const CENTERS: Array<[number, number]> = [
  [0.43, 0.4],
  [0.57, 0.4],
]
const EYES = [
  [33, 133, 159, 145, 468],
  [362, 263, 386, 374, 473],
]

function eyePoints(irisDx = 0, irisDy = 0, opening = 0.02): Point[] {
  const points: Point[] = Array.from({ length: 478 }, () => ({ x: 0.5, y: 0.5, z: 0 }))
  EYES.forEach(([a, b, upper, lower, iris], index) => {
    const [cx, cy] = CENTERS[index]
    points[a] = { x: cx - EYE_WIDTH / 2, y: cy, z: 0 }
    points[b] = { x: cx + EYE_WIDTH / 2, y: cy, z: 0 }
    points[upper] = { x: cx, y: cy - opening / 2, z: 0 }
    points[lower] = { x: cx, y: cy + opening / 2, z: 0 }
    points[iris] = { x: cx + irisDx, y: cy + irisDy, z: 0 }
  })
  return points
}

function frontalFace(points: Point[]): Point[] {
  const out = points.map((point) => ({ ...point }))
  Object.entries({ 10: [0.5, 0.2], 152: [0.5, 0.8], 1: [0.5, 0.5], 78: [0.43, 0.65], 308: [0.57, 0.65] }).forEach(
    ([index, [x, y]]) => {
      out[Number(index)] = { x, y, z: 0 }
    },
  )
  return out
}

const GEOMETRY_CASES: Record<string, [number, number, number, number]> = {
  center: [0, 0, 0, 0],
  eyes_right: [0.012, 0, 0.8, 0],
  eyes_left: [-0.012, 0, -0.8, 0],
  eyes_down: [0, 0.006, 0, 0.9],
  eyes_up: [0, -0.006, 0, -0.9],
}

describe("gaze features mirror the backend", () => {
  for (const [name, [dx, dy, expectedH, expectedV]] of Object.entries(GEOMETRY_CASES)) {
    it(`measures ${name} from the iris geometry`, () => {
      const gaze = measureGaze(eyePoints(dx, dy), {})
      expect(gaze.gazeH).toBeCloseTo(expectedH, 6)
      expect(gaze.gazeV).toBeCloseTo(expectedV, 6)
      expect(gaze.blink).toBe(false)
    })
  }

  it("blends the eyeLook blendshapes with the geometry (ARKit semantics)", () => {
    expect(measureGaze(eyePoints(), { eyeLookOutLeft: 0.8, eyeLookInRight: 0.8 }).gazeH).toBeCloseTo(0.4, 6)
    expect(measureGaze(eyePoints(), { eyeLookInLeft: 0.8, eyeLookOutRight: 0.8 }).gazeH).toBeCloseTo(-0.4, 6)
    expect(measureGaze(eyePoints(), { eyeLookDownLeft: 0.6, eyeLookDownRight: 0.6 }).gazeV).toBeCloseTo(0.3, 6)
    expect(measureGaze(eyePoints(), { eyeLookUpLeft: 0.6, eyeLookUpRight: 0.6 }).gazeV).toBeCloseTo(-0.3, 6)
  })

  it("detects blinks from blendshapes and from closed lids", () => {
    expect(measureGaze(eyePoints(), { eyeBlinkLeft: 0.9, eyeBlinkRight: 0.8 }).blink).toBe(true)
    expect(measureGaze(eyePoints(), { eyeBlinkLeft: 0.2, eyeBlinkRight: 0.3 }).blink).toBe(false)
    expect(measureGaze(eyePoints(0, 0, 0.0024), {}).blink).toBe(true)
  })

  it("gives no gaze, never a clean center, for degenerate eyes or a mesh without irises", () => {
    const flat = Array.from({ length: 478 }, () => ({ x: 0.5, y: 0.5, z: 0 }))
    expect(measureGaze(flat, {})).toEqual({ gazeH: null, gazeV: null, blink: false })
    expect(measureGaze(flat.slice(0, 10), {}).gazeH).toBeNull()
  })

  it("computes head pitch/yaw as 55 % matrix + 45 % landmarks (column-major matrix)", () => {
    const face = frontalFace(eyePoints())
    const identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    expect(headPose(face, identity).pitch).toBeCloseTo(0, 6)
    expect(headPose(face, null).yaw).toBeCloseTo(0, 6)
    const c = Math.cos(Math.PI / 3)
    const s = Math.sin(Math.PI / 3)
    // Rotation about x of +60 degrees (head down), flattened column by column.
    const down = [1, 0, 0, 0, 0, c, s, 0, 0, -s, c, 0, 0, 0, 0, 1]
    expect(headPose(face, down).pitch).toBeCloseTo(33, 6)
    const up = [1, 0, 0, 0, 0, c, -s, 0, 0, s, c, 0, 0, 0, 0, 1]
    expect(headPose(face, up).pitch).toBeCloseTo(-33, 6)
    // Rotation about y of +60 degrees (toward the image right).
    const right = [c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1]
    expect(headPose(face, right).yaw).toBeCloseTo(33, 6)
  })
})

const ZONE: GazeZone = {
  pitch_min: -9,
  pitch_max: 13,
  yaw_min: -13,
  yaw_max: 13,
  gaze_h_min: -0.65,
  gaze_h_max: 0.65,
  gaze_v_min: -0.45,
  gaze_v_max: 0.55,
}
const reading = (extra: Partial<GazeReading> = {}): GazeReading => ({
  faceCount: 1,
  headPitch: 0,
  headYaw: 0,
  gazeH: 0,
  gazeV: 0,
  blink: false,
  ...extra,
})

describe("classification mirrors gaze.classify", () => {
  it.each([
    [reading(), ZONE, "IN"],
    [reading({ headPitch: 30 }), ZONE, "HEAD_POSE_DOWN"],
    [reading({ headPitch: -25 }), ZONE, "HEAD_POSE_UP"],
    [reading({ headYaw: 30 }), ZONE, "HEAD_POSE_SIDE"],
    [reading({ gazeV: 0.95 }), ZONE, "GAZE_AWAY"],
    [reading({ gazeV: 0.95, blink: true }), ZONE, "BLINK"],
    [reading({ headPitch: 30, blink: true }), ZONE, "HEAD_POSE_DOWN"],
    [reading({ faceCount: 0 }), ZONE, "NEUTRAL"],
    [reading({ faceCount: 2 }), ZONE, "NEUTRAL"],
    [reading({ headPitch: 18 }), ZONE, "HEAD_POSE_DOWN"],
    [reading({ headPitch: 18 }), null, "IN"],
    [reading({ headPitch: -18 }), null, "HEAD_POSE_UP"],
    [reading({ gazeH: 0.7 }), null, "GAZE_AWAY"],
  ])("classifies %#", (value, zone, label) => {
    expect(classifyReading(value, zone)).toBe(label)
  })

  it("uses the same default limits as the backend", () => {
    expect(DEFAULT_GAZE_ZONE).toEqual({
      pitch_min: -15,
      pitch_max: 20,
      yaw_min: -16,
      yaw_max: 16,
      gaze_h_min: -0.6,
      gaze_h_max: 0.6,
      gaze_v_min: -0.5,
      gaze_v_max: 0.6,
    })
  })
})

describe("AwayTracker (live hint, the server decides)", () => {
  const feed = (tracker: AwayTracker, labels: Parameters<AwayTracker["update"]>[0][], step = 100, start = 0) =>
    labels.map((label, index) => tracker.update(label, start + index * step))

  it("warns only after more than one second outside the zone", () => {
    const tracker = new AwayTracker()
    const states = feed(tracker, Array(14).fill("GAZE_AWAY"))
    expect(states.indexOf(true)).toBe(11) // 1100 ms after the first away sample
    expect(states.slice(0, 11).every((state) => !state)).toBe(true)
  })

  it("ignores blinks and unmeasurable frames and clears when the candidate looks back", () => {
    const tracker = new AwayTracker()
    const states = feed(tracker, ["IN", "GAZE_AWAY", "BLINK", "BLINK", "NEUTRAL", ...Array(10).fill("GAZE_AWAY"), "IN"])
    expect(states.at(-2)).toBe(true)
    expect(states.at(-1)).toBe(false)
    const clean = feed(new AwayTracker(), ["IN", "BLINK", "BLINK", "BLINK", "IN"])
    expect(clean.every((state) => !state)).toBe(true)
  })

  it("treats eyes closed for longer than a blink as away", () => {
    const tracker = new AwayTracker()
    const states = feed(tracker, Array(14).fill("BLINK"))
    expect(states.at(-1)).toBe(true)
    expect(states[8]).toBe(false)
  })
})

describe("telemetry", () => {
  const at = (offset: number, extra: Partial<TimedReading> = {}): TimedReading => ({ ...reading(), at: 1_000 + offset, ...extra })

  it("keeps the samples of the window as offsets and respects the server limits", () => {
    const readings = [at(-50), at(0), at(10), at(66), at(132), at(2500), at(5000)]
    const samples = samplesForWindow(readings, 1_000, 2400)
    expect(samples.map((sample) => sample.t_ms)).toEqual([0, 66, 132]) // 10 ms later is faster than ~33 fps
    expect(samples[0]).toEqual({
      t_ms: 0,
      head_pitch: 0,
      head_yaw: 0,
      gaze_h: 0,
      gaze_v: 0,
      blink: false,
      face_count: 1,
      mouth_open: null, // a reading without a mouth measurement is not a closed mouth
    })
    const dense = Array.from({ length: 200 }, (_, index) => at(index * 33))
    expect(samplesForWindow(dense, 1_000, 30_000).length).toBe(60)
  })

  it("reports a missing or doubled face without measurements", () => {
    expect(readingFromResult({ faceLandmarks: [] }, 5)).toMatchObject({ faceCount: 0, headPitch: null, gazeH: null })
    expect(readingFromResult({ faceLandmarks: [[], []] }, 5).faceCount).toBe(2)
    const result = readingFromResult(
      {
        faceLandmarks: [frontalFace(eyePoints(0.012, 0))],
        faceBlendshapes: [{ categories: [{ categoryName: "eyeBlinkLeft", score: 0.9 }, { categoryName: "eyeBlinkRight", score: 0.9 }] }],
        facialTransformationMatrixes: [{ data: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1] }],
      },
      7,
    )
    expect(result).toMatchObject({ at: 7, faceCount: 1, blink: true })
    expect(result.gazeH).toBeCloseTo(0.8, 6)
    expect(result.headPitch).toBeCloseTo(0, 6)
  })
})

// ---- mouth aperture (T8 / S11): same landmarks and numbers as backend/tests/test_mouth_open_parity.py -------

function mouthLandmarks(lipGap: number): Point[] {
  const points: Point[] = Array.from({ length: 478 }, () => ({ x: 0.5, y: 0.5, z: 0 }))
  points[78] = { x: 0.43, y: 0.65, z: 0 }
  points[308] = { x: 0.57, y: 0.65, z: 0 }
  points[13] = { x: 0.5, y: 0.65, z: 0 }
  points[14] = { x: 0.5, y: 0.65 + lipGap, z: 0 }
  return points
}

describe("mouth aperture mirrors mouth_open_score", () => {
  it.each([
    ["closed", 0, {}, 0],
    ["inner lip ratio only", 0.021, {}, 0.21],
    ["jawOpen softened by mouthClose", 0, { jawOpen: 0.3, mouthClose: 0.5 }, 0.2175],
    ["mouthClose never takes jawOpen below a fifth", 0, { jawOpen: 0.4, mouthClose: 1 }, 0.18],
    ["funnel and pucker", 0, { mouthFunnel: 0.4, mouthPucker: 0.2 }, 0.275],
    ["the largest signal wins", 0.021, { jawOpen: 0.4, mouthClose: 1 }, 0.21],
  ])("%s", (_name, gap, blendshapes, expected) => {
    expect(mouthOpenScore(mouthLandmarks(gap), blendshapes)).toBeCloseTo(expected, 9)
  })

  it("is closed, not an error, for a degenerate mouth", () => {
    expect(mouthOpenScore(Array.from({ length: 478 }, () => ({ x: 0.5, y: 0.5, z: 0 })), {})).toBe(0)
  })

  it("is part of every single-face reading and absent otherwise", () => {
    const result = readingFromResult(
      {
        faceLandmarks: [mouthLandmarks(0.021)],
        faceBlendshapes: [{ categories: [{ categoryName: "jawOpen", score: 0.1 }] }],
      },
      5,
    )
    expect(result.mouthOpen).toBeCloseTo(0.21, 9)
    expect(readingFromResult({ faceLandmarks: [] }, 5).mouthOpen).toBeNull()
  })
})

describe("mouth telemetry for the voice calibration", () => {
  const at = (offset: number, mouthOpen: number | null, faceCount = 1): TimedReading => ({
    ...reading({ faceCount }),
    at: 5_000 + offset,
    mouthOpen,
  })

  it("keeps single-face readings with a mouth measurement as offsets, thinned to the server limits", () => {
    const readings = [at(-10, 0.1), at(0, 0.1), at(10, 0.2), at(66, 0.3), at(100, null), at(132, 0.4, 2), at(200, 0.5)]
    expect(mouthSamplesForWindow(readings, 5_000, 9_000)).toEqual([
      { t_ms: 0, mouth_open: 0.1 },
      { t_ms: 66, mouth_open: 0.3 },
      { t_ms: 200, mouth_open: 0.5 },
    ])
  })

  it("never exceeds the 450 samples the server accepts", () => {
    const dense = Array.from({ length: 600 }, (_, index) => at(index * 33, 0.2))
    expect(mouthSamplesForWindow(dense, 5_000, 30_000).length).toBe(450)
  })

  it("rounds and bounds the aperture to what the server validates (0 to 2)", () => {
    expect(mouthSamplesForWindow([at(0, 3.456789)], 5_000, 1000)).toEqual([{ t_ms: 0, mouth_open: 2 }])
    expect(mouthSamplesForWindow([at(0, 0.123456)], 5_000, 1000)).toEqual([{ t_ms: 0, mouth_open: 0.123 }])
  })

  it("adds mouth_open to the audiovisual telemetry samples", () => {
    const [sample] = samplesForWindow([at(0, 0.2346)], 5_000, 2400)
    expect(sample.mouth_open).toBe(0.235)
  })
})
