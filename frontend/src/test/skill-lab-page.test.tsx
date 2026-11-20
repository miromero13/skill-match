import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { AdminSkillLabPage } from "@/pages/admin-skill-lab-page"
import { skillLabApi } from "@/features/skill-lab/api/skill-lab-api"
import type {
  SkillLabConfig,
  SkillLabModel,
  SkillLabSample,
  SkillValidationResult,
} from "@/features/skill-lab/types"
import { ApiError } from "@/types/api"

vi.mock("@/features/skill-lab/api/skill-lab-api", () => ({
  skillLabApi: {
    getMetricTypes: vi.fn(),
    getConfig: vi.fn(),
    listSamples: vi.fn(),
    uploadSample: vi.fn(),
    deleteSample: vi.fn(),
    train: vi.fn(),
    listModels: vi.fn(),
    validate: vi.fn(),
    getSamplePreviewUrl: vi.fn(),
  },
}))

const api = vi.mocked(skillLabApi)

const REFERENCE: SkillLabSample = {
  id: "ref-1",
  skill_id: "skill-1",
  skill_level_id: "lvl-1",
  criterion_key: null,
  sample_role: "REFERENCE",
  file_format: "mp4",
  file_size_bytes: 5 * 1024 * 1024,
  participant_id: null,
  analysis_ready: true,
  analysis_notes: [],
  created_at: "2026-11-19T10:00:00Z",
}

const TRAINING_SAMPLE: SkillLabSample = {
  id: "train-1",
  skill_id: "skill-1",
  skill_level_id: "lvl-1",
  criterion_key: "c-touch",
  sample_role: "TRAINING",
  file_format: "webm",
  file_size_bytes: 2 * 1024 * 1024,
  participant_id: "P-07",
  analysis_ready: true,
  analysis_notes: [],
  created_at: "2026-11-19T11:00:00Z",
}

const MODEL: SkillLabModel = {
  id: "model-2",
  skill_id: "skill-1",
  version: "v2",
  activa: true,
  metricas: {
    samples_per_level: { "lvl-1": 3, "lvl-2": 1 },
    loo_level_accuracy: 0.75,
    notes: ["Pocos videos en el nivel Intermedio."],
  },
  created_at: "2026-11-20T09:00:00Z",
}

function makeConfig(overrides: Partial<SkillLabConfig> = {}): SkillLabConfig {
  return {
    skill: {
      id: "skill-1",
      name: "Dominadas",
      category: { id: "cat-1", name: "Fútbol" },
      challenge_type: { id: "ct-1", name: "Pose en video", code: "VIDEO_POSE", evaluation_modality: "VIDEO_POSE" },
      min_approval_threshold: 80,
    },
    levels: [
      {
        id: "lvl-2",
        level_number: 2,
        name: "Intermedio",
        min_score: 75,
        weights_total: 100,
        criteria: [
          { key: "c-rep", name: "Técnica de golpeo", weight: 100, description: "", metric_type: "REFERENCE_REPLICATION", target: null, training_samples: 0, has_reference: false },
        ],
        training_samples: 0,
        reference: null,
      },
      {
        id: "lvl-1",
        level_number: 1,
        name: "Principiante",
        min_score: 60,
        weights_total: 100,
        criteria: [
          { key: "c-posture", name: "Postura corporal", weight: 60, description: "", metric_type: "REFERENCE_REPLICATION", target: null, training_samples: 2, has_reference: true },
          { key: "c-touch", name: "Toques seguidos", weight: 40, description: "", metric_type: "BALL_TOUCH_STREAK", target: 10, training_samples: 1, has_reference: false },
        ],
        training_samples: 3,
        reference: REFERENCE,
      },
    ],
    active_model: null,
    readiness: { ready_to_validate: false, issues: ["El nivel «Intermedio» no tiene video de referencia."] },
    ...overrides,
  }
}

