import { describe, expect, it } from "vitest"
import {
  ATTACK_IGNORE_MS,
  BACK_THUMB_LABEL,
  NO_FLUTE_SOUND_REASON,
  UNCERTAIN_HOLE_MESSAGE,
  buildFluteInferPayload,
  describeFingerStates,
  fluteSplitModeLabel,
  isLegacyFluteModel,
  isVoicedFrame,
  pushFreeWindow,
  scoreExamSegment,
  segmentProgressPct,
  smoothFreeWindow,
  type LiveFrame,
  type TimedFrame,
} from "@/components/admin/flute/flute-live-scoring"
import { FLUTE_AUDIO_SCHEMA } from "@/components/admin/flute/flute-note-specs"
import { FLUTE_VISUAL_SCHEMA } from "@/components/admin/flute/flute-hand-features"
import type { FluteFingerState } from "@/services/dataset-sample-service"

function frame(overrides: Partial<LiveFrame> = {}): LiveFrame {
  return {
    voiced: true,
    sound_class: "SOL",
    sound_ok: true,
    pitch_hz: 784,
    pitch_cents_off: 0,
    posture_ok: true,
    posture_reason: null,
    mismatched_holes: [],
    ...overrides,
  }
}

/** Frames every 150 ms starting at 0 ms (0, 150, 300, 450, ...). */
function timed(frames: LiveFrame[], stepMs = 150): TimedFrame[] {
  return frames.map((prediction, i) => ({
    elapsedMs: i * stepMs,
    voiced: prediction.voiced,
    prediction,
  }))
}

describe("isVoicedFrame", () => {
  it("uses the backend voiced flag", () => {
    expect(isVoicedFrame({ voiced: true })).toBe(true)
    expect(isVoicedFrame({ voiced: false })).toBe(false)
  })
  it("falls back to audio feature [48] === 1", () => {
    const audio = Array<number>(62).fill(0)
    audio[48] = 1
    expect(isVoicedFrame({ voiced: false }, audio)).toBe(true)
    audio[48] = 0
    expect(isVoicedFrame({ voiced: false }, audio)).toBe(false)
  })
})

describe("segmentProgressPct (real elapsed time)", () => {
  it("derives progress from wall-clock timestamps and clamps to 0..100", () => {
    expect(segmentProgressPct(1000, 1000, 4000)).toBe(0)
    expect(segmentProgressPct(1000, 3000, 4000)).toBe(50)
    expect(segmentProgressPct(1000, 9000, 4000)).toBe(100)
    expect(segmentProgressPct(1000, 500, 4000)).toBe(0)
  })
})

