import { act, render } from "@testing-library/react"
import { expect, it, vi } from "vitest"

const connect = vi.fn().mockResolvedValue(true)
const disconnect = vi.fn()

vi.mock("@/stores/realtime-notification-store", () => ({
  useRealtimeNotificationStore: (selector: (state: unknown) => unknown) =>
    selector({ connect, disconnect }),
}))

it("mounts one realtime lifecycle for the application shell", async () => {
  const { RealtimeNotificationBridge } =
    await import("@/components/notifications/realtime-notification-bridge")

  const view = render(<RealtimeNotificationBridge />)
  await act(async () => undefined)

  expect(connect).toHaveBeenCalledTimes(1)
  view.rerender(<RealtimeNotificationBridge />)
  expect(connect).toHaveBeenCalledTimes(1)
  view.unmount()
  expect(disconnect).toHaveBeenCalledTimes(1)
})
