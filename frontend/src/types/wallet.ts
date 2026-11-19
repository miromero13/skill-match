export type PointTransactionType =
  | 'TOPUP'
  | 'CLASS_PAYMENT'
  | 'TIP'
  | 'CASHOUT'
  | 'ADMIN_REWARD'

export type CashoutStatus = 'PENDING' | 'APPROVED' | 'REJECTED'

export interface WalletBalance {
  balance: number
  escrow_balance: number
  available_balance: number
  currency: string
  points_per_usd: number
}

export interface PointPackage {
  package_id?: string
  id?: string
  name?: string
  label?: string
  points: number
  price_usd: number
  bonus_points: number
  total_points?: number
  is_popular: boolean
  description?: string
}

export interface TopupPayload {
  package_id: string
  points: number
  amount_usd: number
  payment_method?: string
}

export interface TopupResult {
  transaction_id: string
  points_added: number
  new_balance: number
  payment_reference: string
  status: string
}

export interface CashoutCalculation {
  points: number
  gross_amount_usd: number
  fee_percentage: number
  platform_fee_usd: number
  net_amount_usd: number
  min_points: number
  points_per_usd: number
  eligible: boolean
}

export interface CashoutPayload {
  points: number
  bank_name: string
  account_type: 'CORRIENTE' | 'AHORROS' | string
  account_number: string
  account_holder_name: string
  account_holder_id: string
}

export interface CashoutRequest {
  id: string
  wallet_id: string
  points: number
  gross_usd: number
  platform_fee_usd: number
  net_usd: number
  status: CashoutStatus
  bank_name: string
  account_type: string
  account_number_masked: string
  created_at: string
}

export interface PointTransaction {
  id: string
  transaction_type: PointTransactionType
  amount: number
  balance_after: number
  reference_id?: string | null
  description?: string | null
  created_at: string
}

export type TransactionFilterType = 'ALL' | PointTransactionType
