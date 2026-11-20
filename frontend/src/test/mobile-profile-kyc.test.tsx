import { render, screen, fireEvent } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { MobileBottomBar } from "@/components/navigation/mobile-bottom-bar"
import { MobileAvailabilityEditor } from "@/components/profile/mobile-availability-editor"
import { BiometricEnrollmentCard } from "@/components/profile/biometric-enrollment-card"
import { useNotificationStore } from "@/stores/notification-store"
import { useProfileStore } from "@/stores/profile-store"
import { useAuthStore } from "@/stores/auth-store"

describe("Mobile Experience & KYC Suite", () => {
  beforeEach(() => {
    vi.clearAllMocks()

    useAuthStore.getState().login(
      {
        id: "member-mobile-1",
        fullName: "Sofia Mobile",
        email: "sofia@example.com",
        role: "MEMBER",
        skillPointsBalance: 500,
        reputationScore: 4.9,
        trustLevel: 3,
        isVerified: false,
      },
      "token",
      "refresh"
    )

    useProfileStore.setState({
      profile: {
        id: "member-mobile-1",
        full_name: "Sofia Mobile",
        email: "sofia@example.com",
        identity_status: "PENDING",
        trust_level: 3,
        has_biometric_enrollment: false,
      } as any,
      availabilitySlots: [
        {
          id: "slot-1",
          user_id: "member-mobile-1",
          day_of_week: 0,
          start_time: "09:00",
          end_time: "13:00",
          is_enabled: true,
          modality: "BOTH",
        },
      ],
      isSavingAvailability: false,
    })

    useNotificationStore.setState({
      unreadTotal: 4,
      unreadLoading: false,
      unreadError: null,
    })
  })

  it("renders MobileBottomBar with reactive unread notification badge on 'Avisos'", () => {
    render(
      <MemoryRouter>
        <MobileBottomBar />
      </MemoryRouter>
    )

    expect(screen.getByText("Avisos")).toBeInTheDocument()
    // Badge con el conteo de 4 notificaciones sin leer
    expect(screen.getByText("4")).toBeInTheDocument()
  })

  it("renders MobileAvailabilityEditor with horizontal Day-Strip and allows switching days", () => {
    render(<MobileAvailabilityEditor />)

    expect(screen.getByText("Agenda y Horarios Semanales")).toBeInTheDocument()
    // Botones de días en el carrusel
    expect(screen.getByText("Lun")).toBeInTheDocument()
    expect(screen.getByText("Mar")).toBeInTheDocument()
    expect(screen.getByText("Mié")).toBeInTheDocument()
    expect(screen.getByText("Jue")).toBeInTheDocument()
    expect(screen.getByText("Vie")).toBeInTheDocument()

    // En Lunes, debe figurar la franja inicial 09:00 - 13:00
    expect(screen.getByText("09:00 - 13:00")).toBeInTheDocument()

    // Cambiar al Martes (sin franjas iniciales)
    fireEvent.click(screen.getByText("Mar"))
    expect(screen.getByText(/No tienes disponibilidad configurada para el Martes/i)).toBeInTheDocument()

    // Botones de presets rápidos
    expect(screen.getByText("Jornada Laboral (09:00 - 18:00)")).toBeInTheDocument()
    expect(screen.getByText("Copiar a Lun-Vie")).toBeInTheDocument()
    expect(screen.getByText("Limpiar Día")).toBeInTheDocument()
  })

  it("renders BiometricEnrollmentCard with touch buttons for camera capture and gallery", () => {
    render(<BiometricEnrollmentCard />)

    expect(screen.getByText("Verificación de Identidad con Carnet (CI/DNI)")).toBeInTheDocument()
    // Botones para tomar foto y galería en el paso de documentos
    const tomarFotoButtons = screen.getAllByRole("button", { name: /Tomar Foto/i })
    expect(tomarFotoButtons.length).toBeGreaterThanOrEqual(2) // Anverso y Reverso

    const galeriaButtons = screen.getAllByRole("button", { name: /Galería/i })
    expect(galeriaButtons.length).toBeGreaterThanOrEqual(2)
  })
})
