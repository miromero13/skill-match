import { readFileSync } from "node:fs"
import process from "node:process"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { createMemoryRouter, RouterProvider } from "react-router-dom"
import { expect, it } from "vitest"
import { NotificationInboxPage } from "@/pages/notifications/notification-inbox-page"
import { NotificationSettingsPage } from "@/pages/notifications/notification-settings-page"
import { NotificationBell } from "@/components/notifications/notification-bell"
import { useAuthStore, type UserProfile } from "@/stores/auth-store"
import { useNotificationStore } from "@/stores/notification-store"
import { getNotifications } from "@/services/notification-service"

const fixturePath = process.env.HU25_TEST_FIXTURE
if (!fixturePath)
  throw new Error("HU25_TEST_FIXTURE is required for this isolated live test")
const fixture = JSON.parse(readFileSync(fixturePath, "utf8")) as {
  users: UserProfile[]
  tokens: string[]
}
function router(path = "/notifications") {
  return createMemoryRouter(
    [
      {
        path: "/notifications",
        element: (
          <>
            <NotificationBell />
            <NotificationInboxPage />
          </>
        ),
      },
      {
        path: "/notifications/settings",
        element: <NotificationSettingsPage />,
      },
    ],
    { initialEntries: [path] }
  )
}

it("runs MEMBER and ADMIN inbox/preferences through live FastAPI and PostgreSQL", async () => {
  const actor = userEvent.setup()
  useAuthStore.getState().login(fixture.users[0], fixture.tokens[0])
  useNotificationStore.getState().reset()
  const app = router()
  render(<RouterProvider router={app} />)
  expect(await screen.findByText("Aviso real 1")).toBeInTheDocument()
  expect(screen.getByText("Aviso real 2")).toBeInTheDocument()
  expect(screen.queryByText("Aviso privado B")).not.toBeInTheDocument()
  expect(
    await screen.findByRole("button", { name: "Notificaciones, 3 no leídas" })
  ).toBeInTheDocument()
  await actor.click(screen.getByRole("tab", { name: "Puntos" }))
  expect(await screen.findByText("Aviso real 2")).toBeInTheDocument()
  expect(screen.queryByText("Aviso real 1")).not.toBeInTheDocument()
  await actor.click(
    screen.getByRole("button", { name: "Marcar como leída: Aviso real 2" })
  )
  await waitFor(async () =>
    expect((await getNotifications({ unread: true }, 1, 1)).count).toBe(2)
  )
  await app.navigate("/notifications/settings")
  const push = await screen.findByRole("switch", { name: "Push" })
  await actor.click(push)
  await actor.click(screen.getByRole("switch", { name: "Puntos" }))
  await actor.click(
    screen.getByRole("button", { name: "Guardar preferencias" })
  )
  expect(
    await screen.findByText("Configuración sincronizada.")
  ).toBeInTheDocument()
  await app.navigate("/notifications")
  await app.navigate("/notifications/settings")
  expect(await screen.findByRole("switch", { name: "Push" })).toBeChecked()
  expect(screen.getByRole("switch", { name: "Puntos" })).not.toBeChecked()

  useAuthStore.getState().login(fixture.users[1], fixture.tokens[1])
  await app.navigate("/notifications")
  expect(await screen.findByText("Aviso privado B")).toBeInTheDocument()
  expect(screen.queryByText("Aviso real 1")).not.toBeInTheDocument()

  useAuthStore.getState().login(fixture.users[2], fixture.tokens[2])
  expect(
    await screen.findByText("Aviso administrativo propio")
  ).toBeInTheDocument()
  expect(screen.queryByText("Aviso privado B")).not.toBeInTheDocument()
  await actor.click(
    screen.getByRole("button", {
      name: "Eliminar: Aviso administrativo propio",
    })
  )
  await actor.click(
    within(screen.getByRole("alertdialog")).getByRole("button", {
      name: "Eliminar notificación",
    })
  )
  await waitFor(async () =>
    expect((await getNotifications({}, 1, 20)).count).toBe(0)
  )
  useAuthStore.getState().logout()
})
