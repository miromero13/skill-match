import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { AdminDatasetCapturePage } from "@/pages/admin-dataset-capture-page"
import { AdminRouteGuard } from "@/components/admin-route-guard"
import { useAuthStore } from "@/stores/auth-store"
import { useDatasetCaptureStore } from "@/stores/dataset-capture-store"

vi.mock("@/services/dataset-sample-service", () => ({
  calculateFileSha256: vi.fn().mockResolvedValue("1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"),
  getDatasetSamples: vi.fn().mockResolvedValue({
    statuscode: 200,
    message: "OK",
    data: [
      {
        id: "sample-1",
        discipline: "futbol",
        challenge: "Dominadas de Balón",
        hardware_info: "Logitech C920",
        signed_consent: true,
        file_format: "mp4",
        file_size_bytes: 5242880,
        file_hash_sha256: "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        storage_path: "datasets/futbol/sample-1.mp4",
        created_at: "2026-11-15T12:00:00Z",
        updated_at: "2026-11-15T12:00:00Z",
      },
    ],
    count: 1,
  }),
  uploadDatasetSample: vi.fn().mockResolvedValue({
    statuscode: 201,
    message: "Muestra multimedia subida y procesada exitosamente.",
    data: null,
  }),
  deleteDatasetSample: vi.fn().mockResolvedValue({
    statuscode: 200,
    message: "Muestra eliminada exitosamente.",
    data: null,
  }),
}))

vi.mock("@/services/admin-catalog-service", () => ({
  getCategories: vi.fn().mockResolvedValue([
    { id: "cat-1", name: "Deporte", slug: "deporte", is_active: true },
    { id: "cat-2", name: "Música", slug: "musica", is_active: true },
    { id: "cat-3", name: "Programación", slug: "programacion", is_active: true },
  ]),
  getSkills: vi.fn().mockResolvedValue({
    items: [
      {
        id: "skill-fb-1",
        category_id: "cat-1",
        name: "Dominadas y Control de Balón",
        slug: "dominadas-y-control-de-balon",
        min_approval_threshold: 80,
        is_ready_to_publish: true,
        is_active: true,
        levels: [],
      },
    ],
    count: 1,
  }),
}))

describe("AdminDatasetCapturePage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useDatasetCaptureStore.getState().resetRecording()
    useDatasetCaptureStore.setState({
      samples: [],
      totalCount: 0,
      isLoading: false,
      isUploading: false,
      error: null,
      lastUploadMessage: null,
      signedConsent: false,
    })
  })

  it("renders page header and exclusive admin badge", async () => {
    render(
      <MemoryRouter>
        <AdminDatasetCapturePage />
      </MemoryRouter>
    )

    expect(
      screen.getByRole("heading", {
        name: /Ingesta y Captura de Muestras Multimedia/i,
      })
    ).toBeInTheDocument()

    expect(screen.getByText(/Panel Exclusivo ADMIN/i)).toBeInTheDocument()
    expect(screen.getByText(/RF-IA-18 \/ HU-17/i)).toBeInTheDocument()
  })

  it("renders capture modality tabs (Video, Audio, Código)", () => {
    render(
      <MemoryRouter>
        <AdminDatasetCapturePage />
      </MemoryRouter>
    )

    expect(screen.getByText(/Video \(Fútbol\)/i)).toBeInTheDocument()
    expect(screen.getByText(/Audio \(Música\)/i)).toBeInTheDocument()
    expect(screen.getByText(/Código \(AST\)/i)).toBeInTheDocument()
  })

  it("toggles signed consent and updates store", async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <AdminDatasetCapturePage />
      </MemoryRouter>
    )

    const consentSwitch = screen.getByRole("switch", {
      name: /Consentimiento Informado Firmado/i,
    })
    expect(consentSwitch).not.toBeChecked()

    await user.click(consentSwitch)
    expect(useDatasetCaptureStore.getState().signedConsent).toBe(true)
  })

  it("displays server message in Alert banner when upload finishes", () => {
    useDatasetCaptureStore.setState({
      lastUploadMessage: "Muestra multimedia subida y procesada exitosamente.",
    })

    render(
      <MemoryRouter>
        <AdminDatasetCapturePage />
      </MemoryRouter>
    )

    expect(screen.getByText(/Servidor SkillMatch/i)).toBeInTheDocument()
    expect(
      screen.getByText("Muestra multimedia subida y procesada exitosamente.")
    ).toBeInTheDocument()
  })

  it("renders automatic metadata mode without requiring manual football fields", () => {
    render(
      <MemoryRouter>
        <AdminDatasetCapturePage />
      </MemoryRouter>
    )

    expect(screen.getByText(/Automático/i)).toBeInTheDocument()
    expect(
      screen.getByText(/Opciones avanzadas y etiquetado manual \(opcional\)/i)
    ).toBeInTheDocument()
    expect(
      screen.queryByText(/Sección 10 — Sin Fuga por Participante/i)
    ).not.toBeInTheDocument()
  })

  it("allows selecting multiple files and uploads batch to Garage S3", async () => {
    const user = userEvent.setup()
    const { uploadDatasetSample } = await import("@/services/dataset-sample-service")

    render(
      <MemoryRouter>
        <AdminDatasetCapturePage />
      </MemoryRouter>
    )

    const file1 = new File(["clip-video-1"], "clip-1.mp4", { type: "video/mp4" })
    const file2 = new File(["clip-video-2"], "clip-2.mp4", { type: "video/mp4" })

    const input = screen.getByLabelText(/Carga Múltiple de Archivos Reales/i)
    await user.upload(input, [file1, file2])

    expect(screen.getByText(/Archivos en lote \(2\):/i)).toBeInTheDocument()
    expect(screen.getByText("clip-1.mp4")).toBeInTheDocument()
    expect(screen.getByText("clip-2.mp4")).toBeInTheDocument()

    // Enable consent
    const consentSwitch = screen.getByRole("switch", {
      name: /Consentimiento Informado Firmado/i,
    })
    await user.click(consentSwitch)

    const uploadBtn = screen.getByRole("button", {
      name: /Subir Lote de 2 Muestras Reales a Garage S3/i,
    })
    await user.click(uploadBtn)

    const { waitFor } = await import("@testing-library/react")
    await waitFor(() => {
      expect(uploadDatasetSample).toHaveBeenCalledTimes(2)
    })
  })
})

