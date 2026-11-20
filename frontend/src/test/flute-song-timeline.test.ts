import { describe, expect, it } from "vitest"
import {
  AUDIO_FRAMES_MAX,
  COUNT_IN_BEATS,
  HAND_FRAMES_MAX,
  PITCH_TRACK_MAX,
  beatsToSeconds,
  buildScoreSongPayload,
  captureEndSeconds,
  capEvenly,
  computeRms,
  countInBeatAt,
  countInSchedule,
  currentNoteIndex,
  fingeringLabel,
  groupSongStrip,
  noteChipStatus,
  noteDisplayName,
  onsetLabel,
  passLabel,
  songDurationSeconds,
  songProgressPct,
} from "@/components/admin/flute/flute-song-timeline"
import type { FluteSong, FluteSongNote, FluteSongNoteResult } from "@/services/flute-song-service"

const PASS_ONE = ["MI", "MI", "FA", "SOL", "SOL", "FA", "MI", "RE", "DO", "DO", "RE", "MI", "MI", "RE", "RE"]
const PASS_TWO = ["MI", "MI", "FA", "SOL", "SOL", "FA", "MI", "RE", "DO", "DO", "RE", "MI", "RE", "DO", "DO"]

function buildPass(names: string[], pass: 1 | 2, offset: number): FluteSongNote[] {
  return names.map((note, i) => ({
    index: offset + i,
    pass,
    note,
    start_beats: (pass - 1) * 16 + i,
    duration_beats: i === names.length - 1 ? 2 : 1,
  }))
}

const HIMNO: FluteSong = {
  id: "himno_alegria",
  title: "Himno a la Alegría",
  default_bpm: 120,
  min_bpm: 60,
  max_bpm: 120,
  beats_per_bar: 4,
  image: "/flute-songs/himno_la_alegria.png",
  notes: [...buildPass(PASS_ONE, 1, 0), ...buildPass(PASS_TWO, 2, 15)],
}

describe("beats → seconds (S5 tempo scaling)", () => {
  it("converts beats at 120 and 60 BPM", () => {
    expect(beatsToSeconds(1, 120)).toBe(0.5)
    expect(beatsToSeconds(16, 120)).toBe(8)
    expect(beatsToSeconds(1, 60)).toBe(1)
  })

  it("song lasts 16 s at 120 BPM and 32 s at 60 BPM; capture stops 0.5 s later", () => {
    expect(songDurationSeconds(HIMNO, 120)).toBe(16)
    expect(songDurationSeconds(HIMNO, 60)).toBe(32)
    expect(captureEndSeconds(HIMNO, 120)).toBe(16.5)
  })
})

describe("count-in (S5: 4 audible beats before t=0)", () => {
  it("schedules 4 clicks ending one beat before t0", () => {
    expect(COUNT_IN_BEATS).toBe(4)
    expect(countInSchedule(120)).toEqual([-2, -1.5, -1, -0.5])
    expect(countInSchedule(60)).toEqual([-4, -3, -2, -1])
  })

  it("reports the beat number 1..4 during the count-in and null otherwise", () => {
    expect(countInBeatAt(120, -2.5)).toBeNull()
    expect(countInBeatAt(120, -2)).toBe(1)
    expect(countInBeatAt(120, -1.6)).toBe(1)
    expect(countInBeatAt(120, -1.5)).toBe(2)
    expect(countInBeatAt(120, -0.01)).toBe(4)
    expect(countInBeatAt(120, 0)).toBeNull()
  })
})

describe("currentNoteIndex / progress (S3 highlight)", () => {
  it("returns the note sounding at t", () => {
    expect(currentNoteIndex(HIMNO, 120, -0.1)).toBeNull()
    expect(currentNoteIndex(HIMNO, 120, 0)).toBe(0)
    expect(currentNoteIndex(HIMNO, 120, 0.49)).toBe(0)
    expect(currentNoteIndex(HIMNO, 120, 0.5)).toBe(1)
    expect(currentNoteIndex(HIMNO, 120, 7.9)).toBe(14)
    expect(currentNoteIndex(HIMNO, 120, 8)).toBe(15)
    expect(currentNoteIndex(HIMNO, 60, 16)).toBe(15)
    expect(currentNoteIndex(HIMNO, 120, 15.99)).toBe(29)
    expect(currentNoteIndex(HIMNO, 120, 16)).toBeNull()
  })

  it("progress is clamped to 0..100", () => {
    expect(songProgressPct(HIMNO, 120, -1)).toBe(0)
    expect(songProgressPct(HIMNO, 120, 8)).toBe(50)
    expect(songProgressPct(HIMNO, 120, 99)).toBe(100)
  })
})

