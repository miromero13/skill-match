import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { AssistantFab } from '@/components/assistant/assistant-fab'
import { AssistantChatDrawer } from '@/components/assistant/assistant-chat-drawer'
import { useAssistantStore } from '@/stores/assistant-store'
import { useAuthStore } from '@/stores/auth-store'
import { useWalletStore } from '@/stores/wallet-store'
import * as assistantService from '@/services/assistant-service'

vi.mock('@/services/assistant-service', () => ({
  sendAssistantMessage: vi.fn(),
  getAssistantHistory: vi.fn().mockResolvedValue([]),
  clearAssistantHistory: vi.fn().mockResolvedValue(undefined),
}))

describe('Asistente Virtual UI & Store Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    useAuthStore.getState().login(
      {
        id: 'user-assistant-test',
        fullName: 'Usuario Copilot Test',
        email: 'copilot@skillmatch.io',
        role: 'MEMBER',
        skillPointsBalance: 200,
        reputationScore: 5.0,
        trustLevel: 3,
        isVerified: true,
      },
      'fake-token',
      'fake-refresh'
    )

    useAssistantStore.setState({
      isOpen: false,
      isLoading: false,
      messages: [],
      suggestedPrompts: [
        '¿Cuál es mi saldo actual?',
        '¿Cuándo es mi próxima clase?',
      ],
    })
  })

  it('renderiza el botón flotante (FAB) para usuarios MEMBER y lo oculta para ADMIN', () => {
    const { rerender } = render(
      <MemoryRouter>
        <AssistantFab />
      </MemoryRouter>
    )

    const fab = screen.getByLabelText('Abrir Asistente Virtual')
    expect(fab).toBeDefined()

    // Oculto para ADMIN
    useAuthStore.setState({
      user: {
        id: 'admin-1',
        fullName: 'Admin',
        email: 'admin@skillmatch.io',
        role: 'ADMIN',
        skillPointsBalance: 0,
        reputationScore: 5.0,
        trustLevel: 3,
        isVerified: true,
      },
    })
    rerender(
      <MemoryRouter>
        <AssistantFab />
      </MemoryRouter>
    )
    expect(screen.queryByLabelText('Abrir Asistente Virtual')).toBeNull()
  })

  it('abre el drawer y muestra el estado inicial con sugerencias', () => {
    useAssistantStore.setState({ isOpen: true })

    render(
      <MemoryRouter>
        <AssistantChatDrawer />
      </MemoryRouter>
    )

    expect(screen.getByText('SkillMatch Copilot')).toBeDefined()
    expect(screen.getByText('¡Hola! ¿En qué puedo ayudarte hoy?')).toBeDefined()
    expect(screen.getByText('¿Cuál es mi saldo actual?')).toBeDefined()
  })

  it('envía un mensaje y renderiza la respuesta del asistente con tarjeta de billetera interactiva', async () => {
    vi.mocked(assistantService.sendAssistantMessage).mockResolvedValueOnce({
      reply: 'Tienes 200 SkillPoints disponibles en tu billetera.',
      action: {
        type: 'wallet_topup',
        data: {
          available_points: 200,
          usd_equivalent: 20.0,
          is_verified: true,
        },
      },
      suggested_prompts: ['¿Cómo funciona el Escrow?'],
    })

    useAssistantStore.setState({ isOpen: true })

    render(
      <MemoryRouter>
        <AssistantChatDrawer />
      </MemoryRouter>
    )

    const input = screen.getByPlaceholderText(/Pregunta sobre tus sesiones/i)
    fireEvent.change(input, { target: { value: '¿Cuánto saldo tengo?' } })

    const sendBtn = screen.getByLabelText('Enviar mensaje')
    fireEvent.click(sendBtn)

    await waitFor(() => {
      expect(screen.getByText('Tienes 200 SkillPoints disponibles en tu billetera.')).toBeDefined()
      expect(screen.getByText('Tu Billetera SkillMatch')).toBeDefined()
      expect(screen.getByText('Recargar SkillPoints')).toBeDefined()
    })

    // Hacer clic en Recargar SkillPoints debe abrir el modal de recarga
    const topupBtn = screen.getByText('Recargar SkillPoints')
    fireEvent.click(topupBtn)

    expect(useWalletStore.getState().isTopupModalOpen).toBe(true)
    expect(useAssistantStore.getState().isOpen).toBe(false)
  })

  it('permite limpiar la conversación con el botón de papelera', async () => {
    useAssistantStore.setState({
      isOpen: true,
      messages: [
        {
          id: 'msg-1',
          role: 'user',
          content: 'Hola',
          timestamp: new Date().toISOString(),
        },
        {
          id: 'msg-2',
          role: 'assistant',
          content: '¡Hola! ¿En qué te ayudo?',
          timestamp: new Date().toISOString(),
        },
      ],
    })

    render(
      <MemoryRouter>
        <AssistantChatDrawer />
      </MemoryRouter>
    )

    expect(screen.getByText('¡Hola! ¿En qué te ayudo?')).toBeDefined()

    const clearBtn = screen.getByLabelText('Limpiar conversación')
    fireEvent.click(clearBtn)

    await waitFor(() => {
      expect(useAssistantStore.getState().messages.length).toBe(0)
    })
  })

  it('renderiza tarjeta de acción cuando el asistente crea una habilidad para enseñar', async () => {
    vi.mocked(assistantService.sendAssistantMessage).mockResolvedValueOnce({
      reply: '¡Habilidad registrada exitosamente en tu perfil!',
      action: {
        type: 'skill_created',
        data: {
          skill_name: 'Programación en Python',
          level: 'ADVANCED',
          experience_years: 3,
          hourly_points_rate: 25,
          accepts_points: true,
        },
      },
      suggested_prompts: ['¿Cuál es mi saldo actual?'],
    })

    useAssistantStore.setState({ isOpen: true })

    render(
      <MemoryRouter>
        <AssistantChatDrawer />
      </MemoryRouter>
    )

    const input = screen.getByPlaceholderText(/Pregunta sobre tus sesiones/i)
    fireEvent.change(input, { target: { value: 'Quiero enseñar Programación en Python' } })

    const sendBtn = screen.getByLabelText('Enviar mensaje')
    fireEvent.click(sendBtn)

    await waitFor(() => {
      expect(screen.getByText('¡Habilidad registrada exitosamente en tu perfil!')).toBeDefined()
      expect(screen.getByText('Habilidad Registrada')).toBeDefined()
      expect(screen.getByText('Programación en Python')).toBeDefined()
      expect(screen.getByText('25 SP / hora')).toBeDefined()
      expect(screen.getByText('Buscar Alumnos')).toBeDefined()
    })
  })

  it('renderiza tarjeta de acción cuando el asistente registra un interés de aprendizaje', async () => {
    vi.mocked(assistantService.sendAssistantMessage).mockResolvedValueOnce({
      reply: '¡Interés de aprendizaje registrado exitosamente!',
      action: {
        type: 'learning_skill_created',
        data: {
          skill_name: 'Dominadas con el balón',
          current_level: 1,
          target_level: 3,
          urgency: 'HIGH',
        },
      },
      suggested_prompts: ['Buscar tutores de Fútbol'],
    })

    useAssistantStore.setState({ isOpen: true })

    render(
      <MemoryRouter>
        <AssistantChatDrawer />
      </MemoryRouter>
    )

    const input = screen.getByPlaceholderText(/Pregunta sobre tus sesiones/i)
    fireEvent.change(input, { target: { value: 'Quiero aprender Dominadas con el balón' } })

    const sendBtn = screen.getByLabelText('Enviar mensaje')
    fireEvent.click(sendBtn)

    await waitFor(() => {
      expect(screen.getByText('¡Interés de aprendizaje registrado exitosamente!')).toBeDefined()
      expect(screen.getByText('Interés de Aprendizaje')).toBeDefined()
      expect(screen.getByText('Dominadas con el balón')).toBeDefined()
      expect(screen.getByText('Buscar Tutores')).toBeDefined()
    })
  })
})
