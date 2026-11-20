import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { JugglingVideoAnalyzer } from "@/features/football-validation"
import {
  footballValidationApi,
  type JugglingVideoAnalysis,
} from "@/features/football-validation/api/football-validation-api"
import { ApiError } from "@/types/api"

const ANALYSIS: JugglingVideoAnalysis = {
  analysis_complete: true,
  ball_detected: true,
  detector: "mediapipe-efficientdet-lite0+classical",
  frames_analyzed: 900,
  ball_frames: 640,
  duration_seconds: 30.0,
  total_touches: 23,
  max_streak: 14,
  streaks: [6, 14, 3],
  ground_contacts: 2,
  score_1_100: 41.0,
  level: "Intermedio",
  level_probabilities: {
    Principiante: 0.2,
    Intermedio: 0.6,
    Avanzado: 0.15,
    Experto: 0.05,
  },
  confidence: 0.6,
  model_version: "rule-based-v1",
  notes: ["Se usó el detector clásico como respaldo."],
  feedback: {
    fortalezas: ["Buen control con el empeine."],
    mejoras: ["Mantener el balón más cerca del cuerpo."],
  },
}

function makeVideo(): File {
  return new File([new Uint8Array([0, 1, 2, 3])], "dominadas.mp4", {
    type: "video/mp4",
  })
}

describe("JugglingVideoAnalyzer", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it("renders the upload card with a disabled analyze button until a video is chosen", async () => {
    const user = userEvent.setup()
    render(<JugglingVideoAnalyzer />)

    expect(screen.getByText("Analizar un video grabado")).toBeInTheDocument()
    const input = screen.getByLabelText(/Video grabado/i)
    expect(input).toHaveAttribute(
      "accept",
      "video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov"
    )
    const analyzeBtn = screen.getByRole("button", { name: /Analizar video/i })
    expect(analyzeBtn).toBeDisabled()

    await user.upload(input, makeVideo())
    expect(analyzeBtn).toBeEnabled()
    expect(screen.getByText(/dominadas\.mp4/)).toBeInTheDocument()
  })

  it("on success renders level, score, best streak and notes as a non-destructive alert", async () => {
    const user = userEvent.setup()
    let resolveRequest: (value: {
      statuscode: number
      message: string
      data: JugglingVideoAnalysis
    }) => void = () => {}
    const spy = vi
      .spyOn(footballValidationApi, "analyzeJugglingVideo")
      .mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveRequest = resolve
          })
      )

    render(<JugglingVideoAnalyzer />)
    const file = makeVideo()
    await user.upload(screen.getByLabelText(/Video grabado/i), file)
    await user.click(screen.getByRole("button", { name: /Analizar video/i }))

    expect(spy).toHaveBeenCalledWith(file)
    expect(
      await screen.findByText("Analizando video… puede tardar unos minutos")
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Analizando/i })).toBeDisabled()

    resolveRequest({
      statuscode: 200,
      message: "Análisis de video completado.",
      data: ANALYSIS,
    })

    expect(await screen.findByTestId("juggling-level-badge")).toHaveTextContent(
      "Intermedio"
    )
    expect(screen.getByTestId("juggling-score")).toHaveTextContent("41")
    expect(screen.getByTestId("juggling-score")).toHaveTextContent("/100")
    expect(screen.getByText("Mejor racha")).toBeInTheDocument()
    expect(screen.getByTestId("juggling-max-streak")).toHaveTextContent("14")
    expect(screen.getByTestId("juggling-total-touches")).toHaveTextContent("23")
    expect(screen.getByTestId("juggling-ground-contacts")).toHaveTextContent(
      "2"
    )
    expect(screen.getByText("Buen control con el empeine.")).toBeInTheDocument()
    expect(
      screen.getByText("Mantener el balón más cerca del cuerpo.")
    ).toBeInTheDocument()
    expect(screen.getByText(/rule-based-v1/)).toBeInTheDocument()

    const notesAlert = screen.getByTestId("juggling-notes-alert")
    expect(notesAlert).toHaveTextContent(
      "Se usó el detector clásico como respaldo."
    )
    expect(notesAlert).not.toHaveClass("text-destructive")
  })

  it("on request failure shows a retry warning without any grade and keeps the file", async () => {
    const user = userEvent.setup()
    const spy = vi
      .spyOn(footballValidationApi, "analyzeJugglingVideo")
      .mockRejectedValueOnce(new ApiError("Failed to fetch", 0))
      .mockResolvedValueOnce({
        statuscode: 200,
        message: "Análisis de video completado.",
        data: ANALYSIS,
      })

    render(<JugglingVideoAnalyzer />)
    const file = makeVideo()
    await user.upload(screen.getByLabelText(/Video grabado/i), file)
    await user.click(screen.getByRole("button", { name: /Analizar video/i }))

    const warning = await screen.findByTestId("juggling-request-warning")
    expect(warning).toHaveTextContent(
      "No se pudo conectar con el servidor para analizar el video."
    )
    expect(warning).not.toHaveClass("text-destructive")
    expect(screen.queryByTestId("juggling-score")).not.toBeInTheDocument()
    expect(screen.queryByTestId("juggling-level-badge")).not.toBeInTheDocument()
    expect(screen.getByText(/dominadas\.mp4/)).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /Reintentar/i }))
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2))
    expect(spy).toHaveBeenLastCalledWith(file)
    expect(await screen.findByTestId("juggling-level-badge")).toHaveTextContent(
      "Intermedio"
    )
    expect(
      screen.queryByTestId("juggling-request-warning")
    ).not.toBeInTheDocument()
  })

  it("shows the backend APIResponse message when the server answered with an error", async () => {
    const user = userEvent.setup()
    vi.spyOn(footballValidationApi, "analyzeJugglingVideo").mockRejectedValueOnce(
      new ApiError("Recurso no encontrado", 404)
    )

    render(<JugglingVideoAnalyzer />)
    await user.upload(screen.getByLabelText(/Video grabado/i), makeVideo())
    await user.click(screen.getByRole("button", { name: /Analizar video/i }))

    expect(
      await screen.findByTestId("juggling-request-warning")
    ).toHaveTextContent("Recurso no encontrado")
    expect(screen.getByRole("button", { name: /Reintentar/i })).toBeEnabled()
    expect(screen.queryByTestId("juggling-score")).not.toBeInTheDocument()
  })
})
