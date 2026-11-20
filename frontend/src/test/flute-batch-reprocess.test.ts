import { afterEach, describe, expect, it, vi } from "vitest"
import {
  REPROCESS_STOPPED_REASON,
  REPROCESS_UNKNOWN_DURATION_TIMEOUT_MS,
  collectReprocessFrame,
  describeReprocessProgress,
  finalizeReprocessTake,
  reprocessItemTimeoutMs,
  runReprocessQueue,
  selectPendingReprocessSamples,
  type ProcessOne,
  type ReprocessOutcome,
  type SaveFluteLabels,
} from "@/components/admin/flute/flute-reprocess-queue"
import { FLUTE_AUDIO_SCHEMA, buildPitchFeatures } from "@/components/admin/flute/flute-note-specs"
import { FLUTE_HAND_SLOT_DIM, FLUTE_VISUAL_SCHEMA } from "@/components/admin/flute/flute-hand-features"
import type { FluteFeatures, FlutePreviewSample } from "@/services/dataset-sample-service"

function sample(overrides: Partial<FlutePreviewSample> = {}): FlutePreviewSample {
  return {
    id: "aaaaaaaa-0000-0000-0000-000000000000",
    labeled: false,
    participant_id: "P1",
    note_label: "SOL",
    sound_label: "flauta",
    posture_label: "correcta",
    needs_reprocess: true,
    pitch_agreement: null,
    file_format: "mp4",
    ...overrides,
  }
}

function audioFrame(hz: number | null): number[] {
  return [...Array<number>(48).fill(0.1), ...buildPitchFeatures(hz, hz === null ? 0.2 : 0.95)]
}

function handFeatures(hands: 0 | 1 | 2): number[] {
  const features = Array<number>(FLUTE_HAND_SLOT_DIM * 2).fill(0.5)
  features[0] = hands >= 1 ? 1 : 0
  features[FLUTE_HAND_SLOT_DIM] = hands === 2 ? 1 : 0
  return features
}

function featureFrame(hz: number | null): FluteFeatures {
  return { visual_schema: FLUTE_VISUAL_SCHEMA, visual_features: handFeatures(1),
    audio_schema: FLUTE_AUDIO_SCHEMA, audio_features: audioFrame(hz) }
}

const ok: ReprocessOutcome = { ok: true }

afterEach(() => { vi.useRealTimers() })

describe("selectPendingReprocessSamples", () => {
  it("keeps only mp4 takes flagged needs_reprocess with participant, sound and posture labels, in order", () => {
    const keepA = sample({ id: "keep-a" })
    const keepB = sample({ id: "keep-b", note_label: null, sound_label: "voz", posture_label: "sin_manos" })
    const samples = [
      keepA,
      sample({ id: "already-v5", needs_reprocess: false, labeled: true }),
      sample({ id: "webm", file_format: "webm" }),
      sample({ id: "no-participant", participant_id: null }),
      sample({ id: "no-sound", sound_label: null }),
      sample({ id: "no-posture", posture_label: null }),
      keepB,
    ]
    expect(selectPendingReprocessSamples(samples).map(s => s.id)).toEqual(["keep-a", "keep-b"])
  })
})

describe("describeReprocessProgress", () => {
  it("shows position, note and participant", () => {
    expect(describeReprocessProgress({ index: 3, total: 22, sample: sample({ participant_id: "X" }) }))
      .toBe("Procesando 3 de 22 · SOL · participante X")
    expect(describeReprocessProgress({ index: 1, total: 2, sample: sample({ note_label: null, sound_label: "ruido" }) }))
      .toBe("Procesando 1 de 2 · ruido · participante P1")
  })
})

describe("reprocessItemTimeoutMs", () => {
  it("allows the video duration plus 10 s, or 30 s when the duration is unknown", () => {
    expect(reprocessItemTimeoutMs(12.5)).toBe(22_500)
    expect(reprocessItemTimeoutMs(Number.NaN)).toBe(30_000)
    expect(reprocessItemTimeoutMs(Number.POSITIVE_INFINITY)).toBe(30_000)
    expect(reprocessItemTimeoutMs(0)).toBe(30_000)
    expect(REPROCESS_UNKNOWN_DURATION_TIMEOUT_MS).toBe(30_000)
  })
})

