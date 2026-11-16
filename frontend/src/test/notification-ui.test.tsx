import {
  act,
  render,
  screen,
  waitFor,
  within,
  fireEvent,
} from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, expect, it, vi } from "vitest"
import { createMemoryRouter, RouterProvider } from "react-router-dom"
import { NotificationInboxPage } from "@/pages/notifications/notification-inbox-page"
import { NotificationSettingsPage } from "@/pages/notifications/notification-settings-page"
import { NotificationBell } from "@/components/notifications/notification-bell"
import { useAuthStore, type UserProfile } from "@/stores/auth-store"
import { useNotificationStore as store } from "@/stores/notification-store"
import * as service from "@/services/notification-service"
import { ApiError } from "@/types/api"
import type {
  NotificationItem,
  NotificationPreferences,
} from "@/types/notification"

vi.mock("@/services/notification-service")
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
const user: UserProfile = {
  id: "A",
  email: "a@example.invalid",
  fullName: "A",
  role: "MEMBER",
  skillPointsBalance: 0,
  reputationScore: 0,
  trustLevel: 0,
  isVerified: false,
}
const item: NotificationItem = {
  id: "one",
  type: "POINTS_RECEIVED",
  category: "POINTS",
  title: "Puntos recibidos",
  message: '<script>alert("test")</script>',
  created_at: "2026-11-16T00:00:00Z",
  read_at: null,
}
const prefs = (): NotificationPreferences => ({
  revision: 0,
  channels: { in_app: true, push: false, email: false },
  categories: { INTERCHANGES: true, POINTS: true, GENERAL: true },
})
const response = <T,>(data: T) => ({
  statuscode: 200,
  message: "Mensaje del servidor",
  data,
})
function renderPage(path = "/notifications") {
  const router = createMemoryRouter(
    [
      { path: "/notifications", element: <NotificationInboxPage /> },
      {
        path: "/notifications/settings",
        element: <NotificationSettingsPage />,
      },
    ],
    { initialEntries: [path] }
  )
  render(<RouterProvider router={router} />)
  return router
}
beforeEach(() => {
  vi.resetAllMocks()
  useAuthStore.getState().login(user, "token")
  store.getState().reset()
  vi.mocked(service.getNotifications).mockResolvedValue({
    ...response([item]),
    count: 25,
  })
  vi.mocked(service.getUnreadCount).mockResolvedValue(9)
  vi.mocked(service.getNotificationPreferences).mockImplementation(async () =>
    response(prefs())
  )
  vi.mocked(service.markNotificationRead).mockResolvedValue(
    response({ ...item, read_at: "2026-11-16T01:00:00Z" })
  )
  vi.mocked(service.markAllNotificationsRead).mockResolvedValue(response(null))
  vi.mocked(service.deleteNotification).mockResolvedValue(response(null))
})

