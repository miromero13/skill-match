import { act, cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { FluteHandOverlay } from "@/components/admin/flute/flute-hand-overlay"

const tracker = vi.hoisted(() => ({ detect: vi.fn(), close: vi.fn(), create: vi.fn(), files: vi.fn() }))
vi.mock("@mediapipe/tasks-vision", () => ({
  HandLandmarker: { createFromOptions: tracker.create },
  FilesetResolver: { forVisionTasks: tracker.files },
}))

beforeEach(() => {
  vi.useFakeTimers()
  vi.clearAllMocks()
  tracker.files.mockResolvedValue({})
  tracker.create.mockResolvedValue({ detectForVideo: tracker.detect, close: tracker.close })
  tracker.detect.mockReturnValue({
    landmarks: [Array.from({ length: 21 }, (_, i) => ({
      x: 0.3 + (i % 5) * 0.05,
      y: 0.2 + Math.floor(i / 5) * 0.08,
      z: (i % 3) * 0.01,
    }))],
    handedness: [[{ categoryName: "Left", score: 0.95 }]],
  })
})
afterEach(() => { cleanup(); vi.useRealTimers() })

async function mount() {
  const video = document.createElement("video")
  Object.defineProperties(video, {
    readyState: { value: 2 }, paused: { value: false, configurable: true },
    videoWidth: { value: 1280 }, videoHeight: { value: 720 },
  })
  const onFrame = vi.fn()
  let view: ReturnType<typeof render>
  await act(async () => { view = render(<FluteHandOverlay videoRef={{ current: video }} onFrame={onFrame} />) })
  return { video, onFrame, view: view! }
}

describe("visible hand tracking", () => {
  it("draws actual returned landmarks and emits features directly without calibration", async () => {
    const { video, onFrame, view } = await mount()
    video.currentTime = 0.1
    act(() => { vi.advanceTimersByTime(100) })
    expect(view.container.querySelectorAll("polyline")).toHaveLength(6)
    expect(onFrame.mock.lastCall?.[0].features).toHaveLength(50)
    expect(onFrame.mock.lastCall?.[0].features[0]).toBe(1)
    expect(screen.getByRole("status").textContent).toContain("21 articulaciones")
    view.unmount()
    expect(tracker.close).toHaveBeenCalledOnce()
  })
  it("clears the frame instead of reusing hands when the video stops", async () => {
    const { video, onFrame } = await mount()
    video.currentTime = 0.1
    act(() => { vi.advanceTimersByTime(100) })
    Object.defineProperty(video, "paused", { value: true })
    act(() => { vi.advanceTimersByTime(100) })
    expect(onFrame).toHaveBeenLastCalledWith(null)
  })
  it("shows model loading failures without inventing detections", async () => {
    tracker.create.mockRejectedValueOnce(new Error("missing asset"))
    const { onFrame } = await mount()
    expect(screen.getByRole("status").textContent).toContain("No se pudo cargar")
    expect(tracker.detect).not.toHaveBeenCalled()
    expect(onFrame).not.toHaveBeenCalled()
  })
})