describe("runReprocessQueue", () => {
  it("processes items sequentially in order, one at a time, reporting progress", async () => {
    const samples = [sample({ id: "s1" }), sample({ id: "s2" }), sample({ id: "s3" })]
    const order: string[] = []
    let active = 0
    let maxActive = 0
    const processOne: ProcessOne = async item => {
      active += 1
      maxActive = Math.max(maxActive, active)
      order.push(item.id)
      await new Promise(resolve => setTimeout(resolve, 1))
      active -= 1
      return ok
    }
    const progress: string[] = []
    const onSaved = vi.fn().mockResolvedValue(undefined)
    const summary = await runReprocessQueue({ samples, processOne, onSaved, signal: new AbortController().signal,
      onProgress: p => progress.push(`${p.index}/${p.total}:${p.sample.id}`) })
    expect(order).toEqual(["s1", "s2", "s3"])
    expect(maxActive).toBe(1)
    expect(progress).toEqual(["1/3:s1", "2/3:s2", "3/3:s3"])
    expect(summary).toEqual({ total: 3, okCount: 3, failures: [], stopped: false, notProcessed: 0 })
  })

  it("continues after rejected or throwing items and lists them with note, participant, short id and reason", async () => {
    const samples = [
      sample({ id: "11111111-ok" }),
      sample({ id: "22222222-rejected", note_label: "LA", participant_id: "P2" }),
      sample({ id: "33333333-throws", note_label: null, sound_label: "voz", participant_id: "P3" }),
      sample({ id: "44444444-ok" }),
    ]
    const rejection = "La altura detectada no corresponde a la nota LA (coincidencia 12%). Repetí la toma."
    const processOne = vi.fn<ProcessOne>(async item => {
      if (item.id.startsWith("2222")) return { ok: false, reason: rejection }
      if (item.id.startsWith("3333")) throw new Error("Error del servidor al guardar")
      return ok
    })
    const onSaved = vi.fn().mockResolvedValue(undefined)
    const summary = await runReprocessQueue({ samples, processOne, onSaved, signal: new AbortController().signal })
    expect(processOne).toHaveBeenCalledTimes(4)
    expect(summary.okCount).toBe(2)
    expect(summary.stopped).toBe(false)
    expect(summary.notProcessed).toBe(0)
    expect(summary.failures).toEqual([
      { id: "22222222-rejected", shortId: "22222222", note: "LA", participant: "P2", reason: rejection },
      { id: "33333333-throws", shortId: "33333333", note: "voz", participant: "P3", reason: "Error del servidor al guardar" },
    ])
    expect(onSaved).toHaveBeenCalledTimes(1)
  })

  it("calls onSaved exactly once, after the last item", async () => {
    const events: string[] = []
    const onSaved = vi.fn(async () => { events.push("saved") })
    await runReprocessQueue({ samples: [sample({ id: "a" }), sample({ id: "b" })], onSaved,
      signal: new AbortController().signal,
      processOne: async item => { events.push(item.id); return ok } })
    expect(onSaved).toHaveBeenCalledTimes(1)
    expect(events).toEqual(["a", "b", "saved"])
  })

  it("stop cancels the current item (not counted as failure), skips the rest and still calls onSaved once", async () => {
    const controller = new AbortController()
    const samples = [sample({ id: "a" }), sample({ id: "b" }), sample({ id: "c" }), sample({ id: "d" })]
    const seenSignals: AbortSignal[] = []
    const processOne = vi.fn<ProcessOne>((item, signal) => {
      seenSignals.push(signal)
      if (item.id === "a") return Promise.resolve(ok)
      // Item "b" never finishes by itself: the admin presses Detener while it plays.
      queueMicrotask(() => controller.abort())
      return new Promise<ReprocessOutcome>(() => undefined)
    })
    const onSaved = vi.fn().mockResolvedValue(undefined)
    const summary = await runReprocessQueue({ samples, processOne, onSaved, signal: controller.signal })
    expect(processOne.mock.calls.map(([item]) => item.id)).toEqual(["a", "b"])
    expect(seenSignals[1].aborted).toBe(true)
    expect(summary).toEqual({ total: 4, okCount: 1, failures: [], stopped: true, notProcessed: 3 })
    expect(onSaved).toHaveBeenCalledTimes(1)
  })

  it("Detener while a save is already in flight waits for it and counts the saved take honestly", async () => {
    const controller = new AbortController()
    const samples = [sample({ id: "a" }), sample({ id: "b" }), sample({ id: "c" })]
    let finishSave: () => void = () => undefined
    const processOne = vi.fn<ProcessOne>(async (_item, _signal, { markSaving }) => {
      markSaving()
      queueMicrotask(() => controller.abort()) // admin presses Detener during the POST
      await new Promise<void>(resolve => { finishSave = resolve; setTimeout(resolve, 0) })
      return ok
    })
    const onSaved = vi.fn().mockResolvedValue(undefined)
    const summary = await runReprocessQueue({ samples, processOne, onSaved, signal: controller.signal })
    finishSave()
    expect(processOne).toHaveBeenCalledTimes(1)
    expect(summary).toEqual({ total: 3, okCount: 1, failures: [], stopped: true, notProcessed: 2 })
    expect(onSaved).toHaveBeenCalledTimes(1)
  })

  it("a started save is not cut by the item deadline", async () => {
    vi.useFakeTimers()
    const processOne = vi.fn<ProcessOne>(async (_item, _signal, { markSaving, setDeadline }) => {
      setDeadline(1_000)
      markSaving()
      await new Promise<void>(resolve => setTimeout(resolve, 5_000))
      return ok
    })
    const run = runReprocessQueue({ samples: [sample()], processOne, onSaved: vi.fn().mockResolvedValue(undefined),
      signal: new AbortController().signal })
    await vi.advanceTimersByTimeAsync(6_000)
    expect(await run).toEqual({ total: 1, okCount: 1, failures: [], stopped: false, notProcessed: 0 })
  })

  it("does not process anything when already stopped, but still refreshes once", async () => {
    const controller = new AbortController()
    controller.abort()
    const processOne = vi.fn<ProcessOne>(async () => ok)
    const onSaved = vi.fn().mockResolvedValue(undefined)
    const summary = await runReprocessQueue({ samples: [sample()], processOne, onSaved, signal: controller.signal })
    expect(processOne).not.toHaveBeenCalled()
    expect(summary).toEqual({ total: 1, okCount: 0, failures: [], stopped: true, notProcessed: 1 })
    expect(onSaved).toHaveBeenCalledTimes(1)
  })

  it("fails an item that exceeds its deadline (30 s by default, or the one it sets) and moves on", async () => {
    vi.useFakeTimers()
    const samples = [sample({ id: "aaaaaaaa-slow" }), sample({ id: "bbbbbbbb-short" }), sample({ id: "cccccccc-ok" })]
    const signals: AbortSignal[] = []
    const processOne: ProcessOne = (item, signal, controls) => {
      signals.push(signal)
      if (item.id.startsWith("cccc")) return Promise.resolve(ok)
      if (item.id.startsWith("bbbb")) controls.setDeadline(5_000)
      return new Promise<ReprocessOutcome>(() => undefined)
    }
    const onSaved = vi.fn().mockResolvedValue(undefined)
    const run = runReprocessQueue({ samples, processOne, onSaved, signal: new AbortController().signal })
    await vi.advanceTimersByTimeAsync(29_999)
    expect(signals).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(signals[0].aborted).toBe(true)
    expect(signals).toHaveLength(2)
    await vi.advanceTimersByTimeAsync(5_000)
    const summary = await run
    expect(signals[1].aborted).toBe(true)
    expect(summary.okCount).toBe(1)
    expect(summary.failures.map(f => [f.shortId, f.reason])).toEqual([
      ["aaaaaaaa", "Tiempo de espera agotado (30 s). No se modificaron las etiquetas anteriores."],
      ["bbbbbbbb", "Tiempo de espera agotado (5 s). No se modificaron las etiquetas anteriores."],
    ])
    expect(onSaved).toHaveBeenCalledTimes(1)
  })
})