const RESULT: SkillValidationResult = {
  skill_id: "skill-1",
  skill_name: "Dominadas",
  engine_version: "engine-1",
  model_version: "v2",
  analysis_complete: true,
  target_level_id: null,
  achieved_level: { level_id: "lvl-1", level_number: 1, name: "Principiante" },
  score: 74.5,
  min_approval_threshold: 80,
  meets_skill_threshold: false,
  approved: false,
  model_level_estimate: { level_id: "lvl-1", name: "Principiante", confidence: 0.7 },
  levels: [
    {
      level_id: "lvl-1",
      level_number: 1,
      name: "Principiante",
      min_score: 60,
      evaluable: true,
      score: 74.5,
      passed: true,
      not_evaluable_reason: null,
      criteria: [
        { key: "c-posture", name: "Postura corporal", weight: 60, metric_type: "REFERENCE_REPLICATION", evaluable: true, score: 78, detail: {}, note: null },
        { key: "c-touch", name: "Toques seguidos", weight: 40, metric_type: "BALL_TOUCH_STREAK", evaluable: true, score: 69.25, detail: {}, note: "Se contaron 7 de 10 toques." },
      ],
    },
    {
      level_id: "lvl-2",
      level_number: 2,
      name: "Intermedio",
      min_score: 75,
      evaluable: false,
      score: 0,
      passed: false,
      not_evaluable_reason: "El nivel no tiene video de referencia.",
      criteria: [
        { key: "c-rep", name: "Técnica de golpeo", weight: 100, metric_type: "REFERENCE_REPLICATION", evaluable: false, score: 0, detail: {}, note: "Falta el video de referencia." },
      ],
    },
  ],
  pose_detected_ratio: 0.93,
  duration_seconds: 21.4,
  notes: ["El ángulo de cámara difiere de la referencia."],
}

function video(name = "intento.mp4"): File {
  return new File([new Uint8Array([0, 1, 2, 3])], name, { type: "video/mp4" })
}

function renderLab(path = "/admin/skill-lab/skill-1") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/admin/skill-lab/:skillId" element={<AdminSkillLabPage />} />
        <Route path="/admin/catalog" element={<p>Catálogo</p>} />
      </Routes>
    </MemoryRouter>
  )
}

async function levelCard(levelId: string) {
  return within(await screen.findByTestId(`skill-lab-level-${levelId}`))
}

beforeEach(() => {
  vi.clearAllMocks()
  api.getMetricTypes.mockResolvedValue([])
  api.getConfig.mockResolvedValue(makeConfig())
  api.listSamples.mockResolvedValue([REFERENCE, TRAINING_SAMPLE])
  api.listModels.mockResolvedValue([])
  let objectUrls = 0
  URL.createObjectURL = vi.fn(() => `blob:preview-${++objectUrls}`)
  URL.revokeObjectURL = vi.fn()
})

