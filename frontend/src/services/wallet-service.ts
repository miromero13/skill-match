import { apiClient } from '@/services/api-client'
import type {
  WalletBalance,
  PointPackage,
  TopupPayload,
  TopupResult,
  CashoutCalculation,
  CashoutPayload,
  CashoutRequest,
  PointTransaction,
} from '@/types/wallet'

const WALLET_ENDPOINT = '/wallet'

export async function getWalletBalance(): Promise<WalletBalance> {
  const response = await apiClient.get<WalletBalance>(`${WALLET_ENDPOINT}/balance`, {
    showToastOnError: true,
  })
  return (
    response.data || {
      balance: 0,
      escrow_balance: 0,
      available_balance: 0,
      currency: 'SkillPoints',
      points_per_usd: 10,
    }
  )
}

export async function getPointPackages(): Promise<PointPackage[]> {
  const response = await apiClient.get<PointPackage[]>(`${WALLET_ENDPOINT}/packages`, {
    showToastOnError: true,
  })
  const list = response.data || []
  return list.map((pkg) => {
    const key = pkg.package_id || pkg.id || ''
    const title = pkg.name || pkg.label || ''
    return {
      ...pkg,
      package_id: key,
      id: key,
      name: title,
      label: title,
      total_points: pkg.total_points ?? (pkg.points + (pkg.bonus_points || 0)),
    }
  })
}

export async function topupPoints(payload: TopupPayload): Promise<TopupResult> {
  const response = await apiClient.post<TopupResult>(
    `${WALLET_ENDPOINT}/topup`,
    payload,
    {
      showToastOnError: true,
      showToastOnSuccess: true,
    }
  )
  if (!response.data) {
    throw new Error(response.message || 'Error al procesar la recarga de puntos')
  }
  return response.data
}

export async function calculateCashout(points: number): Promise<CashoutCalculation> {
  const response = await apiClient.post<CashoutCalculation>(
    `${WALLET_ENDPOINT}/cashout/calculate`,
    { points },
    { showToastOnError: false }
  )
  if (!response.data) {
    throw new Error('No se pudo calcular la liquidación')
  }
  return response.data
}

export async function requestCashout(payload: CashoutPayload): Promise<CashoutRequest> {
  const response = await apiClient.post<CashoutRequest>(
    `${WALLET_ENDPOINT}/cashout`,
    payload,
    {
      showToastOnError: true,
      showToastOnSuccess: true,
    }
  )
  if (!response.data) {
    throw new Error(response.message || 'Error al solicitar el retiro')
  }
  return response.data
}

export async function getWalletTransactions(
  type?: string,
  limit = 50
): Promise<PointTransaction[]> {
  const params: Record<string, string | number> = { limit }
  if (type && type !== 'ALL') {
    params.type = type
  }
  const response = await apiClient.get<PointTransaction[]>(
    `${WALLET_ENDPOINT}/transactions`,
    {
      params,
      showToastOnError: true,
    }
  )
  return response.data || []
}

export async function paySessionEscrow(sessionId: string): Promise<{
  session_id: string
  points_held: number
  status: string
}> {
  const response = await apiClient.post<{
    session_id: string
    points_held: number
    status: string
  }>(`/sessions/${sessionId}/pay`, {}, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })
  if (!response.data) {
    throw new Error(response.message || 'Error al pagar la sesión con puntos')
  }
  return response.data
}
