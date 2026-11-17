import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { toast } from "sonner"
import type { UserProfile } from "@/stores/auth-store"

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }))

const member: UserProfile = {
  id: "11111111-1111-4111-8111-111111111111",
  email: "member@example.invalid",
  fullName: "Member",
  role: "MEMBER",
  skillPointsBalance: 0,
  reputationScore: 0,
  trustLevel: 0,
  isVerified: false,
}

const event = {
  event: "notification.created" as const,
  message: "Mensaje exacto del backend",
  data: {
    id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    type: "MATCH_RECEIVED" as const,
    category: "INTERCHANGES" as const,
    title: "Nuevo match",
    message: "Mensaje exacto del backend",
    created_at: "2026-11-16T20:00:00Z",
    read_at: null,
  },
}

class MockWebSocket {
  static instances: MockWebSocket[] = []
  static OPEN = 1
  readonly url: string
  readyState = 0
  sent: string[] = []
  close = vi.fn(() => {
    this.readyState = 3
    this.onclose?.(new CloseEvent("close"))
  })
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  send(payload: string) {
    this.sent.push(payload)
  }

  open() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.(new Event("open"))
  }

  message(payload: unknown) {
    this.onmessage?.(
      new MessageEvent("message", { data: JSON.stringify(payload) })
    )
  }

  fail() {
    this.onerror?.(new Event("error"))
    this.onclose?.(new CloseEvent("close"))
  }
}

const ticketResponse = {
  statuscode: 200,
  message: "Ticket WebSocket generado exitosamente.",
  data: {
    ticket: "ticket-1",
    expires_in: 30,
    websocket_path: "/ws/notifications" as const,
  },
}