describe("AdminRouteGuard obfuscation 404 for /admin/capture", () => {
  it("renders 404 page when accessed by a non-authenticated user", () => {
    useAuthStore.setState({
      isAuthenticated: false,
      token: null,
      user: null,
    })

    render(
      <MemoryRouter initialEntries={["/admin/capture"]}>
        <Routes>
          <Route
            path="/admin/capture"
            element={
              <AdminRouteGuard>
                <div>Protected Admin Capture Content</div>
              </AdminRouteGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    expect(
      screen.queryByText("Protected Admin Capture Content")
    ).not.toBeInTheDocument()
    expect(screen.getByText(/Error 404/i)).toBeInTheDocument()
    expect(screen.getByText(/Página no encontrada/i)).toBeInTheDocument()
  })

  it("renders 404 page when accessed by a MEMBER user (strict 404 policy)", () => {
    useAuthStore.setState({
      isAuthenticated: true,
      token: "valid-member-token",
      user: {
        id: "member-1",
        email: "member@example.com",
        fullName: "Member Regular",
        role: "MEMBER",
        skillPointsBalance: 100,
        reputationScore: 5.0,
        trustLevel: 1,
        isVerified: true,
      },
    })

    render(
      <MemoryRouter initialEntries={["/admin/capture"]}>
        <Routes>
          <Route
            path="/admin/capture"
            element={
              <AdminRouteGuard>
                <div>Protected Admin Capture Content</div>
              </AdminRouteGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    expect(
      screen.queryByText("Protected Admin Capture Content")
    ).not.toBeInTheDocument()
    expect(screen.getByText(/Error 404/i)).toBeInTheDocument()
    expect(screen.getByText(/Página no encontrada/i)).toBeInTheDocument()
  })

  it("renders protected content when user has ADMIN role", () => {
    useAuthStore.setState({
      isAuthenticated: true,
      token: "valid-admin-token",
      user: {
        id: "admin-1",
        email: "admin@example.com",
        fullName: "Admin User",
        role: "ADMIN",
        skillPointsBalance: 100,
        reputationScore: 5.0,
        trustLevel: 1,
        isVerified: true,
      },
    })

    render(
      <MemoryRouter initialEntries={["/admin/capture"]}>
        <Routes>
          <Route
            path="/admin/capture"
            element={
              <AdminRouteGuard>
                <div>Protected Admin Capture Content</div>
              </AdminRouteGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    expect(
      screen.getByText("Protected Admin Capture Content")
    ).toBeInTheDocument()
  })
})
