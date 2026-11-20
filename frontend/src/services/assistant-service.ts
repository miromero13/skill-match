import { apiClient } from '@/services/api-client'
import type { ChatHistoryItem, ChatMessageResponse } from '@/types/assistant'

const ASSISTANT_ENDPOINT = '/assistant'

export async function sendAssistantMessage(message: string): Promise<ChatMessageResponse> {
  const response = await apiClient.post<ChatMessageResponse>(`${ASSISTANT_ENDPOINT}/chat`, {
    message,
  })
  return (
    response.data ?? {
      reply: 'Disculpa, no pude procesar tu respuesta en este momento.',
      action: null,
      suggested_prompts: [],
    }
  )
}

export async function getAssistantHistory(): Promise<ChatHistoryItem[]> {
  const response = await apiClient.get<ChatHistoryItem[]>(`${ASSISTANT_ENDPOINT}/history`)
  return response.data ?? []
}

export async function clearAssistantHistory(): Promise<void> {
  await apiClient.delete(`${ASSISTANT_ENDPOINT}/history`)
}