describe("collectReprocessFrame (shared single/batch frame gate)", () => {
  it("skips frames without a fresh hand frame without reading audio", () => {
    const readAudio = vi.fn(() => audioFrame(784))
    expect(collectReprocessFrame(sample(), null, readAudio)).toBeNull()
    expect(readAudio).not.toHaveBeenCalled()
  })

  it("requires the note's hands for correct-posture takes", () => {
    const readAudio = vi.fn(() => audioFrame(523.25))
    expect(collectReprocessFrame(sample({ note_label: "DO" }), handFeatures(1), readAudio)).toBeNull()
    expect(readAudio).not.toHaveBeenCalled()
    expect(collectReprocessFrame(sample({ note_label: "DO" }), handFeatures(2), readAudio)).not.toBeNull()
    expect(collectReprocessFrame(sample({ note_label: "DO", posture_label: "incorrecta" }), handFeatures(1), readAudio))
      .not.toBeNull()
  })

  it("drops silent frames only for flute takes and builds the v1/v5 frame", () => {
    expect(collectReprocessFrame(sample(), handFeatures(1), () => audioFrame(null))).toBeNull()
    expect(collectReprocessFrame(sample({ sound_label: "voz" }), handFeatures(1), () => audioFrame(null)))
      .toEqual({ visual_schema: FLUTE_VISUAL_SCHEMA, visual_features: handFeatures(1),
        audio_schema: FLUTE_AUDIO_SCHEMA, audio_features: audioFrame(null) })
  })
})

