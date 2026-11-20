import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { FootballTrainingStudio } from "@/features/football-validation"
import { footballValidationApi } from "@/features/football-validation/api/football-validation-api"

describe("FootballTrainingStudio UI Component", () => {
  const mockModels = [
    {
      id: "mod-1",
      nombre: "level_classifier",
      version: "1.0.0-onnx",
      ruta_onnx: "s3://skillmatch-football/models/football/level_classifier_v1.onnx",
      activa: true,
      metricas: {
        test_samples: 16,
        train_participants: 20,
        test_participants: 8,
        rule_baseline_accuracy: 0.875,
        trained_exact_accuracy: 1.0,
        trained_within_one_level_accuracy: 1.0,
        beats_rule_baseline: true,
        confusion_matrix: [
          [4, 0, 0, 0],
          [0, 4, 0, 0],
          [0, 0, 4, 0],
          [0, 0, 0, 4],
        ],
        loss_history: [
          { epoch: 0, loss: 1.386 },
          { epoch: 300, loss: 0.245 },
          { epoch: 699, loss: 0.082 },
        ],
      },
      created_at: "2026-11-16T00:00:00Z",
    },
    {
      id: "mod-2",
      nombre: "level_classifier",
      version: "1.1.0-onnx",
      ruta_onnx: "s3://skillmatch-football/models/football/level_classifier_v2.onnx",
      activa: false,
      metricas: {
        test_samples: 16,
        train_participants: 20,
        test_participants: 8,
        rule_baseline_accuracy: 0.875,
        trained_exact_accuracy: 0.9375,
        trained_within_one_level_accuracy: 1.0,
        beats_rule_baseline: true,
        confusion_matrix: [
          [4, 0, 0, 0],
          [0, 3, 1, 0],
          [0, 0, 4, 0],
          [0, 0, 0, 4],
        ],
        loss_history: [],
      },
      created_at: "2026-11-16T00:05:00Z",
    },
  ]

  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(footballValidationApi, "listModelVersions").mockResolvedValue({
      statuscode: 200,
      message: "Success",
      data: mockModels,
      count: mockModels.length,
    })
  })

  it("renders studio header, metrics cards, and confusion matrix for active model", async () => {
    render(<FootballTrainingStudio skillId="skill-fb-1" skillName="Dominadas y Control de Balón" />)

    expect(
      screen.getByText(/Entrenamiento de IA/i)
    ).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getAllByText("100.0%").length).toBeGreaterThan(0)
    })

    expect(screen.getAllByText("Exact Accuracy").length).toBeGreaterThan(0)
    expect(screen.getByText("Línea Base (Reglas)")).toBeInTheDocument()
    expect(screen.getByText("Matriz de Confusión (Filas: Real / Columnas: Predicción)")).toBeInTheDocument()
    expect(screen.getAllByText("1.0.0-onnx").length).toBeGreaterThan(0)
  })

  it("disables training button when no skill is selected", async () => {
    render(<FootballTrainingStudio />)

    expect(screen.getByText("Seleccioná una habilidad para entrenar")).toBeInTheDocument()

    const trainBtn = screen.getByRole("button", {
      name: /Entrenar Modelo/i,
    })
    expect(trainBtn).toBeDisabled()
  })

  const DONE_RESULT = {
    id: "mod-3",
    nombre: "level_classifier",
    version: "2.0.0-onnx",
    ruta_onnx: "s3://skillmatch-football/models/football/level_classifier_v3.onnx",
    activa: true,
    metricas: {
      test_samples: 16,
      train_participants: 20,
      test_participants: 8,
      rule_baseline_accuracy: 0.875,
      trained_exact_accuracy: 1.0,
      trained_within_one_level_accuracy: 1.0,
      beats_rule_baseline: true,
      confusion_matrix: [],
      loss_history: [],
    },
    created_at: "2026-11-16T00:10:00Z",
  }

  it("triggers training with 100% real data and refreshes models catalog", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({
      advanceTimers: (ms) => vi.advanceTimersByTime(ms),
    })
    const enqueueSpy = vi
      .spyOn(footballValidationApi, "enqueueTraining")
      .mockResolvedValue({
        statuscode: 202,
        message: "Entrenamiento encolado.",
        data: { task_id: "task-abc" },
      })
    const statusSpy = vi
      .spyOn(footballValidationApi, "getTrainingStatus")
      .mockResolvedValueOnce({
        statuscode: 200,
        message: "Estado del entrenamiento recuperado.",
        data: { status: "running", processed: 1, total: 4, message: "Extrayendo features de muestra 1/4", result: null },
      })
      .mockResolvedValueOnce({
        statuscode: 200,
        message: "Estado del entrenamiento recuperado.",
        data: { status: "done", processed: null, total: null, message: null, result: DONE_RESULT },
      })

    render(<FootballTrainingStudio skillId="skill-fb-1" />)

    const trainBtn = screen.getByRole("button", {
      name: /Entrenar Modelo/i,
    })
    await user.click(trainBtn)

    expect(enqueueSpy).toHaveBeenCalledWith({
      activate: true,
      skill_id: "skill-fb-1",
      version_tag: undefined,
    })

    await vi.advanceTimersByTimeAsync(1500)
    await vi.advanceTimersByTimeAsync(0)
    expect(statusSpy).toHaveBeenCalledTimes(1)
    expect(screen.getByText(/Muestra 1\/4/i)).toBeInTheDocument()

    await vi.advanceTimersByTimeAsync(1500)
    await vi.advanceTimersByTimeAsync(0)
    expect(statusSpy).toHaveBeenCalledTimes(2)

    expect(screen.getByText(/Modelo 2\.0\.0-onnx entrenado/i)).toBeInTheDocument()
    vi.useRealTimers()
  })

  it("shows the backend error message when a queued training fails", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({
      advanceTimers: (ms) => vi.advanceTimersByTime(ms),
    })
    vi.spyOn(footballValidationApi, "enqueueTraining").mockResolvedValue({
      statuscode: 202,
      message: "Entrenamiento encolado.",
      data: { task_id: "task-fail" },
    })
    vi.spyOn(footballValidationApi, "getTrainingStatus").mockResolvedValue({
      statuscode: 200,
      message: "Estado del entrenamiento recuperado.",
      data: {
        status: "failed",
        processed: null,
        total: null,
        message: "No se encontraron muestras reales de fútbol para entrenar.",
        result: null,
      },
    })

    render(<FootballTrainingStudio skillId="skill-fb-1" />)
    await user.click(screen.getByRole("button", { name: /Entrenar Modelo/i }))

    await vi.advanceTimersByTimeAsync(1500)
    await waitFor(() => {
      expect(
        screen.getByText(/No se encontraron muestras reales de fútbol/i)
      ).toBeInTheDocument()
    })
    vi.useRealTimers()
  })

  it("shows the real dataset samples that would train the model on preview", async () => {
    const user = userEvent.setup()
    const previewSpy = vi
      .spyOn(footballValidationApi, "getDatasetPreview")
      .mockResolvedValue({
        statuscode: 200,
        message: "Success",
        data: {
          samples: [
            {
              id: "sample-1",
              participant_id: "REAL-01",
              level_label: "Avanzado",
              split: "train",
              is_synthetic: false,
              manual_touch_count: 42,
              created_at: "2026-11-16T00:00:00Z",
            },
            {
              id: "sample-2",
              participant_id: "SYN-P-001-C00",
              level_label: "Experto",
              split: "train",
              is_synthetic: true,
              manual_touch_count: 80,
              created_at: "2026-11-16T00:00:00Z",
            },
          ],
          total_count: 2,
          real_count: 1,
          synthetic_count: 1,
        },
      })

    render(<FootballTrainingStudio skillId="skill-fb-1" />)

    const previewBtn = screen.getByRole("button", {
      name: /Ver muestras a usar/i,
    })
    await user.click(previewBtn)

    await waitFor(() => {
      expect(previewSpy).toHaveBeenCalled()
    })

    expect(await screen.findByText("REAL-01")).toBeInTheDocument()
    expect(screen.queryByText("SYN-P-001-C00")).not.toBeInTheDocument()
    expect(screen.getByText("1 reales")).toBeInTheDocument()
  })

  it("activates an inactive model version when clicking activate button", async () => {
    const user = userEvent.setup()
    const activateSpy = vi
      .spyOn(footballValidationApi, "activateModelVersion")
      .mockResolvedValue({
        statuscode: 200,
        message: "Activated",
        data: {
          id: "mod-2",
          nombre: "level_classifier",
          version: "1.1.0-onnx",
          activa: true,
        },
      })

    render(<FootballTrainingStudio skillId="skill-fb-1" />)

    await waitFor(() => {
      expect(screen.getByText("1.1.0-onnx")).toBeInTheDocument()
    })

    const activateBtn = screen.getByRole("button", { name: /^Activar$/i })
    await user.click(activateBtn)

    await waitFor(() => {
      expect(activateSpy).toHaveBeenCalledWith("mod-2")
    })
  })
})
