import { apiClient } from "@/services/api-client"

export interface MatchProposal {
  id: string
  starts_at: string
  status: "pending" | "superseded" | "accepted" | "declined"
  proposed_by_you: boolean
  contact_enabled: boolean
}

export interface MatchMessage {
  id: string
  body: string
  sent_by_you: boolean
  created_at: string
}

const path = (id: string) => `/matches/${encodeURIComponent(id)}`
const mutation = { showToastOnSuccess: true, showToastOnError: true }

export const readProposal = (id: string, signal: AbortSignal) =>
  apiClient.get<MatchProposal | null>(`${path(id)}/proposal`, { signal })

export const sendProposal = (id: string, startsAt: string, replacesId?: string) =>
  apiClient.post<MatchProposal>(`${path(id)}/proposals`, {
    starts_at: startsAt, replaces_proposal_id: replacesId ?? null,
  }, mutation)

export const decideProposal = (id: string, action: "accept" | "decline", proposalId: string) =>
  apiClient.post<MatchProposal>(`${path(id)}/${action}`, { proposal_id: proposalId }, mutation)

export const dismissMatch = (id: string) => apiClient.delete<null>(path(id), mutation)

export const readMessages = (id: string, page: number, signal: AbortSignal) =>
  apiClient.get<MatchMessage[]>(`${path(id)}/messages`, { signal, params: { page } })

export const sendMessage = (id: string, body: string) =>
  apiClient.post<MatchMessage>(`${path(id)}/messages`, { body }, mutation)