it("filters and paginates using server queries, rendering messages as text", async () => {
  const actor = userEvent.setup()
  renderPage()
  expect(await screen.findByText(item.message)).toBeInTheDocument()
  expect(document.querySelector("script")).toBeNull()
  expect(screen.getByText("No leída")).toBeInTheDocument()
  await actor.click(screen.getByRole("button", { name: "Siguiente" }))
  await waitFor(() =>
    expect(service.getNotifications).toHaveBeenLastCalledWith({}, 2, 20)
  )
  await actor.click(screen.getByRole("tab", { name: "Puntos" }))
  await waitFor(() =>
    expect(service.getNotifications).toHaveBeenLastCalledWith(
      { category: "POINTS" },
      1,
      20
    )
  )
  await actor.click(screen.getByRole("tab", { name: "No leídas" }))
  await waitFor(() =>
    expect(service.getNotifications).toHaveBeenLastCalledWith(
      { unread: true },
      1,
      20
    )
  )
})
it("marks one and all read and requires confirmation to delete", async () => {
  const actor = userEvent.setup()
  store.setState({ unreadTotal: 9 })
  renderPage()
  await actor.click(
    await screen.findByRole("button", {
      name: `Marcar como leída: ${item.title}`,
    })
  )
  await waitFor(() =>
    expect(service.markNotificationRead).toHaveBeenCalledWith(item.id)
  )
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Marcar todas como leídas" })
    ).toBeEnabled()
  )
  await actor.click(
    screen.getByRole("button", { name: "Marcar todas como leídas" })
  )
  await waitFor(() =>
    expect(service.markAllNotificationsRead).toHaveBeenCalledOnce()
  )
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: `Eliminar: ${item.title}` })
    ).toBeEnabled()
  )
  await actor.click(
    screen.getByRole("button", { name: `Eliminar: ${item.title}` })
  )
  expect(service.deleteNotification).not.toHaveBeenCalled()
  await actor.click(screen.getByRole("button", { name: "Cancelar" }))
  expect(service.deleteNotification).not.toHaveBeenCalled()
  await actor.click(
    screen.getByRole("button", { name: `Eliminar: ${item.title}` })
  )
  await actor.click(
    screen.getByRole("button", { name: "Eliminar notificación" })
  )
  await waitFor(() =>
    expect(service.deleteNotification).toHaveBeenCalledWith(item.id)
  )
  await waitFor(() =>
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
  )
  expect(screen.getByRole("heading", { level: 1 })).toHaveFocus()
})
it("shows the backend error, retries and handles an empty filter", async () => {
  vi.mocked(service.getNotifications).mockRejectedValueOnce(
    new ApiError("Servicio temporalmente no disponible", 503)
  )
  renderPage()
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Servicio temporalmente no disponible"
  )
  vi.mocked(service.getNotifications).mockResolvedValue({
    ...response([]),
    count: 0,
  })
  await userEvent.click(screen.getByRole("button", { name: "Reintentar" }))
  expect(
    await screen.findByText("No hay notificaciones para este filtro.")
  ).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled()
})
it("opens a preview independent of the current inbox filter and closes with Escape", async () => {
  const actor = userEvent.setup()
  store.getState().setFilters({ category: "POINTS" })
  const router = createMemoryRouter([
    { path: "*", element: <NotificationBell /> },
  ])
  render(<RouterProvider router={router} />)
  const bell = await screen.findByRole("button", {
    name: "Notificaciones, 9 no leídas",
  })
  await actor.click(bell)
  expect(await screen.findByText(item.title)).toBeInTheDocument()
  expect(service.getNotifications).toHaveBeenCalledWith({}, 1, 5)
  expect(store.getState().filters).toEqual({ category: "POINTS" })
  expect(screen.getByRole("link", { name: "Preferencias" })).toHaveAttribute(
    "href",
    "/notifications/settings"
  )
  await actor.keyboard("{Escape}")
  await waitFor(() =>
    expect(screen.queryByText(item.title)).not.toBeInTheDocument()
  )
  expect(bell).toHaveFocus()
  fireEvent(window, new Event("focus"))
  await waitFor(() => expect(service.getUnreadCount).toHaveBeenCalledTimes(3))
})
it("edits every preference, saves the complete revision and restores server values on reopen", async () => {
  const actor = userEvent.setup()
  let saved = prefs()
  vi.mocked(service.getNotificationPreferences).mockImplementation(async () =>
    response(saved)
  )
  vi.mocked(service.updateNotificationPreferences).mockImplementation(
    async (value) => {
      saved = { ...value, revision: 1 }
      return response(saved)
    }
  )
  const router = renderPage("/notifications/settings")
  expect(
    await screen.findByRole("switch", { name: "En la aplicación" })
  ).toBeChecked()
  await actor.click(screen.getByRole("switch", { name: "Push" }))
  await actor.click(screen.getByRole("switch", { name: "Puntos" }))
  await actor.click(
    screen.getByRole("button", { name: "Guardar preferencias" })
  )
  await waitFor(() =>
    expect(service.updateNotificationPreferences).toHaveBeenCalledWith({
      revision: 0,
      channels: { in_app: true, push: true, email: false },
      categories: { INTERCHANGES: true, POINTS: false, GENERAL: true },
    })
  )
  await screen.findByText("Configuración sincronizada.")
  await act(async () => {
    await router.navigate("/notifications")
    await router.navigate("/notifications/settings")
  })
  expect(await screen.findByRole("switch", { name: "Push" })).toBeChecked()
  expect(screen.getByRole("switch", { name: "Puntos" })).not.toBeChecked()
})
it("keeps the draft on 409 and confirms before replacing it with the latest revision", async () => {
  const actor = userEvent.setup()
  vi.mocked(service.updateNotificationPreferences).mockRejectedValue(
    new ApiError(
      "Las preferencias cambiaron. Recarga la configuración antes de guardar.",
      409
    )
  )
  renderPage("/notifications/settings")
  await actor.click(await screen.findByRole("switch", { name: "Push" }))
  await actor.click(
    screen.getByRole("button", { name: "Guardar preferencias" })
  )
  expect(
    await screen.findByText(
      "Las preferencias cambiaron. Recarga la configuración antes de guardar."
    )
  ).toBeInTheDocument()
  expect(screen.getByRole("switch", { name: "Push" })).toBeChecked()
  expect(
    screen.getByRole("button", { name: "Guardar preferencias" })
  ).toBeDisabled()
  vi.mocked(service.getNotificationPreferences).mockResolvedValue(
    response({ ...prefs(), revision: 2 })
  )
  await actor.click(
    screen.getByRole("button", { name: "Descartar y recargar" })
  )
  await actor.click(
    within(screen.getByRole("alertdialog")).getByRole("button", {
      name: "Recargar configuración",
    })
  )
  await waitFor(() =>
    expect(screen.getByRole("switch", { name: "Push" })).not.toBeChecked()
  )
  expect(store.getState().draft?.revision).toBe(2)
})
it("protects dirty drafts on focus and warns before leaving", async () => {
  const actor = userEvent.setup()
  const router = renderPage("/notifications/settings")
  await actor.click(await screen.findByRole("switch", { name: "Push" }))
  vi.mocked(service.getNotificationPreferences).mockResolvedValue(
    response({ ...prefs(), revision: 2 })
  )
  await act(async () => {
    fireEvent(window, new Event("focus"))
  })
  expect(screen.getByRole("switch", { name: "Push" })).toBeChecked()
  await actor.click(screen.getByRole("link", { name: "Volver a la bandeja" }))
  expect(await screen.findByRole("alertdialog")).toHaveTextContent(
    "¿Salir sin guardar?"
  )
  await actor.click(screen.getByRole("button", { name: "Seguir editando" }))
  expect(router.state.location.pathname).toBe("/notifications/settings")
  await actor.click(screen.getByRole("link", { name: "Volver a la bandeja" }))
  await actor.click(screen.getByRole("button", { name: "Salir y descartar" }))
  await waitFor(() =>
    expect(router.state.location.pathname).toBe("/notifications")
  )
  expect(store.getState().dirty).toBe(false)
})

