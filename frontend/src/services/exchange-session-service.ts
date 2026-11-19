import { apiClient } from "@/services/api-client"
import type {
  ExchangeSession,
  ExchangeSessionCreate,
  ExchangeSessionReschedule,
  SessionCalendarExport,
  SessionConfirmRequest,
  SessionConfirmResponse,
  SessionListData,
  SessionNoShowRequest,
  SessionNoShowResponse,
  SessionPresencePinResponse,
} from "@/types/exchange-session"

const base = "/sessions"
const requestOptions = { showToastOnError: true, showToastOnSuccess: false }

export async function getExchangeSessions(page = 1, pageSize = 20) {
  const response = await apiClient.get<SessionListData>(base, {
    ...requestOptions,
    params: { page, page_size: pageSize },
  })
  if (
    response.count == null ||
    !Number.isSafeInteger(response.count) ||
    response.count < 0
  )
    throw new Error("La respuesta no contiene un total de sesiones válido.")
  return { ...response, count: response.count }
}

export function createExchangeSession(payload: ExchangeSessionCreate) {
  return apiClient.post<ExchangeSession>(base, payload, requestOptions)
}

export function acceptExchangeSession(id: string) {
  return apiClient.patch<ExchangeSession>(
    `${base}/${encodeURIComponent(id)}/status`,
    { status: "ACCEPTED" },
    requestOptions
  )
}

export function rejectExchangeSession(id: string) {
  return apiClient.patch<ExchangeSession>(
    `${base}/${encodeURIComponent(id)}/status`,
    { status: "REJECTED" },
    requestOptions
  )
}

export function rescheduleExchangeSession(
  id: string,
  payload: ExchangeSessionReschedule
) {
  return apiClient.put<ExchangeSession>(
    `${base}/${encodeURIComponent(id)}/reschedule`,
    payload,
    requestOptions
  )
}

export function cancelExchangeSession(id: string, cancellationReason: string) {
  return apiClient.post<ExchangeSession>(
    `${base}/${encodeURIComponent(id)}/cancel`,
    { cancellation_reason: cancellationReason },
    requestOptions
  )
}

export function getSessionCalendarExport(id: string, signal?: AbortSignal) {
  return apiClient.get<SessionCalendarExport>(
    `${base}/${encodeURIComponent(id)}/calendar-export`,
    { ...requestOptions, signal }
  )
}

export function confirmExchangeSession(
  id: string,
  payload: SessionConfirmRequest
) {
  return apiClient.post<SessionConfirmResponse>(
    `${base}/${encodeURIComponent(id)}/confirm`,
    payload,
    requestOptions
  )
}

export function reportSessionNoShow(
  id: string,
  payload: SessionNoShowRequest
) {
  return apiClient.post<SessionNoShowResponse>(
    `${base}/${encodeURIComponent(id)}/report-noshow`,
    payload,
    requestOptions
  )
}

export function getSessionPresencePin(id: string) {
  return apiClient.get<SessionPresencePinResponse>(
    `${base}/${encodeURIComponent(id)}/presence-pin`,
    requestOptions
  )
}
