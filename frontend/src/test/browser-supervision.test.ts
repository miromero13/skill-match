import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  AV_NOMINAL_WINDOW_MS,
  AVFailureTracker,
  BrowserMonitor,
  IncidentQueue,
  avWindowDurationMs,
  calibrateVoice,
} from "@/services/browser-supervision"
import { apiClient } from "@/services/api-client"

beforeEach(() => { localStorage.clear(); vi.useFakeTimers() })
afterEach(() => { vi.useRealTimers(); document.body.replaceChildren() })

function setup() {
  const area = document.createElement("div")
  const outside = document.createElement("div")
  document.body.append(area, outside)
  const emit = vi.fn()
  const notice = vi.fn()
  const monitor = new BrowserMonitor(area, emit, notice)
  monitor.start()
  return { area, outside, emit, notice, monitor }
}

function action(target: HTMLElement, type: string) {
  const event = new Event(type, { bubbles: true, cancelable: true })
  target.dispatchEvent(event)
  return event
}

describe("SM-43 browser controls", () => {
  it.each(["copy", "cut", "paste", "drop", "contextmenu"])("blocks %s only inside the monitored area and releases on stop", type => {
    const { area, outside, monitor, emit, notice } = setup()
    expect(action(area, type).defaultPrevented).toBe(true)
    expect(emit).toHaveBeenCalledTimes(1)
    expect(notice).toHaveBeenCalled()
    expect(action(outside, type).defaultPrevented).toBe(false)
    monitor.stop()
    expect(action(area, type).defaultPrevented).toBe(false)
    expect(emit).toHaveBeenCalledTimes(1)
  })

  it("covers keyboard clipboard shortcuts without trapping navigation", () => {
    const { area, emit, monitor } = setup()
    const key = new KeyboardEvent("keydown", { key: "v", ctrlKey: true, bubbles: true, cancelable: true })
    area.dispatchEvent(key)
    expect(key.defaultPrevented).toBe(true)
    action(area, "paste")
    expect(emit).toHaveBeenCalledTimes(1)
    const tab = new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true })
    area.dispatchEvent(tab)
    expect(tab.defaultPrevented).toBe(false)
    monitor.stop()
  })

  it("deduplicates blur plus hidden and records a single duration on return", () => {
    const { emit, monitor } = setup()
    window.dispatchEvent(new Event("blur"))
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden")
    document.dispatchEvent(new Event("visibilitychange"))
    vi.advanceTimersByTime(1200)
    expect(emit).toHaveBeenCalledTimes(1)
    expect(emit.mock.calls[0][0].kind).toBe("AWAY")
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible")
    window.dispatchEvent(new Event("focus"))
    expect(emit).toHaveBeenCalledTimes(2)
    expect(emit.mock.calls[1][0]).toMatchObject({ kind: "RETURN", duration_ms: 1200 })
    monitor.stop()
    vi.restoreAllMocks()
  })

  it("records disconnect/reconnect, page exit and an actual fullscreen exit", () => {
    const { emit, monitor } = setup()
    window.dispatchEvent(new Event("offline"))
    window.dispatchEvent(new Event("online"))
    Object.defineProperty(document, "fullscreenElement", { configurable: true, value: document.body })
    document.dispatchEvent(new Event("fullscreenchange"))
    Object.defineProperty(document, "fullscreenElement", { configurable: true, value: null })
    document.dispatchEvent(new Event("fullscreenchange"))
    window.dispatchEvent(new Event("pagehide"))
    expect(emit.mock.calls.map(call => call[0].kind)).toEqual(["OFFLINE", "ONLINE", "FULLSCREEN_EXIT", "PAGE_EXIT"])
    monitor.stop()
  })
})

