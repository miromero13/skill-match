import "@testing-library/jest-dom/vitest"
import { act, render, screen } from "@testing-library/react"
import { beforeEach, expect, it } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { MemberRouteGuard } from "@/components/member-route-guard"
import { AdminRouteGuard } from "@/components/admin-route-guard"
import { useAuthStore } from "@/stores/auth-store"
import { onAuthRehydrate } from "@/stores/auth-hydration"

beforeEach(async () => { await useAuthStore.persist.rehydrate() })

it("does not redirect or expose member content while native persistence is hydrating", () => {
  useAuthStore.getState().login({ id: "member", email: "member@example.com", fullName: "Member", role: "MEMBER", skillPointsBalance: 0, reputationScore: 0, trustLevel: 0, isVerified: false }, "access", "refresh")
  const finish = onAuthRehydrate()
  render(<MemoryRouter><MemberRouteGuard><p>Private member content</p></MemberRouteGuard></MemoryRouter>)
  expect(screen.queryByText("Private member content")).not.toBeInTheDocument()
  expect(screen.getByRole("status")).toHaveTextContent("Cargando sesión")
  act(() => finish(useAuthStore.getState()))
  expect(screen.getByText("Private member content")).toBeInTheDocument()
})

it("does not expose administrator content before hydration, or after a storage error", () => {
  useAuthStore.getState().login({ id: "admin", email: "admin@example.com", fullName: "Admin", role: "ADMIN", skillPointsBalance: 0, reputationScore: 0, trustLevel: 0, isVerified: false }, "access", "refresh")
  const finish = onAuthRehydrate()
  render(<MemoryRouter><AdminRouteGuard><p>Private admin content</p></AdminRouteGuard></MemoryRouter>)
  expect(screen.queryByText("Private admin content")).not.toBeInTheDocument()
  expect(screen.getByRole("status")).toHaveTextContent("Cargando sesión")
  act(() => finish(undefined, new Error("secure store unavailable")))
  expect(screen.queryByText("Private admin content")).not.toBeInTheDocument()
  expect(screen.getByText("Error 404")).toBeInTheDocument()
})
