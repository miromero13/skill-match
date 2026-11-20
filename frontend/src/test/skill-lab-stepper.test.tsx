import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom"
import { AdminSkillLabPage } from "@/pages/admin-skill-lab-page"
import { skillLabApi } from "@/features/skill-lab/api/skill-lab-api"
import { buildSkillLabSteps, clampStepNumber, levelStepStatus } from "@/features/skill-lab/lib/skill-lab-steps"
import { Button } from "@/components/ui/button"
import type {
  SkillLabConfig,
  SkillLabCriterion,
  SkillLabLevel,
  SkillLabModel,
  SkillLabSample,
} from "@/features/skill-lab/types"

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
  },
}))

const api = vi.mocked(skillLabApi)

function reference(levelId: string, criterionKey: string | null = null): SkillLabSample {
  return {
    id: `ref-${levelId}-${criterionKey ?? "level"}`,
    skill_id: "skill-1",
    skill_level_id: levelId,
    criterion_key: criterionKey,
    sample_role: "REFERENCE",
    file_format: "mp4",
    file_size_bytes: 1024 * 1024,
    participant_id: null,
    analysis_ready: true,
    analysis_notes: [],
    created_at: "2026-11-19T10:00:00Z",
  }
}

function criterion(overrides: Partial<SkillLabCriterion>): SkillLabCriterion {
  return {
    key: "c",
    name: "Criterio",
    weight: 100,
    description: "",
    metric_type: "REFERENCE_REPLICATION",
    target: null,
    training_samples: 0,
    has_reference: false,
    ...overrides,
  }
}

function level(overrides: Partial<SkillLabLevel>): SkillLabLevel {
  return {
    id: "lvl",
    level_number: 1,
    name: "Nivel",
    min_score: 60,
    weights_total: 100,
    criteria: [],
    training_samples: 0,
    reference: null,
    ...overrides,
  }
}

/** Nivel 1: completo sin referencia de nivel (su único criterio de replicación tiene la propia). */
const LEVEL_COMPLETE = level({
  id: "lvl-1",
  level_number: 1,
  name: "Básico",
  criteria: [
    criterion({ key: "c-pose", name: "Postura", weight: 70, has_reference: true, training_samples: 2 }),
    criterion({ key: "c-ball", name: "Toques", weight: 30, metric_type: "BALL_TOUCH_STREAK", target: 10 }),
  ],
  training_samples: 2,
})
/** Nivel 2: sin criterios, con referencia de nivel, sin videos de entrenamiento. */
const LEVEL_NO_TRAINING = level({
  id: "lvl-2",
  level_number: 2,
  name: "Saltos",
  reference: reference("lvl-2"),
})
/** Nivel 3: criterio de replicación sin referencia propia ni de nivel. */
const LEVEL_MISSING_REFERENCE = level({
  id: "lvl-3",
  level_number: 3,
  name: "Avanzado",
  criteria: [criterion({ key: "c-tec", name: "Técnica", training_samples: 4 })],
  training_samples: 4,
})

const MODEL: SkillLabModel = {
  id: "model-1",
  skill_id: "skill-1",
  version: "v1",
  activa: true,
  metricas: {},
  created_at: "2026-11-20T09:00:00Z",
}

function makeConfig(overrides: Partial<SkillLabConfig> = {}): SkillLabConfig {
  return {
    skill: {
      id: "skill-1",
      name: "Dominadas",
      category: { id: "cat-1", name: "Fútbol" },
      challenge_type: null,
      min_approval_threshold: 70,
    },
    // Desordenados a propósito: el asistente ordena por level_number.
    levels: [LEVEL_MISSING_REFERENCE, LEVEL_COMPLETE, LEVEL_NO_TRAINING],
    active_model: null,
    readiness: { ready_to_validate: false, issues: ["El nivel «Avanzado» no tiene video de referencia."] },
    ...overrides,
  }
}

function LocationProbe() {
  const location = useLocation()
  const navigate = useNavigate()
  return (
    <>
      <p data-testid="location-search">{location.search}</p>
      <Button type="button" variant="ghost" onClick={() => navigate(-1)}>
        Atrás del navegador
      </Button>
    </>
  )
}