describe("SM-43 durable queue", () => {
  it("preserves the same IDs on failure/reload and removes only acknowledged events", async () => {
    const send = vi.fn().mockRejectedValueOnce(new Error("offline"))
    const warning = vi.fn()
    const queue = new IncidentQueue("owner:trial", send, warning)
    queue.add({ kind: "COPY" })
    await queue.flush().catch(() => undefined)
    const original = JSON.parse(localStorage.getItem("owner:trial") ?? "[]")
    expect(original).toHaveLength(1)
    send.mockImplementation(async (events: { event_id: string }[]) => ({ accepted_ids: events.map(row => row.event_id), event_count: 1 }))
    const resumed = new IncidentQueue("owner:trial", send, warning)
    await Promise.all([resumed.flush(), resumed.flush()])
    expect(send).toHaveBeenCalledTimes(2)
    expect(send.mock.calls[1][0][0].event_id).toBe(original[0].event_id)
    expect(resumed.size).toBe(0)
    expect(localStorage.getItem("owner:trial")).toBe("[]")
  })

  it("retains events added during a request and sends bounded batches", async () => {
    let resolve: ((value: { accepted_ids: string[]; event_count: number }) => void) | undefined
    const send = vi.fn().mockImplementationOnce(() => new Promise(r => { resolve = r }))
      .mockImplementation(async (events: { event_id: string }[]) => ({ accepted_ids: events.map(row => row.event_id), event_count: 52 }))
    const queue = new IncidentQueue("owner:trial", send, vi.fn())
    for (let i = 0; i < 51; i++) queue.add({ kind: "PASTE" })
    const pending = queue.flush()
    queue.add({ kind: "COPY" })
    const first = send.mock.calls[0][0] as { event_id: string }[]
    expect(first).toHaveLength(50)
    resolve?.({ accepted_ids: first.map(row => row.event_id), event_count: 50 })
    await pending
    expect(send.mock.calls[1][0]).toHaveLength(2)
    expect(queue.size).toBe(0)
  })

  it("reserves the last slot of a full queue for a single STREAM_ERROR overflow marker and recovers after a sync", async () => {
    const warning = vi.fn()
    const sent: string[][] = []
    const queue = new IncidentQueue("owner:trial", async (events) => {
      sent.push(events.map((row) => row.kind))
      return { accepted_ids: events.map((row) => row.event_id), event_count: events.length }
    }, warning)
    for (let i = 0; i < 499; i++) expect(queue.add({ kind: "COPY" })).toBe(true)
    expect(warning).not.toHaveBeenCalled()
    expect(queue.add({ kind: "PASTE" })).toBe(false) // the 500th ordinary event does not fit
    expect(warning).toHaveBeenCalledWith(expect.stringMatching(/500 incidentes.*Reconectá/))
    expect(queue.size).toBe(500)
    expect(queue.add({ kind: "PASTE" })).toBe(false)
    expect(queue.size).toBe(500) // a single marker, not one per dropped event
    expect(JSON.parse(localStorage.getItem("owner:trial") ?? "[]").at(-1).kind).toBe("STREAM_ERROR")
    await queue.flush()
    expect(queue.size).toBe(0)
    expect(sent.flat().filter((kind) => kind === "STREAM_ERROR")).toHaveLength(1)
    expect(queue.add({ kind: "COPY" })).toBe(true) // accepting again after the sync
    for (let i = 0; i < 498; i++) queue.add({ kind: "COPY" })
    expect(queue.add({ kind: "COPY" })).toBe(false)
    expect(JSON.parse(localStorage.getItem("owner:trial") ?? "[]").filter((row: { kind: string }) => row.kind === "STREAM_ERROR")).toHaveLength(1)
  })

  it("fails visibly rather than silently dropping a full queue or accepting corrupted storage", () => {
    const warning = vi.fn()
    const queue = new IncidentQueue("owner:trial", vi.fn(), warning)
    for (let i = 0; i < 500; i++) queue.add({ kind: "COPY" })
    expect(queue.add({ kind: "COPY" })).toBe(false)
    expect(queue.size).toBe(500)
    expect(warning).toHaveBeenCalled()
    localStorage.setItem("corrupt", '{"clipboard":"must-not-be-uploaded"}')
    expect(() => new IncidentQueue("corrupt", vi.fn(), warning)).toThrow()
  })
})

describe("S8/S13 audiovisual evidence helpers", () => {
  it("reports the duration of the audio actually sent, within the server bounds", () => {
    expect(avWindowDurationMs(38_400)).toBe(2400)
    expect(avWindowDurationMs(48_000)).toBe(3000)
    expect(avWindowDurationMs(30_720)).toBe(1920)
    expect(avWindowDurationMs(100)).toBe(500)
    expect(avWindowDurationMs(1_000_000)).toBe(30_000)
    expect(avWindowDurationMs(0)).toBe(AV_NOMINAL_WINDOW_MS)
  })

  it("flags a failure streak once and starts over after a success", () => {
    const tracker = new AVFailureTracker(2)
    expect(tracker.failure()).toBe(false)
    expect(tracker.failure()).toBe(true)
    expect(tracker.failure()).toBe(false)
    expect(tracker.consecutive).toBe(3)
    tracker.success()
    expect(tracker.consecutive).toBe(0)
    expect(tracker.failure()).toBe(false)
    expect(tracker.failure()).toBe(true)
  })

  it.each([
    "STREAM_ERROR",
    "MODEL_UNAVAILABLE",
    "VIDEO_MISSING",
    "AUDIO_MISSING",
    "WINDOW_GAP",
    "FACE_OCCLUDED",
    "MOUTH_OCCLUDED",
    "CAMERA_BLOCKED",
  ] as const)(
    "keeps %s in the durable queue and restores it from storage",
    kind => {
      const send = vi.fn()
      const first = new IncidentQueue("kinds", send, vi.fn())
      expect(first.add({ kind })).toBe(true)
      expect(new IncidentQueue("kinds", send, vi.fn()).size).toBe(1)
    },
  )
})

describe("T8 voice calibration service", () => {
  it("posts the recording with the tab id and returns the server message", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({
      statuscode: 200,
      message: "Voz calibrada.",
      data: { voice_enrolled: true, voiced_seconds: 4.2 },
    } as never)
    const request = {
      audio_samples: [0.1],
      ambient_ms: 2000,
      mouth_samples: [{ t_ms: 10, mouth_open: 0.2 }],
      frames: [{ t_ms: 0, image: "data:image/jpeg;base64,AAAA" }],
    }
    const outcome = await calibrateVoice("trial-1", "tab-1", request)
    expect(post).toHaveBeenCalledWith(
      "/browser-supervision/trials/trial-1/voice-calibration",
      { tab_id: "tab-1", ...request },
      { showToastOnError: false },
    )
    expect(outcome).toEqual({ result: { voice_enrolled: true, voiced_seconds: 4.2 }, message: "Voz calibrada." })
    post.mockRestore()
  })
})
