import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { FluteFingerState } from "@/services/dataset-sample-service"

vi.mock("@/components/admin/flute/flute-hand-overlay", () => ({
  FluteHandOverlay: () => null,
}))

import { FluteFingerFeedback } from "@/components/admin/flute/flute-live-validator"

afterEach(() => cleanup())

const fingerStates: FluteFingerState[] = [1, 2, 3, 4, 5, 6, 7].map((hole) => ({
  hole,
  expected: hole <= 4,
  covered_probability: hole <= 3 ? 0.92 : 0.08,
  match: hole !== 4,
}))

describe("FluteFingerFeedback (S7)", () => {
  it("shows the 7 front holes split by hand, the back thumb as not evaluable and the wrong finger", () => {
    render(<FluteFingerFeedback fingerStates={fingerStates} />)
    for (const hole of [1, 2, 3, 4, 5, 6, 7]) {
      expect(screen.getByTestId(`flute-hole-${hole}`)).toBeTruthy()
    }
    expect(screen.getByText("Mano izquierda (1-3)")).toBeTruthy()
    expect(screen.getByText("Mano derecha (4-7)")).toBeTruthy()
    expect(screen.getByText(/no evaluable por cámara/)).toBeTruthy()
    expect(screen.getByText("Hueco 4 debería estar tapado").getAttribute("data-tone")).toBe("error")
    expect(screen.getByTestId("flute-hole-4").getAttribute("data-match")).toBe("false")
    expect(screen.getByTestId("flute-hole-1").getAttribute("data-match")).toBe("true")
    expect(screen.queryByText(/Hueco 1 debería/)).toBeNull()
  })

  it("shows uncertain holes as a neutral camera notice, not as an error", () => {
    const states = fingerStates.map((s) =>
      s.hole === 4 ? { ...s, covered_probability: 0.5, match: null } : s
    )
    render(<FluteFingerFeedback fingerStates={states} uncertainHoles={[4]} />)
    expect(screen.getByTestId("flute-hole-4").getAttribute("data-match")).toBe("uncertain")
    const notice = screen.getByText("Hueco 4: la cámara no lo ve con claridad")
    expect(notice.getAttribute("data-tone")).toBe("neutral")
    expect(screen.queryByText(/debería estar/)).toBeNull()
  })

  it("renders unknown holes when finger states are not available", () => {
    render(<FluteFingerFeedback fingerStates={null} reason="Faltan manos en cámara" />)
    expect(screen.getByTestId("flute-hole-7").getAttribute("data-match")).toBe("unknown")
    expect(screen.getByText("Faltan manos en cámara")).toBeTruthy()
    expect(screen.queryByText(/debería estar/)).toBeNull()
  })
})