async function loadRuntime(profile: UserProfile = member) {
  const { useAuthStore } = await import("@/stores/auth-store")
  const { useNotificationStore } = await import("@/stores/notification-store")
  useAuthStore.getState().login(profile, "access", "refresh")
  useNotificationStore.getState().reset()
  const { useRealtimeNotificationStore } =
    await import("@/stores/realtime-notification-store")
  return { useAuthStore, useNotificationStore, useRealtimeNotificationStore }
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.resetModules()
  vi.clearAllMocks()
  MockWebSocket.instances = []
  vi.stubGlobal("WebSocket", MockWebSocket)
  Object.defineProperty(navigator, "onLine", {
    configurable: true,
    value: true,
  })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe("realtime notification service contract", () => {
  it("builds ws and wss URLs without putting the access token in the URL", async () => {
    const service = await import("@/services/realtime-notification-service")
    expect(
      service.buildWebSocketUrl(
        "http://localhost:8000/api",
        ticketResponse.data
      )
    ).toBe("ws://localhost:8000/ws/notifications?ticket=ticket-1")
    expect(
      service.buildWebSocketUrl(
        "https://skillmatch.test/api",
        ticketResponse.data
      )
    ).toBe("wss://skillmatch.test/ws/notifications?ticket=ticket-1")
    expect(
      service.buildWebSocketUrl(
        "https://skillmatch.test/api",
        ticketResponse.data
      )
    ).not.toContain("access")
  })

  it("rejects unsafe protocols and malformed ticket responses", async () => {
    const service = await import("@/services/realtime-notification-service")
    expect(() =>
      service.buildWebSocketUrl("ftp://skillmatch.test", ticketResponse.data)
    ).toThrow()
    expect(() =>
      service.buildWebSocketUrl("https://skillmatch.test/api", {
        ...ticketResponse.data,
        ticket: "",
      })
    ).toThrow()
  })
})

describe("realtime Zustand lifecycle", () => {
  it("requests a ticket before opening one socket for the current session", async () => {
    vi.doMock("@/services/realtime-notification-service", () => ({
      getWebSocketTicket: vi.fn().mockResolvedValue(ticketResponse),
      buildWebSocketUrl: vi
        .fn()
        .mockReturnValue("ws://localhost/ws/notifications?ticket=ticket-1"),
    }))
    const { useRealtimeNotificationStore: store } = await loadRuntime()
    await store.getState().connect()
    expect(MockWebSocket.instances).toHaveLength(1)
    expect(store.getState().status).toBe("connecting")
    MockWebSocket.instances[0].open()
    expect(store.getState().status).toBe("connected")
    await store.getState().connect()
    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it("uses the same personal realtime channel for an authenticated admin", async () => {
    vi.doMock("@/services/realtime-notification-service", () => ({
      getWebSocketTicket: vi.fn().mockResolvedValue(ticketResponse),
      buildWebSocketUrl: vi
        .fn()
        .mockReturnValue("ws://localhost/ws/notifications?ticket=ticket-1"),
    }))
    const { useRealtimeNotificationStore: store } = await loadRuntime({
      ...member,
      role: "ADMIN",
    })

    await store.getState().connect()
    MockWebSocket.instances[0].open()

    expect(store.getState().status).toBe("connected")
    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it("shows the exact server message once and reconciles HU-25", async () => {
    vi.doMock("@/services/realtime-notification-service", () => ({
      getWebSocketTicket: vi.fn().mockResolvedValue(ticketResponse),
      buildWebSocketUrl: vi
        .fn()
        .mockReturnValue("ws://localhost/ws/notifications?ticket=ticket-1"),
    }))
    const { useNotificationStore, useRealtimeNotificationStore: store } =
      await loadRuntime()
    const unread = vi.spyOn(useNotificationStore.getState(), "loadUnread")
    const list = vi.spyOn(useNotificationStore.getState(), "loadList")
    await store.getState().connect()
    MockWebSocket.instances[0].open()
    MockWebSocket.instances[0].message(event)
    MockWebSocket.instances[0].message(event)
    expect(toast.success).toHaveBeenCalledTimes(1)
    expect(toast.success).toHaveBeenCalledWith(event.message)
    expect(unread).toHaveBeenCalled()
    expect(list).toHaveBeenCalled()
    expect(useNotificationStore.getState().realtimeRevision).toBe(2)
  })

  it("ignores malformed, unknown and message-mismatched payloads", async () => {
    vi.doMock("@/services/realtime-notification-service", () => ({
      getWebSocketTicket: vi.fn().mockResolvedValue(ticketResponse),
      buildWebSocketUrl: vi
        .fn()
        .mockReturnValue("ws://localhost/ws/notifications?ticket=ticket-1"),
    }))
    const { useRealtimeNotificationStore: store } = await loadRuntime()
    await store.getState().connect()
    const socket = MockWebSocket.instances[0]
    socket.open()
    socket.onmessage?.(new MessageEvent("message", { data: "not-json" }))
    socket.message({ event: "unknown", message: "No", data: {} })
    socket.message({ ...event, message: "Texto diferente" })
    expect(toast.success).not.toHaveBeenCalled()
    expect(store.getState().status).toBe("connected")
  })

  it("uses exponential backoff and obtains a fresh ticket per attempt", async () => {
    const getWebSocketTicket = vi
      .fn()
      .mockResolvedValueOnce(ticketResponse)
      .mockResolvedValueOnce({
        ...ticketResponse,
        data: { ...ticketResponse.data, ticket: "ticket-2" },
      })
    vi.doMock("@/services/realtime-notification-service", () => ({
      getWebSocketTicket,
      buildWebSocketUrl: vi.fn(
        (_: string, data: { ticket: string }) =>
          `ws://localhost/ws/notifications?ticket=${data.ticket}`
      ),
    }))
    const { useRealtimeNotificationStore: store } = await loadRuntime()
    vi.spyOn(Math, "random").mockReturnValue(0)
    await store.getState().connect()
    MockWebSocket.instances[0].fail()
    expect(store.getState().status).toBe("reconnecting")
    await vi.advanceTimersByTimeAsync(999)
    expect(MockWebSocket.instances).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(MockWebSocket.instances).toHaveLength(2)
    expect(getWebSocketTicket).toHaveBeenCalledTimes(2)
    expect(MockWebSocket.instances[1].url).toContain("ticket-2")
  })

  it("does not reconnect while offline and resumes on the online event", async () => {
    vi.doMock("@/services/realtime-notification-service", () => ({
      getWebSocketTicket: vi.fn().mockResolvedValue(ticketResponse),
      buildWebSocketUrl: vi
        .fn()
        .mockReturnValue("ws://localhost/ws/notifications?ticket=ticket-1"),
    }))
    const { useRealtimeNotificationStore: store } = await loadRuntime()
    await store.getState().connect()
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: false,
    })
    MockWebSocket.instances[0].fail()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(MockWebSocket.instances).toHaveLength(1)
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: true,
    })
    window.dispatchEvent(new Event("online"))
    await vi.runOnlyPendingTimersAsync()
    expect(MockWebSocket.instances).toHaveLength(2)
  })

  it("recovers a disconnected authenticated session when the tab is visible", async () => {
    vi.doMock("@/services/realtime-notification-service", () => ({
      getWebSocketTicket: vi.fn().mockResolvedValue(ticketResponse),
      buildWebSocketUrl: vi
        .fn()
        .mockReturnValue("ws://localhost/ws/notifications?ticket=ticket-1"),
    }))
    const { useRealtimeNotificationStore: store } = await loadRuntime()
    await store.getState().connect()
    MockWebSocket.instances[0].fail()
    store.getState().disconnect()
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    })

    document.dispatchEvent(new Event("visibilitychange"))
    await vi.advanceTimersByTimeAsync(0)

    expect(MockWebSocket.instances).toHaveLength(2)
  })

  it("closes and clears timers and private state on logout", async () => {
    vi.doMock("@/services/realtime-notification-service", () => ({
      getWebSocketTicket: vi.fn().mockResolvedValue(ticketResponse),
      buildWebSocketUrl: vi
        .fn()
        .mockReturnValue("ws://localhost/ws/notifications?ticket=ticket-1"),
    }))
    const { useAuthStore, useRealtimeNotificationStore: store } =
      await loadRuntime()
    await store.getState().connect()
    const socket = MockWebSocket.instances[0]
    socket.open()
    socket.message(event)
    useAuthStore.getState().logout()
    expect(socket.close).toHaveBeenCalled()
    expect(store.getState()).toMatchObject({ status: "idle", attempt: 0 })
    await vi.advanceTimersByTimeAsync(60_000)
    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it("reconnects with a fresh ticket after token renewal", async () => {
    const getWebSocketTicket = vi
      .fn()
      .mockResolvedValueOnce(ticketResponse)
      .mockResolvedValueOnce({
        ...ticketResponse,
        data: { ...ticketResponse.data, ticket: "ticket-renewed" },
      })
    vi.doMock("@/services/realtime-notification-service", () => ({
      getWebSocketTicket,
      buildWebSocketUrl: vi.fn(
        (_: string, data: { ticket: string }) =>
          `ws://localhost/ws/notifications?ticket=${data.ticket}`
      ),
    }))
    const { useAuthStore, useRealtimeNotificationStore: store } =
      await loadRuntime()
    await store.getState().connect()
    const firstSocket = MockWebSocket.instances[0]
    firstSocket.open()

    useAuthStore.getState().setTokens("access-renewed", "refresh-renewed")
    await vi.advanceTimersByTimeAsync(0)

    expect(firstSocket.close).toHaveBeenCalled()
    expect(getWebSocketTicket).toHaveBeenCalledTimes(2)
    expect(MockWebSocket.instances).toHaveLength(2)
    expect(MockWebSocket.instances[1].url).toContain("ticket-renewed")
  })

  it("closes the previous session socket when the authenticated user changes", async () => {
    vi.doMock("@/services/realtime-notification-service", () => ({
      getWebSocketTicket: vi.fn().mockResolvedValue(ticketResponse),
      buildWebSocketUrl: vi
        .fn()
        .mockReturnValue("ws://localhost/ws/notifications?ticket=ticket-1"),
    }))
    const { useAuthStore, useRealtimeNotificationStore: store } =
      await loadRuntime()
    await store.getState().connect()
    const firstSocket = MockWebSocket.instances[0]
    firstSocket.open()

    useAuthStore
      .getState()
      .login(
        { ...member, id: "22222222-2222-4222-8222-222222222222" },
        "other-access",
        "other-refresh"
      )
    await vi.advanceTimersByTimeAsync(0)

    expect(firstSocket.close).toHaveBeenCalled()
    expect(MockWebSocket.instances).toHaveLength(2)
  })
})

describe("notification WebSocket hook", () => {
  it("connects once on mount and disconnects on unmount", async () => {
    const connect = vi.fn().mockResolvedValue(undefined)
    const disconnect = vi.fn()
    vi.doMock("@/stores/realtime-notification-store", () => ({
      useRealtimeNotificationStore: Object.assign(
        (
          selector: (state: {
            connect: typeof connect
            disconnect: typeof disconnect
          }) => unknown
        ) => selector({ connect, disconnect }),
        { getState: () => ({ connect, disconnect }) }
      ),
    }))
    const { useNotificationWebSocket } =
      await import("@/hooks/use-notification-websocket")
    const { unmount } = renderHook(() => useNotificationWebSocket())
    await act(async () => undefined)
    expect(connect).toHaveBeenCalledTimes(1)
    unmount()
    expect(disconnect).toHaveBeenCalledTimes(1)
  })
})
