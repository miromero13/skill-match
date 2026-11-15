import { beforeEach, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import userEvent from "@testing-library/user-event"
import { AdminRouteGuard } from "@/components/admin-route-guard"
import { MemberRouteGuard } from "@/components/member-route-guard"
import { MobileBottomBar } from "@/components/navigation/mobile-bottom-bar"
import { ProfilePage } from "@/pages/profile-page"
import { useAuthStore, type UserProfile } from "@/stores/auth-store"
import * as teaching from "@/services/teaching-skill-service"

vi.mock("@/services/teaching-skill-service")
const member: UserProfile = {
  id: "a",
  fullName: "Miembro Prueba",
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
})

it.each(["anonymous", "MEMBER"])(
  "keeps the admin route hidden from %s",
  (role) => {
    if (role === "MEMBER") useAuthStore.getState().login(member, "token")
    render(
      <MemoryRouter>
        <AdminRouteGuard>
          <p>Private admin content</p>
        </AdminRouteGuard>
      </MemoryRouter>
    )
    expect(screen.queryByText("Private admin content")).not.toBeInTheDocument()
    expect(screen.getByText("Error 404")).toBeInTheDocument()
  }
)
it("keeps members and administrators on separate route trees", () => {
  useAuthStore.getState().login({ ...member, role: "ADMIN" }, "token")
  render(
    <MemoryRouter initialEntries={["/app/profile"]}>
      <Routes>
        <Route
          path="/app/profile"
          element={
            <MemberRouteGuard>
              <p>Member profile</p>
            </MemberRouteGuard>
          }
        />
        <Route path="/admin/dashboard" element={<p>Admin dashboard</p>} />
      </Routes>
    </MemoryRouter>
  )
  expect(screen.getByText("Admin dashboard")).toBeInTheDocument()
})

it("allows an authenticated administrator into its own route tree", () => {
  useAuthStore.getState().login({ ...member, role: "ADMIN" }, "token")
  render(
    <MemoryRouter>
      <AdminRouteGuard>
        <p>Own admin evidence page</p>
      </AdminRouteGuard>
    </MemoryRouter>
  )
  expect(screen.getByText("Own admin evidence page")).toBeInTheDocument()
})
it("offers a mobile entry to the actual profile", () => {
  render(
    <MemoryRouter>
      <MobileBottomBar />
    </MemoryRouter>
  )
  expect(screen.getByRole("link", { name: "Perfil" })).toHaveAttribute(
    "href",
    "/app/profile"
  )
})
it("renders actual identity and skill cards in the profile", async () => {
  useAuthStore.getState().login(member, "token")
  vi.mocked(teaching.getTeachingCatalog).mockResolvedValue([])
  vi.mocked(teaching.getTeachingSkills).mockResolvedValue({
    statuscode: 200,
    message: "Loaded",
    count: 1,
    data: [
      {
        id: "offer",
        skill_id: "catalog-id",
        skill_name: "Python",
        declared_level: "BEGINNER",
        years_of_experence: 1,
        description: null,
        accepts_points: false,
        hourly_points_rate: null,
        status: "DECLARADA",
      },
    ],
  })
  render(
    <MemoryRouter>
      <ProfilePage />
    </MemoryRouter>
  )
  expect(
    screen.getByRole("heading", { name: "Miembro Prueba" })
  ).toBeInTheDocument()
  expect(
    await screen.findByRole("button", { name: "Evidencias" })
  ).toBeInTheDocument()
  expect(screen.getByText("Python")).toBeInTheDocument()
})

it("explains an empty catalog and lets the member refresh after it is populated", async () => {
  const user = userEvent.setup()
  useAuthStore.getState().login(member, "token")
  vi.mocked(teaching.getTeachingSkills).mockResolvedValue({
    statuscode: 200,
    message: "Loaded",
    count: 0,
    data: [],
  })
  vi.mocked(teaching.getTeachingCatalog)
    .mockResolvedValueOnce([])
    .mockResolvedValue([{ id: "python", name: "Python" }])
  render(
    <MemoryRouter>
      <ProfilePage />
    </MemoryRouter>
  )
  await user.click(
    await screen.findByRole("button", { name: "Agregar habilidad" })
  )
  expect(
    screen.getByText(/Un administrador debe crear y activar/)
  ).toBeInTheDocument()
  expect(screen.getByRole("combobox", { name: "Habilidad" })).toBeDisabled()
  expect(
    screen.queryByRole("link", { name: "Administrar catálogo" })
  ).not.toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: "Actualizar catálogo" }))
  await vi.waitFor(() =>
    expect(screen.getByRole("combobox", { name: "Habilidad" })).toBeEnabled()
  )
  expect(teaching.getTeachingCatalog).toHaveBeenCalledTimes(2)
  await user.click(screen.getByRole("combobox", { name: "Habilidad" }))
  const option = await screen.findByRole("option", { name: "Python" })
  await user.click(option)
  expect(screen.getByRole("button", { name: "Guardar habilidad" })).toBeEnabled()
})
