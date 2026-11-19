import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { PlatformHeader } from "@/components/navigation/platform-header"
import { useAuthStore } from "@/stores/auth-store"
import { TooltipProvider } from "@/components/ui/tooltip"

describe("PlatformHeader responsive layout", () => {
  beforeEach(() => {
    useAuthStore.getState().login(
      {
        id: "test-user-1",
        fullName: "Ilse Romero",
        email: "ilse@example.com",
        role: "MEMBER",
        skillPointsBalance: 250,
        reputationScore: 95,
        trustLevel: 2,
        isVerified: true,
      },
      "fake-token",
      "fake-refresh"
    )
  })

  it("renders wallet balance without overlapping classes", () => {
    render(
      <MemoryRouter initialEntries={["/app"]}>
        <TooltipProvider>
          <PlatformHeader />
        </TooltipProvider>
      </MemoryRouter>
    )

    // Check brand
    expect(screen.getByText("SM")).toBeInTheDocument()

    // Check wallet points
    expect(screen.getByText("250 SP")).toBeInTheDocument()

    // Check wallet link
    const walletLink = screen.getByRole("link", { name: /250 SP/i })
    expect(walletLink).toHaveAttribute("href", "/app/wallet")
    expect(walletLink.className).toContain("shrink-0")

    // Check navigation items are rendered
    const navElement = screen.getByRole("navigation")
    expect(navElement).toBeInTheDocument()
    expect(navElement.className).toContain("flex-1")
    expect(navElement.className).not.toContain("w-2/4")
  })
})
