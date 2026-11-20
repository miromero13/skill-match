import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { ComplaintsPage } from '@/pages/complaints/complaints-page'
import { AdminComplaintsPage } from '@/pages/admin/admin-complaints-page'
import { AdminRouteGuard } from '@/components/admin-route-guard'
import { useComplaintStore } from '@/stores/complaint-store'
import { useAuthStore } from '@/stores/auth-store'
import * as complaintService from '@/services/complaint-service'
import type { Complaint } from '@/types/complaint'

vi.mock('@/services/complaint-service', () => ({
  submitComplaint: vi.fn(),
  getMyComplaints: vi.fn(),
  getAdminComplaints: vi.fn(),
  getAdminComplaintDetail: vi.fn(),
  resolveComplaint: vi.fn(),
}))

const mockComplaints: Complaint[] = [
  {
    id: 'complaint-001',
    user_id: 'member-123',
    user_full_name: 'Carlos Alumno',
    user_email: 'carlos@example.com',
    reason: 'NO_SHOW',
    title: 'Tutor no se presentó a la sesión',
    description: 'Esperé 25 minutos en la sala virtual y el instructor no asistió.',
    evidence_urls: ['https://drive.google.com/screenshot1.png'],
    status: 'OPEN',
    admin_response: null,
    points_compensated: 0,
    created_at: new Date().toISOString(),
  },
  {
    id: 'complaint-002',
    user_id: 'member-123',
    user_full_name: 'Carlos Alumno',
    user_email: 'carlos@example.com',
    reason: 'PAYMENT_DISPUTE',
    title: 'Cobro de puntos por clase cancelada',
    description: 'Se debitaron 50 puntos a pesar de haber cancelado con 24h de anticipación.',
    evidence_urls: [],
    status: 'RESOLVED',
    admin_response: 'Se comprobó la cancelación oportuna. Se restituyeron los puntos en tu billetera.',
    points_compensated: 50,
    created_at: new Date().toISOString(),
    resolved_at: new Date().toISOString(),
  },
]