it("retries initial preference loading and prevents duplicate saves while pending", async () => {
  vi.mocked(service.getNotificationPreferences).mockRejectedValueOnce(
    new ApiError("No se pudo recuperar la configuración", 503)
  )
  const actor = userEvent.setup()
  renderPage("/notifications/settings")
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "No se pudo recuperar la configuración"
  )
  await actor.click(screen.getByRole("button", { name: "Reintentar" }))
  await actor.click(
    await screen.findByRole("switch", { name: "Correo electrónico" })
  )
  let finish!: (
    value: ReturnType<typeof response<NotificationPreferences>>
  ) => void
  vi.mocked(service.updateNotificationPreferences).mockReturnValue(
    new Promise((resolve) => {
      finish = resolve
    })
  )
  await actor.click(
    screen.getByRole("button", { name: "Guardar preferencias" })
  )
  expect(
    screen.getByRole("button", { name: "Guardar preferencias" })
  ).toBeDisabled()
  expect(screen.getByRole("switch", { name: "Push" })).toBeDisabled()
  await actor.click(
    screen.getByRole("button", { name: "Guardar preferencias" })
  )
  expect(service.updateNotificationPreferences).toHaveBeenCalledOnce()
  await act(async () => {
    finish(
      response({
        ...prefs(),
        revision: 1,
        channels: { in_app: true, push: false, email: true },
      })
    )
  })
  expect(
    await screen.findByText("Configuración sincronizada.")
  ).toBeInTheDocument()
})

it("discards an open preview from a previous account, including a late result", async () => {
  const actor = userEvent.setup()
  let finish!: (
    value: Awaited<ReturnType<typeof service.getNotifications>>
  ) => void
  vi.mocked(service.getNotifications).mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve
    })
  )
  const router = createMemoryRouter([
    { path: "*", element: <NotificationBell /> },
  ])
  render(<RouterProvider router={router} />)
  await actor.click(
    await screen.findByRole("button", { name: "Notificaciones, 9 no leídas" })
  )
  expect(screen.getByText("Cargando avisos…")).toBeInTheDocument()
  vi.mocked(service.getNotifications).mockResolvedValue({
    ...response([{ ...item, id: "B", title: "Aviso de B" }]),
    count: 1,
  })
  await act(async () => {
    useAuthStore.getState().login({ ...user, id: "B" }, "tokenB")
  })
  expect(await screen.findByText("Aviso de B")).toBeInTheDocument()
  await act(async () => {
    finish({ ...response([item]), count: 1 })
  })
  expect(screen.queryByText(item.title)).not.toBeInTheDocument()
})