describe("AdminSkillLabPage", () => {
  it("renders the skill parameters, readiness issues and the levels/criteria from the catalog config", async () => {
    renderLab()

    expect(await screen.findByRole("heading", { name: "Dominadas" })).toBeInTheDocument()
    expect(api.getConfig).toHaveBeenCalledWith("skill-1")
    expect(screen.getByText("Fútbol")).toBeInTheDocument()
    expect(screen.getByText(/Pose en video/)).toBeInTheDocument()
    expect(screen.getByText("Umbral mínimo 80%")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Volver al catálogo/ })).toHaveAttribute("href", "/admin/catalog")

    const readiness = screen.getByTestId("skill-lab-readiness")
    expect(readiness).toHaveTextContent("El nivel «Intermedio» no tiene video de referencia.")
    expect(readiness).not.toHaveClass("text-destructive")

    // S8: only the current step (first level by level_number) is rendered.
    const cards = screen.getAllByTestId(/^skill-lab-level-/)
    expect(cards.map((card) => card.getAttribute("data-testid"))).toEqual(["skill-lab-level-lvl-1"])

    const beginner = await levelCard("lvl-1")
    expect(beginner.getByText("Mínimo 60%")).toBeInTheDocument()
    const touchRow = beginner.getByRole("row", { name: /Toques seguidos/ })
    expect(touchRow).toHaveTextContent("Toques seguidos con balón")
    expect(touchRow).toHaveTextContent("40%")
    expect(touchRow).toHaveTextContent("10")
    const postureRow = beginner.getByRole("row", { name: /Postura corporal/ })
    expect(postureRow).toHaveTextContent("Replicar video de referencia")
    expect(postureRow).toHaveTextContent("60%")
    expect(postureRow).toHaveTextContent("Sí")
    expect(beginner.getByTestId("skill-lab-reference-current")).toHaveTextContent("MP4")
    expect(beginner.getByTestId("skill-lab-reference-current")).toHaveTextContent("5.0 MB")
    expect(beginner.getByText("P-07")).toBeInTheDocument()
  })

  it("shows the ready state when the backend reports no readiness issues", async () => {
    api.getConfig.mockResolvedValue(makeConfig({ readiness: { ready_to_validate: true, issues: [] } }))
    renderLab()
    expect(await screen.findByText("Listo para validar")).toBeInTheDocument()
  })

  it("uploads a reference video for the level with role REFERENCE and the chosen criterion", async () => {
    const user = userEvent.setup()
    api.uploadSample.mockResolvedValue({ ...REFERENCE, id: "ref-2" })
    renderLab()
    await levelCard("lvl-1")
    await user.click(screen.getByRole("button", { name: "Siguiente: Nivel 2 · Intermedio" }))
    const card = await levelCard("lvl-2")

    const upload = card.getByRole("button", { name: /Subir referencia/ })
    expect(upload).toBeDisabled()
    const file = video("referencia.mp4")
    await user.upload(card.getByLabelText("Video"), file)
    await user.click(card.getByRole("combobox", { name: "Criterio de la referencia" }))
    await user.click(await screen.findByRole("option", { name: "Técnica de golpeo" }))
    await user.click(card.getByRole("switch", { name: "Tengo el consentimiento de la persona del video" }))
    await user.click(upload)

    await waitFor(() =>
      expect(api.uploadSample).toHaveBeenCalledWith("skill-1", {
        file,
        skillLevelId: "lvl-2",
        sampleRole: "REFERENCE",
        criterionKey: "c-rep",
        participantId: null,
        signedConsent: true,
      })
    )
    await waitFor(() => expect(api.getConfig).toHaveBeenCalledTimes(2))
  })

  it("requires consent for training videos and uploads them sequentially with level and criterion", async () => {
    const user = userEvent.setup()
    api.uploadSample.mockResolvedValue(TRAINING_SAMPLE)
    renderLab()
    const card = await levelCard("lvl-1")

    const first = video("a.mp4")
    const second = video("b.mp4")
    await user.upload(card.getByLabelText("Videos"), [first, second])
    await user.click(card.getByRole("combobox", { name: "Criterio de los videos" }))
    await user.click(await screen.findByRole("option", { name: "Toques seguidos" }))
    await user.type(card.getByLabelText("Participante (opcional)"), "P-09")

    const uploadButton = card.getByRole("button", { name: /Subir 2 videos/ })
    expect(uploadButton).toBeDisabled()
    expect(card.getByText("Activá el consentimiento.")).toBeInTheDocument()

    await user.click(card.getByRole("switch", { name: "Tengo el consentimiento de las personas de los videos" }))
    expect(uploadButton).toBeEnabled()
    await user.click(uploadButton)

    await waitFor(() => expect(api.uploadSample).toHaveBeenCalledTimes(2))
    expect(api.uploadSample).toHaveBeenNthCalledWith(1, "skill-1", {
      file: first,
      skillLevelId: "lvl-1",
      sampleRole: "TRAINING",
      criterionKey: "c-touch",
      participantId: "P-09",
      signedConsent: true,
    })
    expect(api.uploadSample).toHaveBeenNthCalledWith(2, "skill-1", expect.objectContaining({ file: second, sampleRole: "TRAINING", criterionKey: "c-touch" }))
    expect(await card.findAllByText("Subido")).toHaveLength(2)
  })

  it("deletes a training sample after confirming in the dialog", async () => {
    const user = userEvent.setup()
    api.deleteSample.mockResolvedValue()
    renderLab()
    const card = await levelCard("lvl-1")
    await user.click(card.getByRole("button", { name: "Eliminar video de entrenamiento P-07" }))
    expect(api.deleteSample).not.toHaveBeenCalled()
    await user.click(await screen.findByRole("button", { name: "Eliminar" }))
    await waitFor(() => expect(api.deleteSample).toHaveBeenCalledWith("train-1"))
  })

  it("trains the model and shows its version and key metrics", async () => {
    const user = userEvent.setup()
    api.train.mockResolvedValue(MODEL)
    api.getConfig.mockResolvedValueOnce(makeConfig()).mockResolvedValue(makeConfig({ active_model: MODEL }))
    renderLab("/admin/skill-lab/skill-1?paso=3")

    await user.click(await screen.findByRole("button", { name: /Entrenar modelo/ }))
    expect(api.train).toHaveBeenCalledWith("skill-1")

    const panel = await screen.findByTestId("skill-lab-active-model")
    expect(panel).toHaveTextContent("v2")
    expect(panel).toHaveTextContent("Videos4")
    expect(panel).not.toHaveTextContent("Principiante: 3")
    await user.click(within(panel).getByRole("button", { name: "Detalles" }))
    expect(panel).toHaveTextContent("Principiante: 3")
    expect(panel).toHaveTextContent("Intermedio: 1")
    expect(panel).toHaveTextContent("75%")
    expect(panel).toHaveTextContent("Pocos videos en el nivel Intermedio.")
  })

  it("validates a video and renders achieved level, score, per-criterion breakdown and notes as non-destructive alerts", async () => {
    const user = userEvent.setup()
    let resolveValidation: (value: SkillValidationResult) => void = () => {}
    api.validate.mockImplementation(() => new Promise((resolve) => { resolveValidation = resolve }))
    renderLab("/admin/skill-lab/skill-1?paso=4")

    const validateButton = await screen.findByRole("button", { name: /Validar video/ })
    expect(validateButton).toBeDisabled()
    const file = video()
    await user.upload(screen.getByLabelText("Video"), file)
    await user.click(validateButton)

    expect(api.validate).toHaveBeenCalledWith("skill-1", file, null)
    expect(await screen.findByText("Analizando… puede tardar unos minutos")).toBeInTheDocument()
    resolveValidation(RESULT)

    expect(await screen.findByTestId("skill-lab-achieved-level")).toHaveTextContent("Principiante")
    expect(screen.getByTestId("skill-lab-score")).toHaveTextContent("74.5/100")
    expect(screen.getByTestId("skill-lab-approved")).toHaveTextContent("No aprobado")
    expect(screen.getByTestId("skill-lab-approved")).toHaveTextContent("80%")
    expect(screen.getByTestId("skill-lab-model-estimate")).toHaveTextContent("Principiante")
    expect(screen.getByTestId("skill-lab-model-estimate")).toHaveTextContent("70%")

    const notes = screen.getByTestId("skill-lab-result-notes")
    expect(notes).toHaveTextContent("El ángulo de cámara difiere de la referencia.")
    expect(notes).not.toHaveClass("text-destructive")

    // S9: the per-level/criterion breakdown starts collapsed.
    const beginner = screen.getByTestId("skill-lab-result-level-lvl-1")
    expect(within(beginner).queryByText("Postura corporal")).not.toBeInTheDocument()
    const content = within(screen.getByTestId("skill-lab-step-content"))
    await user.click(content.getByRole("button", { name: /Principiante/ }))
    expect(within(beginner).getByText("Postura corporal")).toBeInTheDocument()
    expect(within(beginner).getByText("Se contaron 7 de 10 toques.")).toBeInTheDocument()
    expect(within(beginner).getByText("Superado")).toBeInTheDocument()

    await user.click(content.getByRole("button", { name: /Intermedio/ }))
    const intermediate = screen.getByTestId("skill-lab-result-level-lvl-2")
    // level status badge + the criterion that could not be scored
    expect(within(intermediate).getAllByText("No evaluable")).toHaveLength(2)
    expect(within(intermediate).getByText("Falta el video de referencia.")).toBeInTheDocument()
    const reason = within(intermediate).getByTestId("skill-lab-not-evaluable-lvl-2")
    expect(reason).toHaveTextContent("El nivel no tiene video de referencia.")
    expect(reason).not.toHaveClass("text-destructive")
    expect(document.querySelector('[data-slot="alert"].text-destructive')).toBeNull()
  })

  it("sends the selected level when the admin targets a specific level", async () => {
    const user = userEvent.setup()
    api.validate.mockResolvedValue(RESULT)
    renderLab("/admin/skill-lab/skill-1?paso=4")
    await screen.findByRole("heading", { name: "Dominadas" })
    const file = video()
    await user.upload(screen.getByLabelText("Video"), file)
    await user.click(screen.getByRole("combobox", { name: "Nivel a validar" }))
    await user.click(await screen.findByRole("option", { name: "Nivel 2 · Intermedio" }))
    await user.click(screen.getByRole("button", { name: /Validar video/ }))
    await waitFor(() => expect(api.validate).toHaveBeenCalledWith("skill-1", file, "lvl-2"))
  })

  it("on transport failure shows a retry warning without any grade and keeps the selected file", async () => {
    const user = userEvent.setup()
    api.validate.mockRejectedValueOnce(new ApiError("Failed to fetch", 0)).mockResolvedValueOnce(RESULT)
    renderLab("/admin/skill-lab/skill-1?paso=4")
    await screen.findByRole("heading", { name: "Dominadas" })
    const file = video()
    await user.upload(screen.getByLabelText("Video"), file)
    await user.click(screen.getByRole("button", { name: /Validar video/ }))

    const warning = await screen.findByTestId("skill-lab-validation-warning")
    expect(warning).toHaveTextContent("No se pudo conectar con el servidor")
    expect(warning).not.toHaveClass("text-destructive")
    expect(screen.queryByTestId("skill-lab-score")).not.toBeInTheDocument()
    expect(screen.queryByTestId("skill-lab-achieved-level")).not.toBeInTheDocument()
    expect(screen.getByText(/intento\.mp4/)).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /Reintentar/ }))
    await waitFor(() => expect(api.validate).toHaveBeenCalledTimes(2))
    expect(api.validate).toHaveBeenLastCalledWith("skill-1", file, null)
    expect(await screen.findByTestId("skill-lab-score")).toHaveTextContent("74.5/100")
    expect(screen.queryByTestId("skill-lab-validation-warning")).not.toBeInTheDocument()
  })
})

