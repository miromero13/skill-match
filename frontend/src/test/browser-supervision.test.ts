import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { BrowserMonitor, IncidentQueue } from "@/services/browser-supervision"

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
