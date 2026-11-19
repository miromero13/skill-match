import { describe, expect, it } from "vitest"
import { WINDOW_LIMITS, WindowBuffer } from "@/hooks/av-window-buffer"

const chunk = (count: number, value: number) => new Array<number>(count).fill(value)

describe("WindowBuffer", () => {
  it("keeps only the newest frames within the server limit", () => {
    const buffer = new WindowBuffer()
    for (let index = 0; index < 40; index++) buffer.addFrame(`f${index}`, 1000 + index * 400)
    const taken = buffer.take()
    expect(taken.frames).toHaveLength(WINDOW_LIMITS.frames)
    expect(taken.frames.at(-1)?.image).toBe("f39")
    expect(taken.frames[0].image).toBe("f28")
  })

  it("keeps only the newest audio within the server limit and moves the window start with it", () => {
    const buffer = new WindowBuffer()
    buffer.addAudio(chunk(16_000 * 8, 0.1), 8_000)
    buffer.addAudio(chunk(16_000 * 8, 0.9), 16_000)
    const taken = buffer.take()
    expect(taken.audio).toHaveLength(WINDOW_LIMITS.audioSamples)
    expect(taken.audio.every((value) => value === 0.9 || value === 0.1)).toBe(true)
    expect(taken.audio.at(-1)).toBe(0.9)
    expect(taken.audio[0]).toBe(0.1) // the newest 10 s: the last 2 s of the first chunk and all of the second
    expect(taken.audio.filter((value) => value === 0.1)).toHaveLength(16_000 * 2)
    expect(taken.audioStartedAt).toBe(6_000)
  })

  it("empties itself on take and reports no audio start without audio", () => {
    const buffer = new WindowBuffer()
    buffer.addFrame("a", 1)
    buffer.addAudio(chunk(1600, 0.2), 1000)
    expect(buffer.take().audioStartedAt).toBe(900)
    const again = buffer.take()
    expect(again.frames).toEqual([])
    expect(again.audio).toEqual([])
    expect(again.audioStartedAt).toBeNull()
  })

  it("clear() drops everything collected so far", () => {
    const buffer = new WindowBuffer()
    buffer.addFrame("a", 1)
    buffer.addAudio(chunk(10, 0.2), 1000)
    buffer.clear()
    expect(buffer.take().frames).toEqual([])
  })
})
