import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { createMemoryRouter, RouterProvider } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"

import { NotificationSettingsPage } from "@/pages/notifications/notification-settings-page"
import * as notificationService from "@/services/notification-service"
import * as webPushService from "@/services/web-push-service"
import { useAuthStore, type UserProfile } from "@/stores/auth-store"
import { useNotificationStore } from "@/stores/notification-store"

vi.mock("@/services/notification-service")
vi.mock("@/services/web-push-service")

const member: UserProfile = {
  id: "member-one",
  email: "member@example.invalid",
  fullName: "Member One",
  role: "MEMBER",
  skillPointsBalance: 0,
  reputationScore: 0,
  trustLevel: 0,
  isVerified: true,
}

function renderSettings() {
  const router = createMemoryRouter(
    [{ path: "/notifications/settings", element: <NotificationSettingsPage /> }],
    { initialEntries: ["/notifications/settings"] }
  )
  render(<RouterProvider router={router} />)
}

beforeEach(() => {
  vi.resetAllMocks()
  useAuthStore.getState().login(member, "token")
  useNotificationStore.getState().reset()
  vi.mocked(notificationService.getNotificationPreferences).mockResolvedValue({
    statuscode: 200,
    message: "Preferencias recuperadas",
    data: {
      revision: 1,
      channels: { in_app: true, push: true, email: true },
      categories: { INTERCHANGES: true, POINTS: true, GENERAL: true },
    },
  })
  vi.mocked(webPushService.getWebPushCapability).mockResolvedValue({
    status: "AVAILABLE",
    permission: "default",
    subscriptionId: null,
  })
  vi.mocked(webPushService.requestWebPushSubscription).mockResolvedValue({
    status: "SUBSCRIBED",
    permission: "granted",
    subscriptionId: "subscription-one",
  })
})

it("does not request browser permission while rendering settings", async () => {
  renderSettings()
  expect(await screen.findByText("Preferencias de notificaciones")).toBeInTheDocument()
  expect(webPushService.getWebPushCapability).toHaveBeenCalledOnce()
  expect(webPushService.requestWebPushSubscription).not.toHaveBeenCalled()
})

it("activates Web Push only from an explicit device action", async () => {
  const actor = userEvent.setup()
  renderSettings()
  await actor.click(
    await screen.findByRole("button", {
      name: "Activar notificaciones en este dispositivo",
    })
  )
  expect(webPushService.requestWebPushSubscription).toHaveBeenCalledOnce()
  expect(await screen.findByText("Activo en este dispositivo")).toBeInTheDocument()
})

it("explains denied permission without repeatedly prompting", async () => {
  vi.mocked(webPushService.getWebPushCapability).mockResolvedValue({
    status: "DENIED",
    permission: "denied",
    subscriptionId: null,
  })
  renderSettings()
  expect(
    await screen.findByText(/habilita las notificaciones desde la configuración del navegador/i)
  ).toBeInTheDocument()
  await waitFor(() =>
    expect(webPushService.requestWebPushSubscription).not.toHaveBeenCalled()
  )
})
