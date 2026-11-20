import { create } from 'zustand'
import {
  clearAssistantHistory,
  getAssistantHistory,
  sendAssistantMessage,
} from '@/services/assistant-service'
import type { ChatHistoryItem } from '@/types/assistant'

const DEFAULT_PROMPTS = [
  '¿Cuál es mi saldo actual?',
  '¿Cuándo es mi próxima clase?',
  'Buscar tutores de programación',
  '¿Cómo funciona el sistema Escrow?',
]

interface AssistantState {
  isOpen: boolean
  isLoading: boolean
  messages: ChatHistoryItem[]
  suggestedPrompts: string[]

  // Acciones
  openAssistant: () => void
  closeAssistant: () => void
  toggleAssistant: () => void
  loadHistory: () => Promise<void>
  sendMessage: (text: string) => Promise<void>
  clearConversation: () => Promise<void>
}

export const useAssistantStore = create<AssistantState>((set, get) => ({
  isOpen: false,
  isLoading: false,
  messages: [],
  suggestedPrompts: DEFAULT_PROMPTS,

  openAssistant: () => {
    set({ isOpen: true })
    if (get().messages.length === 0) {
      void get().loadHistory()
    }
  },

  closeAssistant: () => {
    set({ isOpen: false })
  },

  toggleAssistant: () => {
    const next = !get().isOpen
    set({ isOpen: next })
    if (next && get().messages.length === 0) {
      void get().loadHistory()
    }
  },

  loadHistory: async () => {
    try {
      const history = await getAssistantHistory()
      if (history.length > 0) {
        set({ messages: history })
      }
    } catch {
      // Ignorar error de carga inicial
    }
  },

  sendMessage: async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || get().isLoading) return

    const tempUserMsg: ChatHistoryItem = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
    }

    set((state) => ({
      messages: [...state.messages, tempUserMsg],
      isLoading: true,
    }))

    try {
      const response = await sendAssistantMessage(trimmed)
      const assistantMsg: ChatHistoryItem = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.reply,
        timestamp: new Date().toISOString(),
        action: response.action,
      }

      set((state) => ({
        messages: [...state.messages, assistantMsg],
        suggestedPrompts:
          response.suggested_prompts && response.suggested_prompts.length > 0
            ? response.suggested_prompts
            : DEFAULT_PROMPTS,
        isLoading: false,
      }))
    } catch {
      const errorMsg: ChatHistoryItem = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: 'Hubo un inconveniente conectando con el servicio de IA. Por favor intenta de nuevo en unos momentos.',
        timestamp: new Date().toISOString(),
      }
      set((state) => ({
        messages: [...state.messages, errorMsg],
        isLoading: false,
      }))
    }
  },

  clearConversation: async () => {
    try {
      await clearAssistantHistory()
      set({ messages: [], suggestedPrompts: DEFAULT_PROMPTS })
    } catch {
      set({ messages: [] })
    }
  },
}))