function renderLab(path = "/admin/skill-lab/skill-1") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/admin/skill-lab/:skillId"
          element={
            <>
              <AdminSkillLabPage />
              <LocationProbe />
            </>
          }
        />
        <Route path="/admin/catalog" element={<p>Catálogo</p>} />
      </Routes>
    </MemoryRouter>
  )
}

async function stepNav() {
  return within(await screen.findByRole("navigation", { name: "Pasos del laboratorio" }))
}

function stepButton(number: number) {
  return screen.getByTestId(`skill-lab-step-${number}`)
}

function locationSearch() {
  return screen.getByTestId("location-search").textContent
}

beforeEach(() => {
  vi.clearAllMocks()
  api.getMetricTypes.mockResolvedValue([])
  api.getConfig.mockResolvedValue(makeConfig())
  api.listSamples.mockResolvedValue([reference("lvl-1", "c-pose"), reference("lvl-2")])
  api.listModels.mockResolvedValue([])
})

describe("Skill lab step-by-step navigation (S8)", () => {
  it("lists one step per level ordered by level_number, then Entrenamiento and Probar validación", async () => {
    renderLab()
    const nav = await stepNav()
    const names = nav.getAllByRole("button").map((button) => button.getAttribute("aria-label"))
    expect(names).toEqual([
      "Paso 1: Nivel 1 · Básico — Completo",
      "Paso 2: Nivel 2 · Saltos — Sin videos de entrenamiento",
      "Paso 3: Nivel 3 · Avanzado — Falta referencia",
      "Paso 4: Entrenamiento — Sin entrenar",
      "Paso 5: Probar validación — Opcional",
    ])
    expect(stepButton(1)).toHaveAttribute("aria-current", "step")
    expect(stepButton(2)).not.toHaveAttribute("aria-current")
    expect(screen.getByTestId("skill-lab-step-summary")).toHaveTextContent("Paso 1 de 5 — Nivel 1 · Básico")
  })

  it("renders only the current step content", async () => {
    renderLab()
    expect(await screen.findByTestId("skill-lab-level-lvl-1")).toBeInTheDocument()
    expect(screen.queryByTestId("skill-lab-level-lvl-2")).not.toBeInTheDocument()
    expect(screen.queryByTestId("skill-lab-level-lvl-3")).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Entrenar modelo/ })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Validar video/ })).not.toBeInTheDocument()

    const content = screen.getByTestId("skill-lab-step-content")
    expect(within(content).getByRole("heading", { name: "Video de referencia" })).toBeInTheDocument()
    expect(within(content).getByRole("heading", { name: "Videos de entrenamiento" })).toBeInTheDocument()
  })

  it("moves with Siguiente/Anterior, keeps ?paso= in the URL and pushes history entries", async () => {
    const user = userEvent.setup()
    const scrollSpy = vi.spyOn(HTMLElement.prototype, "scrollIntoView")
    renderLab()
    await screen.findByTestId("skill-lab-level-lvl-1")
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled()

    await user.click(screen.getByRole("button", { name: "Siguiente: Nivel 2 · Saltos" }))
    expect(await screen.findByTestId("skill-lab-level-lvl-2")).toBeInTheDocument()
    expect(screen.queryByTestId("skill-lab-level-lvl-1")).not.toBeInTheDocument()
    expect(locationSearch()).toBe("?paso=2")
    expect(stepButton(2)).toHaveAttribute("aria-current", "step")
    expect(scrollSpy).toHaveBeenCalled()

    await user.click(screen.getByRole("button", { name: "Siguiente: Nivel 3 · Avanzado" }))
    expect(locationSearch()).toBe("?paso=3")

    await user.click(screen.getByRole("button", { name: "Anterior" }))
    expect(locationSearch()).toBe("?paso=2")
    expect(screen.getByTestId("skill-lab-level-lvl-2")).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Siguiente: Nivel 3 · Avanzado" }))
    await user.click(screen.getByRole("button", { name: "Atrás del navegador" }))
    expect(locationSearch()).toBe("?paso=2")
    expect(screen.getByTestId("skill-lab-level-lvl-2")).toBeInTheDocument()
    scrollSpy.mockRestore()
  })

  it("jumps to any step when its indicator is clicked", async () => {
    const user = userEvent.setup()
    renderLab()
    await stepNav()
    await user.click(stepButton(4))
    expect(await screen.findByRole("button", { name: /Entrenar modelo/ })).toBeInTheDocument()
    expect(locationSearch()).toBe("?paso=4")
    expect(stepButton(4)).toHaveAttribute("aria-current", "step")
    expect(screen.queryByTestId(/^skill-lab-level-/)).not.toBeInTheDocument()
  })

  it("clamps an out-of-range ?paso= to the last step and shows Volver al catálogo instead of Siguiente", async () => {
    const user = userEvent.setup()
    renderLab("/admin/skill-lab/skill-1?paso=99")
    expect(await screen.findByRole("button", { name: /Validar video/ })).toBeInTheDocument()
    expect(stepButton(5)).toHaveAttribute("aria-current", "step")
    await waitFor(() => expect(locationSearch()).toBe("?paso=5"))

    const footer = within(screen.getByTestId("skill-lab-step-footer"))
    expect(footer.queryByRole("button", { name: /Siguiente/ })).not.toBeInTheDocument()
    const back = footer.getByRole("link", { name: /Volver al catálogo/ })
    expect(back).toHaveAttribute("href", "/admin/catalog")
    await user.click(back)
    expect(await screen.findByText("Catálogo")).toBeInTheDocument()
  })

  it("falls back to the first step for a non numeric ?paso=", async () => {
    renderLab("/admin/skill-lab/skill-1?paso=abc")
    expect(await screen.findByTestId("skill-lab-level-lvl-1")).toBeInTheDocument()
    await waitFor(() => expect(locationSearch()).toBe("?paso=1"))
  })

  it("derives level and training status from the config", async () => {
    api.getConfig.mockResolvedValue(makeConfig({ active_model: MODEL }))
    renderLab()
    await stepNav()
    expect(stepButton(1)).toHaveAttribute("data-status", "complete")
    expect(stepButton(1)).toHaveTextContent("Completo")
    expect(stepButton(2)).toHaveAttribute("data-status", "no-training")
    expect(stepButton(2)).toHaveTextContent("Sin videos de entrenamiento")
    expect(stepButton(3)).toHaveAttribute("data-status", "missing-reference")
    expect(stepButton(3)).toHaveTextContent("Falta referencia")
    expect(stepButton(4)).toHaveAttribute("data-status", "complete")
    expect(stepButton(4)).toHaveTextContent("Completo")
    expect(stepButton(5)).toHaveAttribute("data-status", "neutral")
  })

  it("never blocks navigation and shows a non-destructive hint after leaving an incomplete level", async () => {
    const user = userEvent.setup()
    renderLab("/admin/skill-lab/skill-1?paso=3")
    await screen.findByTestId("skill-lab-level-lvl-3")
    expect(screen.queryByTestId("skill-lab-incomplete-hint")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Siguiente: Entrenamiento" }))
    expect(await screen.findByRole("button", { name: /Entrenar modelo/ })).toBeInTheDocument()
    const hint = screen.getByTestId("skill-lab-incomplete-hint")
    expect(hint).toHaveTextContent("Nivel 3 · Avanzado quedó incompleto: falta el video de referencia.")
    expect(hint).not.toHaveClass("text-destructive")
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()

    await user.click(within(hint).getByRole("button", { name: "Volver al nivel" }))
    expect(await screen.findByTestId("skill-lab-level-lvl-3")).toBeInTheDocument()
    expect(locationSearch()).toBe("?paso=3")
    expect(screen.queryByTestId("skill-lab-incomplete-hint")).not.toBeInTheDocument()

    // Leaving a non-level step clears the hint; leaving a complete level never shows it.
    await user.click(screen.getByRole("button", { name: "Siguiente: Entrenamiento" }))
    expect(screen.getByTestId("skill-lab-incomplete-hint")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Siguiente: Probar validación" }))
    expect(screen.queryByTestId("skill-lab-incomplete-hint")).not.toBeInTheDocument()
    await user.click(stepButton(1))
    await user.click(screen.getByRole("button", { name: "Siguiente: Nivel 2 · Saltos" }))
    expect(screen.queryByTestId("skill-lab-incomplete-hint")).not.toBeInTheDocument()
  })

  it("without levels shows the empty message and only Entrenamiento and Probar validación", async () => {
    api.getConfig.mockResolvedValue(
      makeConfig({ levels: [], readiness: { ready_to_validate: false, issues: ["La habilidad no tiene niveles configurados."] } })
    )
    renderLab()
    const nav = await stepNav()
    expect(nav.getAllByRole("button").map((button) => button.getAttribute("aria-label"))).toEqual([
      "Paso 1: Entrenamiento — Sin entrenar",
      "Paso 2: Probar validación — Opcional",
    ])
    expect(screen.getByText("Esta habilidad no tiene niveles configurados en el catálogo.")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Entrenar modelo/ })).toBeInTheDocument()
  })

  it("collapses a long readiness list", async () => {
    const user = userEvent.setup()
    api.getConfig.mockResolvedValue(
      makeConfig({ readiness: { ready_to_validate: false, issues: ["Pendiente A", "Pendiente B", "Pendiente C", "Pendiente D"] } })
    )
    renderLab()
    const readiness = await screen.findByTestId("skill-lab-readiness")
    expect(readiness).toHaveTextContent("Pendientes antes de validar (4)")
    expect(readiness).toHaveTextContent("Pendiente A")
    expect(readiness).toHaveTextContent("Pendiente B")
    expect(readiness).not.toHaveTextContent("Pendiente C")
    await user.click(within(readiness).getByRole("button", { name: "Ver 2 más" }))
    expect(readiness).toHaveTextContent("Pendiente D")
    expect(within(readiness).getByRole("button", { name: "Ver menos" })).toBeInTheDocument()
  })
})