describe('Complaints & Dispute Resolution Suite (SM-55 / HU-43)', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    useAuthStore.getState().login(
      {
        id: 'member-123',
        fullName: 'Carlos Alumno',
        email: 'carlos@example.com',
        role: 'MEMBER',
        skillPointsBalance: 300,
        reputationScore: 4.9,
        trustLevel: 3,
        isVerified: true,
      },
      'fake-member-token',
      'fake-refresh'
    )

    useComplaintStore.setState({
      memberComplaints: mockComplaints,
      memberTotal: mockComplaints.length,
      isLoadingMember: false,
      isSubmitting: false,
      adminComplaints: mockComplaints,
      adminTotal: mockComplaints.length,
      selectedComplaint: mockComplaints[0],
      isLoadingAdmin: false,
      isResolving: false,
      statusFilter: 'ALL',
    })
  })

  it('renders member complaints page with metrics and resolved compensation badge (RF-GOV-01)', async () => {
    vi.mocked(complaintService.getMyComplaints).mockResolvedValue({
      items: mockComplaints,
      total: mockComplaints.length,
    })

    render(
      <MemoryRouter>
        <ComplaintsPage />
      </MemoryRouter>
    )

    // Verificar encabezado y métricas
    expect(screen.getByText('Centro de Quejas y Mediación')).toBeInTheDocument()
    expect(screen.getByText('+50 SP')).toBeInTheDocument() // Puntos compensados
    expect(screen.getByText('Tutor no se presentó a la sesión')).toBeInTheDocument()
    expect(screen.getByText('Cobro de puntos por clase cancelada')).toBeInTheDocument()
    expect(screen.getByText('+50 SP Compensados')).toBeInTheDocument()
  })

  it('opens create complaint dialog and submits new dispute (RF-GOV-01)', async () => {
    vi.mocked(complaintService.getMyComplaints).mockResolvedValue({
      items: mockComplaints,
      total: mockComplaints.length,
    })
    vi.mocked(complaintService.submitComplaint).mockResolvedValue({
      id: 'complaint-003',
      user_id: 'member-123',
      user_full_name: 'Carlos Alumno',
      reason: 'TECHNICAL_ISSUES',
      title: 'Corte de audio recurrente',
      description: 'El tutor no pudo transmitir audio durante toda la clase.',
      evidence_urls: [],
      status: 'OPEN',
      points_compensated: 0,
      created_at: new Date().toISOString(),
    })

    render(
      <MemoryRouter>
        <ComplaintsPage />
      </MemoryRouter>
    )

    // Abrir diálogo
    const openBtn = screen.getByRole('button', { name: /Radicar Nueva Queja/i })
    fireEvent.click(openBtn)

    expect(screen.getByText('Radicar Queja o Disputa Formal')).toBeInTheDocument()

    // Llenar formulario
    const titleInput = screen.getByPlaceholderText(/Ej. Tutor no asistió a la sesión de Python/i)
    fireEvent.change(titleInput, { target: { value: 'Corte de audio recurrente' } })

    const descInput = screen.getByPlaceholderText(/Explica qué sucedió, fecha/i)
    fireEvent.change(descInput, {
      target: { value: 'El tutor no pudo transmitir audio durante toda la clase.' },
    })

    // Enviar
    const submitBtn = screen.getByRole('button', { name: /Enviar Queja Formal/i })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(complaintService.submitComplaint).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Corte de audio recurrente',
          description: 'El tutor no pudo transmitir audio durante toda la clase.',
        })
      )
    })
  })

  it('renders admin arbitration console and allows resolving with point compensation (RF-GOV-02, RF-GOV-03)', async () => {
    useAuthStore.getState().login(
      {
        id: 'admin-999',
        fullName: 'Admin Arbitro',
        email: 'admin@skillmatch.io',
        role: 'ADMIN',
        skillPointsBalance: 0,
        reputationScore: 5.0,
        trustLevel: 5,
        isVerified: true,
      },
      'admin-token',
      'refresh'
    )

    vi.mocked(complaintService.getAdminComplaints).mockResolvedValue({
      items: mockComplaints,
      total: mockComplaints.length,
    })
    vi.mocked(complaintService.resolveComplaint).mockResolvedValue({
      ...mockComplaints[0],
      status: 'RESOLVED',
      admin_response: 'Se verificaron los logs y se confirma la inasistencia. Se compensa al alumno.',
      points_compensated: 50,
      resolved_at: new Date().toISOString(),
    })

    render(
      <MemoryRouter>
        <AdminComplaintsPage />
      </MemoryRouter>
    )

    // Verificar panel Master-Detail
    expect(screen.getByText('Resolución de Disputas y Quejas')).toBeInTheDocument()
    expect(screen.getByText('Emitir Dictamen Arbitral')).toBeInTheDocument()

    // Escribir dictamen
    const responseTextarea = screen.getByPlaceholderText(/Redacta la resolución oficial del caso/i)
    fireEvent.change(responseTextarea, {
      target: {
        value: 'Se verificaron los logs y se confirma la inasistencia. Se compensa al alumno.',
      },
    })

    // Activar toggle de compensación
    const compensateSwitch = screen.getByRole('switch', { name: /Compensar con SkillPoints/i })
    fireEvent.click(compensateSwitch)

    // Presionar botón de resolución favorable
    const resolveBtn = screen.getByRole('button', { name: /Resolver y Compensar \+50 SP/i })
    fireEvent.click(resolveBtn)

    await waitFor(() => {
      expect(complaintService.resolveComplaint).toHaveBeenCalledWith(
        'complaint-001',
        expect.objectContaining({
          status: 'RESOLVED',
          admin_response: 'Se verificaron los logs y se confirma la inasistencia. Se compensa al alumno.',
          points_to_compensate: 50,
        })
      )
    })
  })

  it('enforces 404 security-by-obfuscation when MEMBER tries to access admin route guard', () => {
    // Usuario autenticado con rol MEMBER
    useAuthStore.getState().login(
      {
        id: 'member-123',
        fullName: 'Carlos Alumno',
        email: 'carlos@example.com',
        role: 'MEMBER',
        skillPointsBalance: 300,
        reputationScore: 4.9,
        trustLevel: 3,
        isVerified: true,
      },
      'member-token',
      'refresh'
    )

    render(
      <MemoryRouter>
        <AdminRouteGuard>
          <div>SECRETO PANEL ADMIN</div>
        </AdminRouteGuard>
      </MemoryRouter>
    )

    // Debe mostrar la página 404 (NotFoundPage), NUNCA el panel ni 403 Forbidden
    expect(screen.queryByText('SECRETO PANEL ADMIN')).not.toBeInTheDocument()
    expect(screen.getByText(/404/i)).toBeInTheDocument()
  })
})
