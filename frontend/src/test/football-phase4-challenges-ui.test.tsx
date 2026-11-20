import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { ChallengeHud } from "@/features/football-validation"

describe("Football Validation Phase 4 — ChallengeHud UI", () => {
  it("renders large dynamic challenge order, countdown, approximate touch counter, and supervision banner", () => {
    render(
      <ChallengeHud
        activeCommand={{
          indice: 1,
          tipo: "HIGH",
          inicio_servidor_ms: 8000,
          duracion_ms: 9000,
        }}
        remainingSeconds={7}
        approximateTouchCount={14}
        isSupervised={true}
        totalSegments={5}
      />
    )

    expect(screen.getByTestId("supervision-banner")).toBeInTheDocument()
    expect(screen.getByText(/Supervisión Antifraude Activa/i)).toBeInTheDocument()
    expect(screen.getByTestId("challenge-command-title")).toHaveTextContent(
      "TOQUES ALTOS"
    )
    expect(screen.getByTestId("challenge-countdown")).toHaveTextContent("7s")
    expect(screen.getByTestId("live-touch-counter")).toHaveTextContent("14")
    expect(screen.getByText(/Tramo 2\/5 • HIGH/i)).toBeInTheDocument()
  })
})