describe("finalizeReprocessTake (shared single/batch gate + save)", () => {
  it("rejects a take whose pitch is not the labeled note and never saves (labels kept)", async () => {
    const save = vi.fn()
    const frames = [...Array<FluteFeatures>(7).fill(featureFrame(880)), featureFrame(784)]
    const result = await finalizeReprocessTake(sample(), frames, save)
    expect(result).toEqual({ ok: false, kind: "rejected",
      reason: "La altura detectada no corresponde a la nota SOL (coincidencia 13%). Repetí la toma.",
      pitch: { agreement: 0.125, voicedFrames: 8, rejected: true } })
    expect(save).not.toHaveBeenCalled()
  })

  it("rejects too few frames without saving", async () => {
    const save = vi.fn()
    const result = await finalizeReprocessTake(sample({ sound_label: "voz", note_label: null }), [featureFrame(null)], save)
    expect(result).toMatchObject({ ok: false, kind: "rejected",
      reason: "No se detectaron suficientes articulaciones." })
    expect(save).not.toHaveBeenCalled()
  })

  it("saves gated frames keeping participant, note, sound and posture labels", async () => {
    const save = vi.fn<SaveFluteLabels>(async () => ({ message: "Etiquetas guardadas" }))
    const frames = [featureFrame(784), featureFrame(null), featureFrame(784), featureFrame(784)]
    const result = await finalizeReprocessTake(sample({ id: "s-1" }), frames, save)
    expect(result).toEqual({ ok: true, message: "Etiquetas guardadas",
      pitch: { agreement: 1, voicedFrames: 3, rejected: false } })
    expect(save).toHaveBeenCalledTimes(1)
    const [id, payload] = save.mock.calls[0]
    expect(id).toBe("s-1")
    expect(payload.feature_frames).toHaveLength(3)
    expect(payload).toMatchObject({ participant_id: "P1", note_label: "SOL", sound_label: "flauta",
      posture_label: "correcta", audio_schema: FLUTE_AUDIO_SCHEMA, visual_schema: FLUTE_VISUAL_SCHEMA })
  })

  it("reports a backend error as an error (not a rejection)", async () => {
    const save = vi.fn(async () => { throw new Error("No se pudo guardar la muestra") })
    const frames = [featureFrame(784), featureFrame(784), featureFrame(784)]
    expect(await finalizeReprocessTake(sample(), frames, save)).toMatchObject({ ok: false, kind: "error",
      reason: "No se pudo guardar la muestra" })
  })

  it("announces the save right before sending it", async () => {
    const order: string[] = []
    const save = vi.fn<SaveFluteLabels>(() => { order.push("save"); return Promise.resolve({ statuscode: 200, message: "ok", data: null } as never) })
    await finalizeReprocessTake(sample(), Array.from({ length: 4 }, () => featureFrame(783.99)), save, undefined, () => order.push("saving"))
    expect(order).toEqual(["saving", "save"])
  })

  it("never saves once the item was stopped", async () => {
    const save = vi.fn()
    const controller = new AbortController()
    controller.abort()
    const frames = [featureFrame(784), featureFrame(784), featureFrame(784)]
    expect(await finalizeReprocessTake(sample(), frames, save, controller.signal))
      .toMatchObject({ ok: false, kind: "cancelled", reason: REPROCESS_STOPPED_REASON })
    expect(save).not.toHaveBeenCalled()
  })
})