describe("Skill lab copy (S9)", () => {
  it("moves the reference explanation behind an info tooltip reachable by its accessible name", async () => {
    const user = userEvent.setup()
    renderLab()
    const card = await levelCard("lvl-1")
    expect(screen.queryByText(/deberá replicar en vivo/)).not.toBeInTheDocument()

    await user.click(card.getByRole("button", { name: "Ayuda: video de referencia" }))
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Lo que la persona deberá replicar en vivo para este nivel.")
  })
})

describe("Video previews (S10)", () => {
  const FUTURE = "2999-01-01T00:00:00Z"
  const signedUrl = (id: string, token = "t1") =>
    `http://localhost:8000/api/admin/skill-lab/samples/${id}/file?token=${token}`

  async function videoIn(container: HTMLElement): Promise<HTMLVideoElement> {
    let found: HTMLVideoElement | null = null
    await waitFor(() => {
      found = container.querySelector("video")
      expect(found).not.toBeNull()
    })
    return found as unknown as HTMLVideoElement
  }

  it("'Ver' on a training sample opens a dialog that plays the signed URL", async () => {
    const user = userEvent.setup()
    api.getSamplePreviewUrl.mockResolvedValue({ url: signedUrl("train-1"), expires_at: FUTURE, content_type: "video/webm" })
    renderLab()
    const card = await levelCard("lvl-1")
    expect(api.getSamplePreviewUrl).not.toHaveBeenCalled()

    await user.click(card.getByRole("button", { name: "Ver video 1" }))

    const dialog = await screen.findByRole("dialog")
    expect(within(dialog).getByText("Video 1")).toBeInTheDocument()
    const player = await videoIn(dialog)
    expect(player).toHaveAttribute("src", signedUrl("train-1"))
    expect(player).toHaveAttribute("controls")
    expect(player).toHaveAttribute("preload", "metadata")
    expect(api.getSamplePreviewUrl).toHaveBeenCalledTimes(1)
    expect(api.getSamplePreviewUrl).toHaveBeenCalledWith("train-1")
  })

  it("the reference block expands a player for the current reference on 'Ver'", async () => {
    const user = userEvent.setup()
    api.getSamplePreviewUrl.mockResolvedValue({ url: signedUrl("ref-1"), expires_at: FUTURE, content_type: "video/mp4" })
    renderLab()
    const card = await levelCard("lvl-1")
    expect(card.queryByLabelText("Reproductor de referencia")).not.toBeInTheDocument()

    await user.click(card.getByRole("button", { name: "Ver video de referencia" }))

    expect(api.getSamplePreviewUrl).toHaveBeenCalledWith("ref-1")
    expect(await card.findByLabelText("Reproductor de referencia")).toHaveAttribute("src", signedUrl("ref-1"))
    await user.click(card.getByRole("button", { name: "Ocultar video de referencia" }))
    expect(card.queryByLabelText("Reproductor de referencia")).not.toBeInTheDocument()
  })

  it("a failed URL request shows 'Video no disponible' instead of a player", async () => {
    const user = userEvent.setup()
    api.getSamplePreviewUrl.mockRejectedValue(new ApiError("El video de la muestra no está disponible.", 404))
    renderLab()
    const card = await levelCard("lvl-1")
    await user.click(card.getByRole("button", { name: "Ver video 1" }))

    const dialog = await screen.findByRole("dialog")
    expect(await within(dialog).findByText("Video no disponible")).toBeInTheDocument()
    expect(dialog.querySelector("video")).toBeNull()
  })

  it("re-requests a fresh URL once when the token expired, then gives up", async () => {
    const user = userEvent.setup()
    api.getSamplePreviewUrl
      .mockResolvedValueOnce({ url: signedUrl("train-1", "old"), expires_at: "2000-01-01T00:00:00Z", content_type: "video/webm" })
      .mockResolvedValueOnce({ url: signedUrl("train-1", "new"), expires_at: FUTURE, content_type: "video/webm" })
    renderLab()
    const card = await levelCard("lvl-1")
    await user.click(card.getByRole("button", { name: "Ver video 1" }))
    const dialog = await screen.findByRole("dialog")

    fireEvent.error(await videoIn(dialog))
    await waitFor(() => expect(dialog.querySelector("video")).toHaveAttribute("src", signedUrl("train-1", "new")))
    expect(api.getSamplePreviewUrl).toHaveBeenCalledTimes(2)

    fireEvent.error(await videoIn(dialog))
    expect(await within(dialog).findByText("Video no disponible")).toBeInTheDocument()
    expect(api.getSamplePreviewUrl).toHaveBeenCalledTimes(2)
  })

  it("previews the file selected for validation and revokes its object URL on change and unmount", async () => {
    const user = userEvent.setup()
    const view = renderLab("/admin/skill-lab/skill-1?paso=4")
    await screen.findByRole("heading", { name: "Dominadas" })
    const first = video("uno.mp4")
    await user.upload(screen.getByLabelText("Video"), first)

    const preview = await screen.findByLabelText("Vista previa del video a validar")
    expect(URL.createObjectURL).toHaveBeenCalledWith(first)
    expect(preview).toHaveAttribute("src", "blob:preview-1")
    expect(URL.revokeObjectURL).not.toHaveBeenCalled()

    await user.upload(screen.getByLabelText("Video"), video("dos.mp4"))
    await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:preview-1"))
    expect(screen.getByLabelText("Vista previa del video a validar")).toHaveAttribute("src", "blob:preview-2")

    view.unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:preview-2")
    expect(api.getSamplePreviewUrl).not.toHaveBeenCalled()
  })

  it("previews the reference file and the clicked pending training file before upload", async () => {
    const user = userEvent.setup()
    renderLab()
    const card = await levelCard("lvl-1")

    const reference = video("referencia.mp4")
    await user.upload(card.getByLabelText("Video"), reference)
    expect(await card.findByLabelText("Vista previa de la referencia")).toHaveAttribute("src", "blob:preview-1")

    await user.upload(card.getByLabelText("Videos"), [video("a.mp4"), video("b.mp4")])
    expect(await card.findByLabelText("Vista previa de a.mp4")).toBeInTheDocument()
    const pending = card.getByRole("list", { name: "Videos seleccionados" })
    await user.click(within(pending).getByRole("button", { name: /b\.mp4/ }))
    expect(await card.findByLabelText("Vista previa de b.mp4")).toBeInTheDocument()
    expect(card.queryByLabelText("Vista previa de a.mp4")).not.toBeInTheDocument()
    expect(within(pending).getByRole("button", { name: /b\.mp4/ })).toHaveAttribute("aria-pressed", "true")
  })
})
