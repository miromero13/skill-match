import { act, fireEvent, render, screen, within } from "@testing-library/react"
import { createRef } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type {
  FluteSong,
  FluteSongNote,
  FluteSongNoteResult,
  FluteSongScore,
  ScoreFluteSongPayload,
} from "@/services/flute-song-service"
import type { HandFrame } from "@/components/admin/flute/flute-hand-features"

vi.mock("@/services/flute-song-service", () => ({
  listFluteSongs: vi.fn(),
  scoreFluteSong: vi.fn(),
}))

vi.mock("@/components/admin/flute/flute-note-specs", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/components/admin/flute/flute-note-specs")>()
  return {
    ...actual,
    estimatePitchYin: vi.fn(() => ({ hz: 659.3, clarity: 0.95 })),
    extractFluteAudioFeatures: vi.fn(() => Array<number>(62).fill(0.1)),
  }
})

import { listFluteSongs, scoreFluteSong } from "@/services/flute-song-service"
import {
  FluteSongPractice,
  FluteSongResultView,
  FluteSongStrip,
  type SongCaptureDevices,
} from "@/components/admin/flute/flute-song-practice"

const PASS_ONE = ["MI", "MI", "FA", "SOL", "SOL", "FA", "MI", "RE", "DO", "DO", "RE", "MI", "MI", "RE", "RE"]
const PASS_TWO = ["MI", "MI", "FA", "SOL", "SOL", "FA", "MI", "RE", "DO", "DO", "RE", "MI", "RE", "DO", "DO"]

const buildPass = (names: string[], pass: 1 | 2, offset: number): FluteSongNote[] =>
  names.map((note, i) => ({
    index: offset + i,
    pass,
    note,
    start_beats: (pass - 1) * 16 + i,
    duration_beats: i === names.length - 1 ? 2 : 1,
  }))

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

function noteResult(note: FluteSongNote): FluteSongNoteResult {
  return {
    index: note.index,
    pass: note.pass,
    note: note.note,
    expected_start_s: note.start_beats * 0.5,
    duration_s: note.duration_beats * 0.5,
    detected_note: note.note,
    pitch_share: 0.9,
    onset_ms: 10,
    timing_ok: true,
    repeated: false,
    articulation_ok: null,
    flute_ok: null,
    posture_ok: null,
    posture_reason: "Sin modelo activo",
    mismatched_holes: [],
    correct: true,
  }
}

const SCORE: FluteSongScore = {
  song_id: "himno_alegria",
  tempo_bpm: 120,
  model_version: null,
  latency_offset_ms: 40,
  tuning_offset_cents: 0,
  notes: HIMNO.notes.map((n) =>
    n.index === 1
      ? {
          ...noteResult(n),
          detected_note: "RE",
          pitch_share: 0.1,
          onset_ms: 120,
          posture_ok: false,
          posture_reason: null,
          mismatched_holes: [4, 5],
          correct: false,
        }
      : n.index === 0
      ? { ...noteResult(n), posture_ok: true, posture_reason: null }
      : noteResult(n)
  ),
  notes_correct: 29,
  notes_total: 30,
  sound_score: 96.67,
  posture_score: null,
  total_score: 96.67,
  approved: true,
  message: "Canción calificada: 29 de 30 notas correctas.",
}

const ok = <T,>(data: T, message = "OK") => ({ statuscode: 200, message, data })

beforeEach(() => {
  vi.mocked(listFluteSongs).mockResolvedValue(ok([HIMNO]))
  vi.mocked(scoreFluteSong).mockResolvedValue(ok(SCORE, SCORE.message))
})

afterEach(() => {
  vi.useRealTimers()
})

