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
    render(<FootballTrainingStudio />)

    expect(
      screen.getByText(/Estudio de Entrenamiento de IA/i)
    ).toBeInTheDocument()
    expect(screen.getByText("Garage S3 + ONNX")).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getAllByText("100.0%").length).toBeGreaterThan(0)
    })

    expect(screen.getAllByText("Exact Accuracy").length).toBeGreaterThan(0)
    expect(screen.getByText("Línea Base (Reglas)")).toBeInTheDocument()
    expect(screen.getByText("Matriz de Confusión (Filas: Real / Columnas: Predicción)")).toBeInTheDocument()
    expect(screen.getByText("1.0.0-onnx")).toBeInTheDocument()
  })

  it("triggers synthetic dataset generation when user clicks button", async () => {
    const user = userEvent.setup()
    const genSpy = vi
      .spyOn(footballValidationApi, "generateSyntheticDataset")
      .mockResolvedValue({
        statuscode: 201,
        message: "Generated",
        data: {
          generated_count: 12,
          splits_summary: { train: 8, val: 2, test: 2 },
          levels_summary: { Principiante: 3, Intermedio: 3, Avanzado: 3, Experto: 3 },
          samples: [],
        },
      })

    render(<FootballTrainingStudio />)

    const genBtn = screen.getByRole("button", {
      name: /Generar Muestras y Guardar en S3/i,
    })
    await user.click(genBtn)

    await waitFor(() => {
      expect(genSpy).toHaveBeenCalledWith({
        count: 12,
        train_ratio: 0.7,
        val_ratio: 0.15,
      })
    })

    expect(screen.getByText(/\+12 clips/i)).toBeInTheDocument()
  })

  it("triggers training and refreshes models catalog", async () => {
    const user = userEvent.setup()
    const trainSpy = vi
      .spyOn(footballValidationApi, "trainLevelModel")
      .mockResolvedValue({
        statuscode: 200,
        message: "Trained",
        data: {
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
        },
      })

    render(<FootballTrainingStudio />)

    const trainBtn = screen.getByRole("button", {
      name: /Entrenar y Evaluar Modelo/i,
    })
    await user.click(trainBtn)

    await waitFor(() => {
      expect(trainSpy).toHaveBeenCalled()
    })

    expect(
      screen.getByText(/¡Entrenamiento exitoso! Modelo versión 2.0.0-onnx/i)
    ).toBeInTheDocument()
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

    render(<FootballTrainingStudio />)

    await waitFor(() => {
      expect(screen.getByText("1.1.0-onnx")).toBeInTheDocument()
    })

    const activateBtn = screen.getByRole("button", { name: /Activar como Único/i })
    await user.click(activateBtn)

    await waitFor(() => {
      expect(activateSpy).toHaveBeenCalledWith("mod-2")
    })
  })
})