describe("scoreExamSegment (S10 exam mode)", () => {
  it("ignores frames in the first 400 ms of the segment", () => {
    const wrong = frame({ sound_class: "LA", sound_ok: false, posture_ok: false })
    // 0, 150, 300 ms are attack frames (wrong); 450.. ms are correct.
    const frames = timed([wrong, wrong, wrong, ...Array.from({ length: 7 }, () => frame())])
    const score = scoreExamSegment(frames)
    expect(ATTACK_IGNORE_MS).toBe(400)
    expect(score.postAttackFrames).toBe(7)
    expect(score.voicedFrames).toBe(7)
    expect(score.soundScorePct).toBe(100)
    expect(score.detectedNote).toBe("SOL")
    expect(score.postureOk).toBe(true)
    expect(score.segmentTotalPct).toBe(100)
  })

  it("includes a frame exactly at 400 ms", () => {
    const frames: TimedFrame[] = [
      { elapsedMs: 399, voiced: true, prediction: frame({ sound_ok: false, sound_class: "LA" }) },
      { elapsedMs: 400, voiced: true, prediction: frame() },
      { elapsedMs: 550, voiced: true, prediction: frame() },
      { elapsedMs: 700, voiced: true, prediction: frame() },
    ]
    const score = scoreExamSegment(frames)
    expect(score.postAttackFrames).toBe(3)
    expect(score.soundScorePct).toBe(100)
  })

  it("scores only voiced frames when at least 40% of post-attack frames are voiced", () => {
    const silent = frame({ voiced: false, sound_class: "NO_FLAUTA", sound_ok: false })
    // attack frames (3) + 10 post-attack: 6 voiced matching, 4 silent
    const frames = timed([
      silent, silent, silent,
      ...Array.from({ length: 6 }, () => frame()),
      ...Array.from({ length: 4 }, () => silent),
    ])
    const score = scoreExamSegment(frames)
    expect(score.postAttackFrames).toBe(10)
    expect(score.voicedFrames).toBe(6)
    expect(score.matchedFrames).toBe(6)
    expect(score.soundScorePct).toBe(100)
    expect(score.soundReason).toBeNull()
  })

  it("uses ceil(0.4 * postAttackFrames) as the denominator floor for mostly silent segments", () => {
    const silent = frame({ voiced: false, sound_class: "NO_FLAUTA", sound_ok: false })
    // 10 post-attack frames, 3 voiced matching → 3 / max(3, 4) = 75%
    const frames = timed([
      silent, silent, silent,
      ...Array.from({ length: 3 }, () => frame()),
      ...Array.from({ length: 7 }, () => silent),
    ])
    const score = scoreExamSegment(frames)
    expect(score.voicedFrames).toBe(3)
    expect(score.soundScorePct).toBe(75)
    expect(score.segmentTotalPct).toBe(Math.round(75 * 0.75 + 25))
  })

  it("counts only matching voiced frames", () => {
    const wrong = frame({ sound_class: "LA", sound_ok: false })
    const frames = timed([frame(), frame(), frame(), frame(), frame(), wrong, wrong, frame()])
    // post-attack: indexes 3..7 → frame, frame, wrong, wrong, frame
    const score = scoreExamSegment(frames)
    expect(score.voicedFrames).toBe(5)
    expect(score.matchedFrames).toBe(3)
    expect(score.soundScorePct).toBe(60)
  })

  it("gives sound 0 with reason when fewer than 3 voiced frames, and the segment scores 0", () => {
    const silent = frame({ voiced: false, sound_class: "NO_FLAUTA", sound_ok: false })
    const frames = timed([
      silent, silent, silent,
      frame(), frame(),
      silent, silent, silent, silent,
    ])
    const score = scoreExamSegment(frames)
    expect(score.voicedFrames).toBe(2)
    expect(score.soundScorePct).toBe(0)
    expect(score.soundReason).toBe(NO_FLUTE_SOUND_REASON)
    expect(score.soundReason).toBe("No se detectó sonido de flauta")
    expect(score.detectedNote).toBe("NO_FLAUTA")
    expect(score.postureOk).toBe(true)
    expect(score.segmentTotalPct).toBe(0)
  })

  it("posture is null with fewer than 3 evaluable frames, and the segment is inconclusive", () => {
    const noHands = frame({ posture_ok: null, posture_reason: "Falta la mano derecha" })
    const frames = timed([frame(), frame(), frame(), frame(), frame(), noHands, noHands, noHands])
    const score = scoreExamSegment(frames)
    expect(score.postureOk).toBeNull()
    expect(score.postureReason).toBe("Falta la mano derecha")
    expect(score.segmentTotalPct).toBeNull()
  })

  it("posture is null when less than 70% of post-attack frames are evaluable", () => {
    const noHands = frame({ posture_ok: null, posture_reason: null })
    // post-attack: 6 evaluable + 4 not evaluable = 60%
    const frames = timed([
      frame(), frame(), frame(),
      ...Array.from({ length: 6 }, () => frame()),
      ...Array.from({ length: 4 }, () => noHands),
    ])
    const score = scoreExamSegment(frames)
    expect(score.postureOk).toBeNull()
    expect(score.postureReason).toBe("Digitación inconclusa: faltan observaciones fiables.")
  })

  it("posture is true when at least 50% of evaluable frames have posture_ok, false otherwise", () => {
    const bad = frame({ posture_ok: false })
    const half = scoreExamSegment(timed([frame(), frame(), frame(), frame(), frame(), bad, bad]))
    expect(half.postureOk).toBe(true)
    expect(half.segmentTotalPct).toBe(100)
    const mostlyBad = scoreExamSegment(timed([frame(), frame(), frame(), frame(), bad, bad, bad]))
    expect(mostlyBad.postureOk).toBe(false)
    expect(mostlyBad.segmentTotalPct).toBe(75)
  })
})

