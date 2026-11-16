import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { FootballResultView } from "@/features/football-validation"

describe("Football Validation Phases 5 & 6 — FootballResultView UI", () => {
  it("renders verified level, animated seal, metrics, and template feedback when clean", () => {
    render(
      <FootballResultView
        result={{
          session_id: "sess-clean-1",
          estado: "scored",
          nivel: "Avanzado",
          probabilidades: {
            Principiante: 0.02,
            Intermedio: 0.14,
            Avanzado: 0.78,
            Experto: 0.06,
          },
          confianza: 0.78,
          metricas: {
            toques: 38,
            racha: 32,
            toques_por_minuto: 57.0,
            altura_media: 1.85,
            regularidad: 0.88,
            cumplimiento_por_tramo: [],
          },
          coherencia_audio_video: 0.94,
          puntaje_riesgo: 0,
          incidencias: [],
          retroalimentacion: {
            fortalezas: [
              "Excelente continuidad de dominio con una racha máxima de 32 toques seguidos.",
            ],
            mejoras: [
              "Incrementa la velocidad en los tramos rápidos manteniendo la altura por debajo de 1,5 diámetros.",
            ],
          },
          requiere_revision: false,
          version_modelo: "rules-v1",
          version_config: "0.1.0-phase0:a1b2c3d4e5f6",
        }}
      />
    )

    expect(screen.getByTestId("verified-skill-seal")).toBeInTheDocument()
    expect(screen.getByTestId("validated-level-title")).toHaveTextContent(
      "Nivel: Avanzado"
    )
    expect(screen.getByTestId("metric-total-touches")).toHaveTextContent("38")
    expect(screen.getByTestId("metric-max-streak")).toHaveTextContent("32")
    expect(
      screen.getByText(/Excelente continuidad de dominio/i)
    ).toBeInTheDocument()
  })

  it("renders review badge, fraud incidents alert, and manual review action when flagged", async () => {
    const onReview = vi.fn()
    const user = userEvent.setup()

    render(
      <FootballResultView
        result={{
          session_id: "sess-flagged-1",
          estado: "needs_review",
          nivel: "Intermedio",
          probabilidades: {
            Principiante: 0.25,
            Intermedio: 0.52,
            Avanzado: 0.18,
            Experto: 0.05,
          },
          confianza: 0.52,
          metricas: {
            toques: 14,
            racha: 10,
            toques_por_minuto: 32.0,
            altura_media: 2.1,
            regularidad: 0.62,
            cumplimiento_por_tramo: [],
          },
          coherencia_audio_video: 0.35,
          puntaje_riesgo: 65,
          incidencias: [
            {
              tipo: "low_av_coherence",
              severidad: "high",
              t_ms: 0,
              detalle: "Coherencia audio-video baja (0.35 < 0.65).",
            },
          ],
          retroalimentacion: {
            fortalezas: ["Buen control sostenido."],
            mejoras: ["Evita ruido de fondo."],
          },
          requiere_revision: true,
          version_modelo: "rules-v1",
          version_config: "0.1.0-phase0:a1b2c3d4e5f6",
        }}
        onRequestManualReview={onReview}
      />
    )

    expect(screen.getByTestId("needs-review-badge")).toBeInTheDocument()
    expect(screen.getByTestId("fraud-incidents-alert")).toBeInTheDocument()
    const reviewBtn = screen.getByTestId("request-review-button")
    await user.click(reviewBtn)
    expect(onReview).toHaveBeenCalledWith("sess-flagged-1")
  })
})