describe("FluteSongStrip / FluteSongResultView (S3, S4, S6 display)", () => {
  it("colors the strip chips from the results and shows the per-note table", () => {
    render(<FluteSongStrip song={HIMNO} activeIndex={null} results={SCORE.notes} />)
    expect(screen.getByText("1ª vuelta")).toBeInTheDocument()
    expect(screen.getByText("2ª vuelta")).toBeInTheDocument()
    expect(screen.getByTestId("flute-song-chip-0")).toHaveAttribute("data-status", "correct")
    expect(screen.getByTestId("flute-song-chip-1")).toHaveAttribute("data-status", "wrong")
    expect(screen.getByTestId("flute-song-chip-29")).toHaveAttribute("data-status", "correct")
  })

  it("shows pending gray chips without results and highlights the active one", () => {
    render(<FluteSongStrip song={HIMNO} activeIndex={3} />)
    const chips = screen.getAllByTestId(/flute-song-chip-/)
    expect(chips).toHaveLength(30)
    expect(chips.every((c) => c.getAttribute("data-status") === "pending")).toBe(true)
    expect(screen.getByTestId("flute-song-chip-3")).toHaveAttribute("data-active", "true")
    expect(screen.getByTestId("flute-song-chip-3")).toHaveTextContent("Sol")
  })

  it("renders the verdict, scores, message and fingering states", () => {
    render(<FluteSongResultView score={SCORE} />)
    expect(screen.getByTestId("flute-song-verdict")).toHaveTextContent("Aprobado")
    expect(screen.getByText("Notas correctas: 29 / 30")).toBeInTheDocument()
    expect(screen.getByText("97 / 100")).toBeInTheDocument()
    expect(
      screen.getByText("Digitación no evaluable (sin modelo o sin datos de estas notas)")
    ).toBeInTheDocument()
    expect(screen.getByText(SCORE.message)).toBeInTheDocument()

    const wrong = within(screen.getByTestId("flute-song-row-1"))
    expect(wrong.getByText("Re")).toBeInTheDocument()
    expect(wrong.getByText("+120 ms tarde")).toBeInTheDocument()
    expect(wrong.getByText("✗")).toBeInTheDocument()
    expect(wrong.getByText("Huecos: 4, 5")).toBeInTheDocument()
    expect(wrong.getByText("✗ Incorrecta")).toBeInTheDocument()

    expect(within(screen.getByTestId("flute-song-row-0")).getByText("✓")).toBeInTheDocument()
    const unjudged = within(screen.getByTestId("flute-song-row-2"))
    expect(unjudged.getByText("no evaluable")).toBeInTheDocument()
    expect(unjudged.getByText("a tiempo")).toBeInTheDocument()
    expect(unjudged.getByText("✓ Correcta")).toBeInTheDocument()
  })

  it("shows Reprobado and the fingering score when evaluable", () => {
    render(
      <FluteSongResultView
        score={{ ...SCORE, approved: false, posture_score: 50, total_score: 60 }}
      />
    )
    expect(screen.getByTestId("flute-song-verdict")).toHaveTextContent("Reprobado")
    expect(screen.getByText("Digitación: 50 / 100")).toBeInTheDocument()
  })
})

interface FakeClock {
  now: number
  starts: number[]
}

function fakeDevices(clock: FakeClock): SongCaptureDevices {
  const node = { connect: vi.fn(), disconnect: vi.fn() }
  const ctx = {
    get currentTime() {
      return clock.now
    },
    sampleRate: 44100,
    state: "running",
    destination: {},
    resume: vi.fn(() => Promise.resolve()),
    createBuffer: (_ch: number, length: number) => {
      const data = new Float32Array(length)
      return { getChannelData: () => data }
    },
    createBufferSource: () => ({
      ...node,
      buffer: null,
      start: (at: number) => clock.starts.push(at),
      stop: vi.fn(),
    }),
    createGain: () => ({ ...node, gain: { value: 1 } }),
  }
  const analyser = {
    fftSize: 2048,
    getFloatTimeDomainData: (buf: Float32Array) => buf.fill(0.1),
  }
  return {
    audioContext: ctx as unknown as AudioContext,
    analyser: analyser as unknown as AnalyserNode,
    sampleRate: 44100,
  }
}