describe("scoreExamSegment mismatched holes (S7)", () => {
  it("reports holes mismatched in at least half of the evaluable post-attack frames", () => {
    const wrong4 = frame({ posture_ok: false, mismatched_holes: [4] })
    const wrong4and6 = frame({ posture_ok: false, mismatched_holes: [4, 6] })
    const attackWrong = frame({ posture_ok: false, mismatched_holes: [1, 2, 3] })
    // attack frames ignored; post-attack: wrong4, wrong4and6, ok, ok → hole 4 in 2/4, hole 6 in 1/4
    const score = scoreExamSegment(timed([attackWrong, attackWrong, attackWrong, wrong4, wrong4and6, frame(), frame()]))
    expect(score.mismatchedHoles).toEqual([4])
  })

  it("reports no holes when posture is not evaluable", () => {
    const noHands = frame({ posture_ok: null, mismatched_holes: [] })
    expect(scoreExamSegment(timed([noHands, noHands, noHands, noHands])).mismatchedHoles).toEqual([])
  })
})

describe("free-mode smoothing (S10 free mode)", () => {
  const free = (prediction: LiveFrame) => ({ voiced: prediction.voiced, prediction })

  it("keeps only the last 3 frames", () => {
    let window = pushFreeWindow([], free(frame({ pitch_hz: 1 })))
    window = pushFreeWindow(window, free(frame({ pitch_hz: 2 })))
    window = pushFreeWindow(window, free(frame({ pitch_hz: 3 })))
    window = pushFreeWindow(window, free(frame({ pitch_hz: 4 })))
    expect(window.map((f) => f.prediction.pitch_hz)).toEqual([2, 3, 4])
  })

  it("uses the most frequent voiced sound_class and the median voiced pitch", () => {
    const state = smoothFreeWindow([
      free(frame({ sound_class: "SOL", pitch_hz: 780, pitch_cents_off: -9 })),
      free(frame({ sound_class: "LA", pitch_hz: 880, pitch_cents_off: 2 })),
      free(frame({ sound_class: "SOL", pitch_hz: 786, pitch_cents_off: 4 })),
    ])
    expect(state.note).toBe("SOL")
    expect(state.pitchHz).toBe(786)
    expect(state.centsOff).toBe(-2.5)
  })

  it("does not show a note when fewer than 2 of the last frames agree on a voiced note", () => {
    const silent = frame({ voiced: false, sound_class: "NO_FLAUTA", pitch_hz: null, pitch_cents_off: null, posture_ok: null })
    const state = smoothFreeWindow([free(silent), free(frame()), free(silent)])
    expect(state.note).toBeNull()
    expect(state.pitchHz).toBe(784)
    expect(state.confirmedNote).toBeNull()
  })

  it("smooths posture by majority over evaluable frames (no Top-5 averaging)", () => {
    const bad = frame({ posture_ok: false })
    const noHands = frame({ posture_ok: null })
    expect(smoothFreeWindow([free(frame()), free(bad), free(frame())]).postureOk).toBe(true)
    expect(smoothFreeWindow([free(bad), free(bad), free(frame())]).postureOk).toBe(false)
    expect(smoothFreeWindow([free(noHands), free(noHands), free(frame())]).postureOk).toBeNull()
    expect(smoothFreeWindow([free(noHands), free(frame()), free(bad)]).postureOk).toBe(false)
  })

  it("confirms a note only when smoothed sound and smoothed posture agree", () => {
    const bad = frame({ posture_ok: false })
    expect(smoothFreeWindow([free(frame()), free(frame()), free(bad)]).confirmedNote).toBe("SOL")
    expect(smoothFreeWindow([free(frame()), free(bad), free(bad)]).confirmedNote).toBeNull()
    expect(
      smoothFreeWindow([
        free(frame({ sound_class: "NO_FLAUTA", sound_ok: false })),
        free(frame({ sound_class: "NO_FLAUTA", sound_ok: false })),
        free(frame()),
      ]).confirmedNote
    ).toBeNull()
  })
})

