import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { WalletPage } from '@/pages/wallet/wallet-page'
import { TopupModal } from '@/components/wallet/topup-modal'
import { CashoutModal } from '@/components/wallet/cashout-modal'
import { TransactionHistoryTable } from '@/components/wallet/transaction-history-table'
import { useWalletStore } from '@/stores/wallet-store'
import { useAuthStore } from '@/stores/auth-store'
import * as walletService from '@/services/wallet-service'

vi.mock('@/services/wallet-service', () => ({
  getWalletBalance: vi.fn(),
  getPointPackages: vi.fn(),
  topupPoints: vi.fn(),
  calculateCashout: vi.fn(),
  requestCashout: vi.fn(),
  getWalletTransactions: vi.fn(),
  paySessionEscrow: vi.fn(),
}))

describe('Wallet UI & Store Suite (SM-54 / HU-42)', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    useAuthStore.getState().login(
      {
        id: 'member-123',
        fullName: 'Estudiante Prueba',
        email: 'estudiante@skillmatch.io',
        role: 'MEMBER',
        skillPointsBalance: 350,
        reputationScore: 4.8,
        trustLevel: 3,
        isVerified: true,
      },
      'fake-token',
      'fake-refresh'
    )

    useWalletStore.setState({
      balance: 350,
      escrowBalance: 50,
      availableBalance: 300,
      pointsPerUsd: 10,
      packages: [
        {
          id: 'sp_100',
          points: 100,
          price_usd: 10,
          bonus_points: 0,
          label: 'Paquete Inicial',
          is_popular: false,
        },
        {
          id: 'sp_250',
          points: 250,
          price_usd: 25,
          bonus_points: 15,
          label: 'Paquete Formativo',
          is_popular: true,
        },
      ],
      transactions: [
        {
          id: 'tx-1',
          transaction_type: 'TOPUP',
          amount: 250,
          balance_after: 250,
          reference_id: 'ref-1234567890',
          description: 'Recarga de paquete formativo',
          created_at: '2026-11-19T10:00:00Z',
        },
        {
          id: 'tx-2',
          transaction_type: 'CLASS_PAYMENT',
          amount: -50,
          balance_after: 200,
          reference_id: 'session-abc-xyz',
          description: 'Pago por clase de programación',
          created_at: '2026-11-19T11:00:00Z',
        },
      ],
      filter: 'ALL',
      isLoadingBalance: false,
      isLoadingPackages: false,
      isLoadingTransactions: false,
      isTopupModalOpen: false,
      isCashoutModalOpen: false,
      isProcessingPayment: false,
      isProcessingCashout: false,
    })

    vi.mocked(walletService.getWalletBalance).mockResolvedValue({
      balance: 350,
      escrow_balance: 50,
      available_balance: 300,
      currency: 'SkillPoints',
      points_per_usd: 10,
    })

    vi.mocked(walletService.getWalletTransactions).mockResolvedValue([
      {
        id: 'tx-1',
        transaction_type: 'TOPUP',
        amount: 250,
        balance_after: 250,
        reference_id: 'ref-1234567890',
        description: 'Recarga de paquete formativo',
        created_at: '2026-11-19T10:00:00Z',
      },
    ])
  })

  it('renders WalletPage with available balance, escrow, and key rates', async () => {
    render(
      <MemoryRouter>
        <WalletPage />
      </MemoryRouter>
    )

    // Check main title
    expect(screen.getByText('Billetera de SkillPoints')).toBeInTheDocument()

    // Check metrics
    expect(screen.getByText('Saldo Disponible')).toBeInTheDocument()
    expect(screen.getByText('300')).toBeInTheDocument() // available balance
    expect(screen.getByText('$30.00 USD')).toBeInTheDocument()

    expect(screen.getByText('En Custodia (Escrow)')).toBeInTheDocument()
    expect(screen.getByText('50')).toBeInTheDocument() // escrow balance
    expect(screen.getByText('$5.00 USD')).toBeInTheDocument()

    expect(screen.getByText('Tasa de Cambio')).toBeInTheDocument()
    expect(screen.getByText('10 SP')).toBeInTheDocument()
    expect(screen.getByText('= $1.00 USD')).toBeInTheDocument()

    expect(screen.getByText('15% Plataforma')).toBeInTheDocument()

    // Check CTA buttons
    expect(screen.getByRole('button', { name: /Recargar Puntos/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Retirar Fondos/i })).toBeInTheDocument()
  })

  it('opens TopupModal and allows selecting packages and payment methods with realistic inputs', async () => {
    useWalletStore.setState({ isTopupModalOpen: true })

    render(
      <MemoryRouter>
        <TopupModal />
      </MemoryRouter>
    )

    expect(screen.getByText('Recargar SkillPoints (SP)')).toBeInTheDocument()
    expect(screen.getByText('Paquete Formativo')).toBeInTheDocument()
    expect(screen.getByText('Más Popular')).toBeInTheDocument()
    expect(screen.getByText('$25.00 USD')).toBeInTheDocument()

    // Select different package
    const initialPkg = screen.getByText('Paquete Inicial')
    fireEvent.click(initialPkg)

    expect(screen.getByRole('button', { name: /Pagar \$10\.00 USD/i })).toBeInTheDocument()

    // Test card number input accepts fake / test data
    const cardInput = screen.getByLabelText(/Número de Tarjeta/i)
    fireEvent.change(cardInput, { target: { value: '4532819210294821' } })
    expect(cardInput).toHaveValue('4532 8192 1029 4821')

    // Switch to PayPal
    const paypalBtn = screen.getByRole('button', { name: /PayPal/i })
    fireEvent.click(paypalBtn)
    expect(screen.getByLabelText(/Correo Electrónico de PayPal/i)).toBeInTheDocument()
  })

  it('opens CashoutModal and dynamically calculates 15% fee and net USD', async () => {
    useWalletStore.setState({ isCashoutModalOpen: true, availableBalance: 300 })

    render(
      <MemoryRouter>
        <CashoutModal />
      </MemoryRouter>
    )

    expect(screen.getByText('Retirar Fondos (Cashout)')).toBeInTheDocument()
    expect(screen.getByText('300 SP')).toBeInTheDocument()

    const pointsInput = screen.getByLabelText(/Cantidad de SkillPoints a retirar/i)
    expect(pointsInput).toHaveValue(100)

    // With 100 SP: gross = $10.00, 15% fee = $1.50, net = $8.50
    expect(screen.getByText('$10.00 USD')).toBeInTheDocument()
    expect(screen.getByText('-$1.50 USD')).toBeInTheDocument()
    expect(screen.getByText('$8.50 USD')).toBeInTheDocument()

    // Change input to 200 SP: gross = $20.00, fee = $3.00, net = $17.00
    fireEvent.change(pointsInput, { target: { value: '200' } })

    expect(screen.getByText('$20.00 USD')).toBeInTheDocument()
    expect(screen.getByText('-$3.00 USD')).toBeInTheDocument()
    expect(screen.getByText('$17.00 USD')).toBeInTheDocument()
  })

  it('renders TransactionHistoryTable with filters and badges', async () => {
    render(
      <MemoryRouter>
        <TransactionHistoryTable />
      </MemoryRouter>
    )

    expect(screen.getByText('Historial de Movimientos')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Todas/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Recargas/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Retiros/i })).toBeInTheDocument()

    // Check items from store/service (desktop & mobile views render responsive items)
    await waitFor(() => {
      expect(screen.getAllByText('Recarga de paquete formativo').length).toBeGreaterThan(0)
    })
    expect(screen.getAllByText('+250 SP').length).toBeGreaterThan(0)

    // Test filter change
    await act(async () => {
      await useWalletStore.getState().setFilter('CLASS_PAYMENT')
    })
    expect(screen.getByText(/No hay movimientos de clases registrados/i)).toBeInTheDocument()

    // Switch back to Todas
    await act(async () => {
      await useWalletStore.getState().setFilter('ALL')
    })
    expect(screen.getAllByText('Recarga de paquete formativo').length).toBeGreaterThan(0)
  })
})