describe("FluteSongPractice (S1, S3, S5)", () => {
  it("loads the song catalog, shows the score image, tempo and the 30 pending chips", async () => {
    render(
      <FluteSongPractice
        devices={null}
        requestDevices={vi.fn()}
        handFrameRef={createRef<HandFrame | null>()}
      />
    )
    const image = await screen.findByAltText("Partitura: Himno a la Alegría")
    expect(image).toHaveAttribute("src", "/flute-songs/himno_la_alegria.png")
    expect(screen.getByText("Tempo: 120 BPM")).toBeInTheDocument()
    expect(screen.getAllByTestId(/flute-song-chip-/)).toHaveLength(30)
    expect(screen.getByRole("button", { name: /Empezar/ })).toBeEnabled()
  })

  it("counts in 4 clicks before t0, captures, scores relative to t0 and shows the verdict", async () => {
    const clock: FakeClock = { now: 10, starts: [] }
    const devices = fakeDevices(clock)
    const requestDevices = vi.fn(() => Promise.resolve(devices))
    const handFrameRef = createRef<HandFrame | null>()
    render(
      <FluteSongPractice devices={null} requestDevices={requestDevices} handFrameRef={handFrameRef} />
    )
    await screen.findByAltText("Partitura: Himno a la Alegría")
    vi.useFakeTimers()

    fireEvent.click(screen.getByRole("button", { name: /Empezar/ }))
    await act(async () => {
      await Promise.resolve()
    })
    expect(requestDevices).toHaveBeenCalledTimes(1)
    const t0 = 10 + 0.15 + 2
    expect(clock.starts.map((s) => Number((s - t0).toFixed(6)))).toEqual([-2, -1.5, -1, -0.5])

    act(() => vi.advanceTimersByTime(100))
    expect(screen.getByTestId("flute-song-countin")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Detener/ })).toBeInTheDocument()

    for (let step = 0; step < 200; step++) {
      clock.now += 0.1
      handFrameRef.current = {
        features: Array<number>(50).fill(0.5),
        hands: [],
        timestamp: performance.now(),
      }
      act(() => vi.advanceTimersByTime(100))
    }
    await act(async () => {
      await Promise.resolve()
    })

    expect(clock.starts).toHaveLength(4)
    expect(scoreFluteSong).toHaveBeenCalledTimes(1)
    const payload: ScoreFluteSongPayload = vi.mocked(scoreFluteSong).mock.calls[0][0]
    expect(payload.song_id).toBe("himno_alegria")
    expect(payload.tempo_bpm).toBe(120)
    expect(payload.audio_schema).toBe("flute-audio-pitch-v1")
    expect(payload.visual_schema).toBe("hand-landmarks-palm-v5")
    expect(payload.pitch_track.length).toBeGreaterThan(100)
    expect(payload.pitch_track.every((p) => p.t >= -1 && p.t <= 16.5)).toBe(true)
    expect(payload.pitch_track[0]).toMatchObject({ hz: 659.3, clarity: 0.95 })
    expect(payload.pitch_track[0].rms).toBeCloseTo(0.1, 5)
    expect(payload.audio_frames.length).toBeGreaterThan(10)
    expect(payload.audio_frames[0].features).toHaveLength(62)
    expect(payload.hand_frames.length).toBeGreaterThan(10)
    expect(payload.hand_frames[0].features).toHaveLength(50)

    expect(screen.getByTestId("flute-song-verdict")).toHaveTextContent("Aprobado")
    expect(screen.getByTestId("flute-song-chip-1")).toHaveAttribute("data-status", "wrong")
    expect(screen.getByRole("button", { name: /Repetir/ })).toBeInTheDocument()
  })

  it("«Detener» cancels the take without scoring", async () => {
    const clock: FakeClock = { now: 0, starts: [] }
    const devices = fakeDevices(clock)
    render(
      <FluteSongPractice
        devices={devices}
        requestDevices={vi.fn()}
        handFrameRef={createRef<HandFrame | null>()}
      />
    )
    await screen.findByAltText("Partitura: Himno a la Alegría")
    vi.useFakeTimers()
    fireEvent.click(screen.getByRole("button", { name: /Empezar/ }))
    await act(async () => {
      await Promise.resolve()
    })
    clock.now += 3
    act(() => vi.advanceTimersByTime(100))
    fireEvent.click(screen.getByRole("button", { name: /Detener/ }))
    clock.now += 30
    act(() => vi.advanceTimersByTime(500))
    expect(scoreFluteSong).not.toHaveBeenCalled()
    expect(screen.getByRole("button", { name: /Empezar/ })).toBeInTheDocument()
  })

  it("shows the backend message in an Alert when scoring fails", async () => {
    vi.mocked(scoreFluteSong).mockRejectedValue(new Error("Canción no encontrada"))
    const clock: FakeClock = { now: 0, starts: [] }
    render(
      <FluteSongPractice
        devices={fakeDevices(clock)}
        requestDevices={vi.fn()}
        handFrameRef={createRef<HandFrame | null>()}
      />
    )
    await screen.findByAltText("Partitura: Himno a la Alegría")
    vi.useFakeTimers()
    fireEvent.click(screen.getByRole("button", { name: /Empezar/ }))
    await act(async () => {
      await Promise.resolve()
    })
    clock.now += 30
    act(() => vi.advanceTimersByTime(100))
    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.getByText("Canción no encontrada")).toBeInTheDocument()
  })
})