describe("describeFingerStates (S7)", () => {
  const states: FluteFingerState[] = [1, 2, 3, 4, 5, 6, 7].map((hole) => ({
    hole,
    expected: hole <= 3,
    covered_probability: hole <= 3 ? 0.9 : 0.1,
    match: true,
  }))

  it("returns 7 holes, 1-3 left hand and 4-7 right hand", () => {
    const view = describeFingerStates(states)
    expect(view.map((h) => h.hole)).toEqual([1, 2, 3, 4, 5, 6, 7])
    expect(view.map((h) => h.hand)).toEqual(["left", "left", "left", "right", "right", "right", "right"])
    expect(view.every((h) => h.message === null)).toBe(true)
  })

  it("explains mismatched holes", () => {
    const wrong = states.map((s) =>
      s.hole === 4
        ? { ...s, expected: true, covered_probability: 0.2, match: false }
        : s.hole === 2
        ? { ...s, expected: false, covered_probability: 0.8, match: false }
        : s
    )
    const view = describeFingerStates(wrong)
    expect(view[3].message).toBe("Hueco 4 debería estar tapado")
    expect(view[1].message).toBe("Hueco 2 debería estar destapado")
    expect(view[3].covered).toBe(false)
    expect(view[1].covered).toBe(true)
  })

  it("returns 7 unknown holes when finger states are not available", () => {
    const view = describeFingerStates(null)
    expect(view).toHaveLength(7)
    expect(view.every((h) => h.match === null && h.expected === null && h.message === null)).toBe(true)
  })

  it("marks uncertain holes as neutral instead of wrong", () => {
    const withUncertain = states.map((s) =>
      s.hole === 5 ? { ...s, expected: false, covered_probability: 0.5, match: null } : s
    )
    const view = describeFingerStates(withUncertain, [5])
    expect(view[4].uncertain).toBe(true)
    expect(view[4].match).toBeNull()
    expect(view[4].message).toBe("Hueco 5: la cámara no lo ve con claridad")
    expect(UNCERTAIN_HOLE_MESSAGE(5)).toBe("Hueco 5: la cámara no lo ve con claridad")
    expect(view.filter((h) => h.uncertain).map((h) => h.hole)).toEqual([5])
    expect(view.filter((h) => h.match === false)).toHaveLength(0)
  })

  it("defaults to no uncertain holes", () => {
    expect(describeFingerStates(states).every((h) => !h.uncertain)).toBe(true)
  })

  it("labels the back thumb as not evaluable by camera", () => {
    expect(BACK_THUMB_LABEL).toContain("no evaluable por cámara")
  })
})

describe("buildFluteInferPayload", () => {
  it("always sends both schemas", () => {
    const payload = buildFluteInferPayload([1, 2], [3, 4], "SOL")
    expect(payload).toEqual({
      target_note: "SOL",
      audio_features: [1, 2],
      audio_schema: FLUTE_AUDIO_SCHEMA,
      visual_features: [3, 4],
      visual_schema: FLUTE_VISUAL_SCHEMA,
    })
    expect(buildFluteInferPayload([], [], null).target_note).toBeNull()
  })
})

describe("training studio helpers (S2/S11 display)", () => {
  it("labels split modes", () => {
    expect(fluteSplitModeLabel("participant")).toBe("Validado con personas independientes")
    expect(fluteSplitModeLabel("session")).toBe("Intra-persona, otra sesión")
    expect(fluteSplitModeLabel("take")).toBe("Intra-persona, otras tomas (optimista)")
    expect(fluteSplitModeLabel("none")).toBe("Sin partición de prueba")
    expect(fluteSplitModeLabel(undefined)).toBe("Sin partición de prueba")
  })

  it("flags models whose audio or visual schema differs from the current extractors", () => {
    expect(isLegacyFluteModel({ audio_schema: FLUTE_AUDIO_SCHEMA, visual_schema: FLUTE_VISUAL_SCHEMA })).toBe(false)
    expect(isLegacyFluteModel({ audio_schema: undefined, visual_schema: FLUTE_VISUAL_SCHEMA })).toBe(true)
    expect(isLegacyFluteModel({ audio_schema: FLUTE_AUDIO_SCHEMA, visual_schema: "hand-landmarks-palm-v4" })).toBe(true)
  })
})
