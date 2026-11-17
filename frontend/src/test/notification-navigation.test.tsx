import { render, screen, waitFor } from "@testing-library/react"
import { beforeEach, expect, it, vi } from "vitest"
import { createMemoryRouter, RouterProvider } from "react-router-dom"
import { router as applicationRouter } from "@/routes"
import { useAuthStore, type UserProfile } from "@/stores/auth-store"
import { useNotificationStore } from "@/stores/notification-store"
import * as service from "@/services/notification-service"
import { TooltipProvider } from "@/components/ui/tooltip"

vi.mock("@/services/notification-service")
const user: UserProfile = {
  id: "A",
  fullName: "Usuario",
  email: "a@example.invalid",
  role: "MEMBER",
  skillPointsBalance: 0,
  reputationScore: 0,
  trustLevel: 0,
  isVerified: false,
}
beforeEach(() => {
  vi.resetAllMocks()
  useAuthStore.getState().logout()
  useNotificationStore.getState().reset()
  vi.mocked(service.getNotifications).mockResolvedValue({
    statuscode: 200,
    message: "Listado",
    data: [],
    count: 0,
  })
  vi.mocked(service.getUnreadCount).mockResolvedValue(7)
  vi.mocked(service.getNotificationPreferences).mockResolvedValue({
    statuscode: 200,
    message: "Preferencias",
    data: {
      revision: 0,
      channels: { in_app: true, push: false, email: false },
      categories: { INTERCHANGES: true, POINTS: true, GENERAL: true },
    },
  })
})
function open(path: string) {
  // Use the application's actual routes, shells and guards, replacing only login content.
  const routes = applicationRouter.routes.filter(
    (route) => route.path !== "/login"
  )
  const router = createMemoryRouter(
    [
      ...routes,
      {
        id: "test-login",
        path: "/login",
        element: <p>Autenticación requerida</p>,
      },
    ],
    { initialEntries: [path] }
  )
  render(
    <TooltipProvider>
      <RouterProvider router={router} />
    </TooltipProvider>
  )
  return router
}
it.each(["MEMBER", "ADMIN"] as const)(
  "opens the personal inbox and bell in the %s shell",
  async (role) => {
    useAuthStore.getState().login({ ...user, role }, "token")
    const router = open("/app/notifications")
    expect(
      await screen.findByRole("heading", { name: "Bandeja de notificaciones" })
    ).toBeInTheDocument()
    expect(
      await screen.findByRole("button", { name: "Notificaciones, 7 no leídas" })
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe("/notifications")
    if (role === "ADMIN")
      expect(screen.getByText("SkillMatch Admin")).toBeInTheDocument()
    else
      expect(screen.getByRole("link", { name: "Avisos" })).toHaveAttribute(
        "href",
        "/notifications"
      )
  }
)
it.each(["MEMBER", "ADMIN"] as const)(
  "opens canonical personal settings for %s",
  async (role) => {
    useAuthStore.getState().login({ ...user, role }, "token")
    const router = open("/app/notifications/settings")
    expect(
      await screen.findByRole("heading", {
        name: "Preferencias de notificaciones",
      })
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe("/notifications/settings")
    expect(
      await screen.findByRole("switch", { name: "Push" })
    ).not.toBeChecked()
  }
)
it("redirects anonymous personal access to login preserving its destination", async () => {
  const router = open("/notifications/settings")
  expect(await screen.findByText("Autenticación requerida")).toBeInTheDocument()
  expect(router.state.location.state.from.pathname).toBe(
    "/notifications/settings"
  )
  expect(service.getNotifications).not.toHaveBeenCalled()
  expect(service.getNotificationPreferences).not.toHaveBeenCalled()
})
it("retains administrative 404 obfuscation for a member", async () => {
  useAuthStore.getState().login(user, "token")
  open("/admin/catalog")
  expect(await screen.findByText("Error 404")).toBeInTheDocument()
  expect(service.getNotifications).not.toHaveBeenCalled()
})
it("still redirects administrators away from member-only pages", async () => {
  useAuthStore.getState().login({ ...user, role: "ADMIN" }, "token")
  const router = createMemoryRouter(
    [
      ...applicationRouter.routes.filter((route) => route.path === "/app"),
      { path: "/admin/dashboard", element: <p>Dashboard administrativo</p> },
    ],
    { initialEntries: ["/app/notifications-unknown"] }
  )
  // Use an existing member route so it goes through the actual member guard.
  await router.navigate("/app/profile")
  render(<RouterProvider router={router} />)
  await waitFor(() =>
    expect(router.state.location.pathname).toBe("/admin/dashboard")
  )
  expect(screen.getByText("Dashboard administrativo")).toBeInTheDocument()
})