describe("groupSongStrip (S3 30-chip strip)", () => {
  it("groups the 30 notes by pass and 4-beat bars", () => {
    const groups = groupSongStrip(HIMNO)
    expect(groups.map((g) => g.label)).toEqual(["1ª vuelta", "2ª vuelta"])
    expect(groups[0].bars.map((b) => b.notes.length)).toEqual([4, 4, 4, 3])
    expect(groups[1].bars.map((b) => b.notes.length)).toEqual([4, 4, 4, 3])
    expect(groups[1].bars[0].bar).toBe(5)
    expect(groups.flatMap((g) => g.bars.flatMap((b) => b.notes)).length).toBe(30)
  })
})

describe("computeRms", () => {
  it("is 0 for silence and the amplitude/√2 for a sine", () => {
    expect(computeRms(new Float32Array(64))).toBe(0)
    expect(computeRms(new Float32Array(0))).toBe(0)
    const sine = new Float32Array(1000).map((_, i) => 0.5 * Math.sin((2 * Math.PI * i) / 100))
    expect(computeRms(sine)).toBeCloseTo(0.5 / Math.SQRT2, 3)
  })
})

describe("capEvenly", () => {
  it("keeps short lists and downsamples long ones evenly keeping order", () => {
    expect(capEvenly([1, 2, 3], 5)).toEqual([1, 2, 3])
    const capped = capEvenly(Array.from({ length: 10 }, (_, i) => i), 5)
    expect(capped).toEqual([0, 2, 4, 6, 8])
  })
})

describe("buildScoreSongPayload (Contract)", () => {
  const pitch = (t: number) => ({ t, hz: 659.3, clarity: 0.95, rms: 0.05 })

  it("keeps samples in [-1.0 s, last note end + 0.5 s] and fills the schemas", () => {
    const payload = buildScoreSongPayload({
      song: HIMNO,
      tempoBpm: 120,
      pitchTrack: [pitch(-1.5), pitch(-1), pitch(0), pitch(16.5), pitch(16.6)],
      audioFrames: [{ t: -1.2, features: [1] }, { t: 3, features: [2] }],
      handFrames: [{ t: 17, features: [3] }, { t: 0.1, features: [4] }],
    })
    expect(payload).toEqual({
      song_id: "himno_alegria",
      tempo_bpm: 120,
      pitch_track: [pitch(-1), pitch(0), pitch(16.5)],
      audio_schema: "flute-audio-pitch-v1",
      audio_frames: [{ t: 3, features: [2] }],
      visual_schema: "hand-landmarks-palm-v5",
      hand_frames: [{ t: 0.1, features: [4] }],
    })
  })

  it("caps the tracks (pitch ≤ 4000, audio ≤ 1000, hands ≤ 1000) and sends an integer tempo in 60..120", () => {
    const many = Array.from({ length: 5000 }, (_, i) => i * 0.003)
    const payload = buildScoreSongPayload({
      song: HIMNO,
      tempoBpm: 59.6,
      pitchTrack: many.map(pitch),
      audioFrames: many.map((t) => ({ t, features: [] })),
      handFrames: many.map((t) => ({ t, features: [] })),
    })
    expect(PITCH_TRACK_MAX).toBe(4000)
    expect(AUDIO_FRAMES_MAX).toBe(1000)
    expect(HAND_FRAMES_MAX).toBe(1000)
    expect(payload.pitch_track).toHaveLength(4000)
    expect(payload.audio_frames).toHaveLength(1000)
    expect(payload.hand_frames).toHaveLength(1000)
    expect(payload.tempo_bpm).toBe(60)
  })
})

describe("result formatting (S4)", () => {
  it("labels onset offsets", () => {
    expect(onsetLabel(120)).toBe("+120 ms tarde")
    expect(onsetLabel(-80)).toBe("−80 ms adelantado")
    expect(onsetLabel(4)).toBe("a tiempo")
    expect(onsetLabel(-20.4)).toBe("a tiempo")
    expect(onsetLabel(null)).toBe("sin entrada detectada")
  })

  it("shows Do/Re/Mi/Fa/Sol names and pass labels", () => {
    expect(["DO", "RE", "MI", "FA", "SOL"].map(noteDisplayName)).toEqual([
      "Do",
      "Re",
      "Mi",
      "Fa",
      "Sol",
    ])
    expect(noteDisplayName(null)).toBe("—")
    expect(noteDisplayName("XYZ")).toBe("XYZ")
    expect(passLabel(1)).toBe("1ª vuelta")
    expect(passLabel(2)).toBe("2ª vuelta")
  })

  it("labels fingering and chip status", () => {
    expect(fingeringLabel(true)).toBe("✓")
    expect(fingeringLabel(false)).toBe("✗")
    expect(fingeringLabel(null)).toBe("no evaluable")
    const result = { correct: true } as FluteSongNoteResult
    expect(noteChipStatus(undefined)).toBe("pending")
    expect(noteChipStatus(result)).toBe("correct")
    expect(noteChipStatus({ ...result, correct: false })).toBe("wrong")
  })
})
