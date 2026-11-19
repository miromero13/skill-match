import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { BiometricEnrollmentCard } from "@/components/profile/biometric-enrollment-card"
import { ProfilePage } from "@/pages/profile-page"
import { useProfileStore } from "@/stores/profile-store"
import { useAuthStore } from "@/stores/auth-store"
import { MemoryRouter } from "react-router-dom"
import type { UserProfileData } from "@/types/profile"

describe("BiometricEnrollmentCard y ProfilePage - Identidad limpia e inmutable", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.getState().login(
      {
        id: "usr-1",
        fullName: "María Ilse Romero Saavedra",
        email: "ilse@example.com",
        role: "MEMBER",
        skillPointsBalance: 100,
        reputationScore: 90,
        trustLevel: 2,
        isVerified: true,
      },
      "token",
      "refresh"
    )
  })

  it("solicita obligatoriamente anverso y reverso y NO muestra campos de texto manuales para CI o Nombre", () => {
    useProfileStore.setState({
      profile: {
        id: "usr-1",
        user_id: "usr-1",
        full_name: "María Ilse Romero Saavedra",
        bio: "",
        languages: ["Español"],
        primary_skills: [],
        secondary_skills: [],
        availability: [],
        reputation_score: 90,
        trust_level: 2,
        is_identity_verified: false,
        identity_status: "UNVERIFIED",
        has_biometric_enrollment: false,
      } as unknown as UserProfileData,
      isVerifyingIdentity: false,
    })

    render(<BiometricEnrollmentCard />)

    // 1. Debe mostrar ambas secciones de captura obligatoria: Anverso y Reverso
    expect(screen.getByText(/1\. Anverso \(Frontal\)/i)).toBeInTheDocument()
    expect(screen.getByText(/2\. Reverso \(Posterior\)/i)).toBeInTheDocument()
    expect(screen.getByText(/Cargar anverso del carnet/i)).toBeInTheDocument()
    expect(screen.getByText(/Cargar reverso del carnet/i)).toBeInTheDocument()

    // 2. NO debe existir input manual de texto para escribir el CI o el nombre
    expect(screen.queryByLabelText(/número de carnet de identidad o dni/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/nombre completo en el carnet/i)).not.toBeInTheDocument()

    // 3. Debe mostrar el titular oficial de la cuenta como referencia
    expect(screen.getByText(/Titular Oficial de la Cuenta a Contrastar/i)).toBeInTheDocument()
    expect(screen.getByText("María Ilse Romero Saavedra")).toBeInTheDocument()

    // 4. El botón para avanzar debe estar deshabilitado hasta cargar ambos lados
    const nextBtn = screen.getByRole("button", { name: /siguiente: cotejo facial en vivo/i })
    expect(nextBtn).toBeDisabled()
  })

  it("bloquea la tarjeta como inmutable y sin datos técnicos confusos una vez verificado", () => {
    useProfileStore.setState({
      profile: {
        id: "usr-1",
        user_id: "usr-1",
        full_name: "María Ilse Romero Saavedra",
        id_document_number: "11348175",
        id_face_similarity_score: 0.73,
        identity_verified_at: "2026-11-18T10:00:00Z",
        identity_status: "VERIFIED",
        has_biometric_enrollment: true,
        biometric_face_hash: "6e3996c627871e9c1dd62c30734abeaabe71e6bf4efa95eca8194bc94723b7f5",
      } as unknown as UserProfileData,
      isVerifyingIdentity: false,
    })

    render(<BiometricEnrollmentCard />)

    // Datos limpios y comprensibles para el usuario
    expect(screen.getByText(/Titular Verificado: María Ilse Romero Saavedra/i)).toBeInTheDocument()
    expect(screen.getByText(/CI\/DNI: 11348175/i)).toBeInTheDocument()
    expect(screen.getByText(/Identidad Oficial Verificada ✓/i)).toBeInTheDocument()
    expect(screen.getByText(/Documento e identidad vinculados de forma inmutable/i)).toBeInTheDocument()

    // NO debe mostrar jerga técnica confusa (ni SHA-256 ni vectores de 128 dimensiones)
    expect(screen.queryByText(/Firma Criptográfica SHA-256/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Vector local OpenCV SFace/i)).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /actualizar documento o reverificar/i })).not.toBeInTheDocument()
  })

  it("en ProfilePage NO muestra el botón 'Verificar Otro Documento' cuando ya está verificado", () => {
    useProfileStore.setState({
      profile: {
        id: "usr-1",
        user_id: "usr-1",
        full_name: "María Ilse Romero Saavedra",
        id_document_number: "11348175",
        identity_status: "VERIFIED",
        has_biometric_enrollment: true,
        languages: ["Español"],
        primary_skills: [],
        secondary_skills: [],
        availability: [],
      } as unknown as UserProfileData,
      isVerifyingIdentity: false,
    })

    render(
      <MemoryRouter initialEntries={["/app/profile"]}>
        <ProfilePage />
      </MemoryRouter>
    )

    // La tarjeta a la izquierda muestra el check verde
    expect(screen.getByText(/CI Verificado ✓/i)).toBeInTheDocument()
    expect(screen.getByText(/CI: 11348175 • Titular verificado con biometría/i)).toBeInTheDocument()

    // NO debe salir el botón 'Verificar Otro Documento'
    expect(screen.queryByRole("button", { name: /verificar otro documento/i })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /verificar con carnet/i })).not.toBeInTheDocument()
  })
})
