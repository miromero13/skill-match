import { describe, it, expect } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { CompatibilityBadge } from "@/components/matches/compatibility-badge"
import type { MatchCompatibility } from "@/types/match"

const mockCompatibility: MatchCompatibility = {
    match_id: "match-123",
    counterpart_id: "user-bruno",
    counterpart_name: "Bruno Músico",
    compatibility_score: 96,
    factors: {
        skill_affinity: {
            score: 100,
            weight: 40,
            weighted_score: 40.0,
            description: "Reciprocidad simétrica exacta en habilidades",
        },
        schedule_overlap: {
            score: 90,
            weight: 25,
            weighted_score: 22.5,
            description: "Horarios coincidentes en Sábado y Domingo",
        },
        modality_location: {
            score: 100,
            weight: 20,
            weighted_score: 20.0,
            description: "Modalidad virtual compartida",
        },
        reputation_verification: {
            score: 90,
            weight: 15,
            weighted_score: 13.5,
            description: "Sello de verificación IA activo",
        },
    },
    match_reasons: [
        "Intercambio recíproco directo (1 habilidad(es) ofrecida(s) y 1 aprendida(s))",
        "Ambos disponibles fines de semana",
        "Habilidad evaluada y verificada por IA de SkillMatch",
    ],
}

describe("CompatibilityBadge (HU-22 / RF-MAT-04, RF-MAT-06)", () => {
    it("renders the compatibility percentage correctly", () => {
        render(
            <CompatibilityBadge
                initialScore={96}
                compatibility={mockCompatibility}
            />
        )

        const badge = screen.getByTestId("compatibility-badge")
        expect(badge).toBeDefined()
        expect(badge.textContent).toContain("96% Match")
    })

    it("displays the detailed factors and reasons in the popover when clicked", async () => {
        render(
            <CompatibilityBadge
                initialScore={96}
                compatibility={mockCompatibility}
            />
        )

        const badge = screen.getByTestId("compatibility-badge")
        fireEvent.click(badge)

        await waitFor(() => {
            expect(screen.getByTestId("compatibility-popover")).toBeDefined()
        })

        // Comprueba título y contraparte
        expect(screen.getByText("Afinidad de Intercambio")).toBeDefined()
        expect(screen.getByText(/Bruno Músico/i)).toBeDefined()

        // Comprueba los 4 factores ponderados
        expect(screen.getByText(/Habilidades \(40%\)/i)).toBeDefined()
        expect(screen.getByText(/Disponibilidad \(25%\)/i)).toBeDefined()
        expect(screen.getByText(/Modalidad y Zona \(20%\)/i)).toBeDefined()
        expect(screen.getByText(/Verificación IA \(15%\)/i)).toBeDefined()

        // Comprueba descripciones del backend
        expect(screen.getByText("Reciprocidad simétrica exacta en habilidades")).toBeDefined()
        expect(screen.getByText("Horarios coincidentes en Sábado y Domingo")).toBeDefined()

        // Comprueba razones explicativas (RF-MAT-06)
        expect(screen.getByText("Ambos disponibles fines de semana")).toBeDefined()
        expect(screen.getByText("Habilidad evaluada y verificada por IA de SkillMatch")).toBeDefined()
    })

    it("applies the emerald badge variant for high scores >= 80", () => {
        render(
            <CompatibilityBadge
                initialScore={85}
                compatibility={mockCompatibility}
            />
        )

        const badge = screen.getByTestId("compatibility-badge")
        expect(badge.className).toContain("bg-emerald-500/10")
    })
})