describe("skill-lab-steps helpers", () => {
  it("applies the backend readiness rule for required references", () => {
    expect(levelStepStatus(LEVEL_COMPLETE)).toBe("complete")
    expect(levelStepStatus(LEVEL_NO_TRAINING)).toBe("no-training")
    expect(levelStepStatus(LEVEL_MISSING_REFERENCE)).toBe("missing-reference")
    // Sin criterios y sin referencia de nivel: falta referencia aunque haya videos.
    expect(levelStepStatus(level({ training_samples: 3 }))).toBe("missing-reference")
    // Solo criterios de toques: no requiere referencia.
    expect(
      levelStepStatus(
        level({
          criteria: [criterion({ metric_type: "BALL_TOUCH_STREAK", target: 5 })],
          training_samples: 1,
        })
      )
    ).toBe("complete")
    // Criterio de replicación sin referencia propia: la referencia del nivel lo cubre.
    expect(levelStepStatus(level({ ...LEVEL_MISSING_REFERENCE, reference: reference("lvl-3") }))).toBe("complete")
  })

  it("clamps step numbers to 1..total", () => {
    expect(clampStepNumber("99", 5)).toBe(5)
    expect(clampStepNumber("0", 5)).toBe(1)
    expect(clampStepNumber("-2", 5)).toBe(1)
    expect(clampStepNumber("abc", 5)).toBe(1)
    expect(clampStepNumber(null, 5)).toBe(1)
    expect(clampStepNumber("3", 5)).toBe(3)
    expect(clampStepNumber("2.7", 5)).toBe(2)
  })

  it("builds steps in order with stable labels", () => {
    const steps = buildSkillLabSteps(makeConfig())
    expect(steps.map((step) => step.title)).toEqual([
      "Nivel 1 · Básico",
      "Nivel 2 · Saltos",
      "Nivel 3 · Avanzado",
      "Entrenamiento",
      "Probar validación",
    ])
  })
})
