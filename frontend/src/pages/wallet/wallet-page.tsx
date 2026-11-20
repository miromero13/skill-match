import * as React from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useWalletStore } from '@/stores/wallet-store'
import { TopupModal } from '@/components/wallet/topup-modal'
import { CashoutModal } from '@/components/wallet/cashout-modal'
import { TransactionHistoryTable } from '@/components/wallet/transaction-history-table'
import {
  Coins,
  ArrowDownToLine,
  Plus,
  Lock,
  Scale,
  Percent,
  RefreshCw,
  Sparkles,
} from 'lucide-react'

export function WalletPage() {
  const {
    balance,
    escrowBalance,
    availableBalance,
    pointsPerUsd,
    loadBalance,
    isLoadingBalance,
    openTopupModal,
    openCashoutModal,
  } = useWalletStore()

  React.useEffect(() => {
    loadBalance()
  }, [loadBalance])

  const safeAvailable = availableBalance ?? balance ?? 0
  const safeEscrow = escrowBalance ?? 0
  const rate = pointsPerUsd || 10
  const availableUsd = (safeAvailable / rate).toFixed(2)
  const escrowUsd = (safeEscrow / rate).toFixed(2)

  return (
    <div className="flex-1 min-w-0 h-full overflow-y-auto p-4 lg:p-8 bg-background">
      <div className="mx-auto max-w-5xl space-y-8 pb-16">
        {/* Header Section */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border/50 pb-5">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-500">
                <Coins className="w-6 h-6 text-emerald-500" />
              </div>
              <div>
                <h1 className="text-2xl font-extrabold tracking-tight text-foreground">
                  Billetera de SkillPoints
                </h1>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Gestiona tu saldo para agendar clases formativas, recibir transferencias y retirar fondos a tu cuenta bancaria.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => loadBalance()}
              disabled={isLoadingBalance}
              className="text-xs h-9 px-3"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 mr-1.5 ${
                  isLoadingBalance ? 'animate-spin' : ''
                }`}
              />
              Actualizar
            </Button>
            <Button
              onClick={openTopupModal}
              className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs h-9 px-4 shadow-sm"
            >
              <Plus className="w-3.5 h-3.5 mr-1.5" />
              Recargar Puntos
            </Button>
          </div>
        </div>

        {/* Metric Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1: Saldo Disponible */}
          <Card className="border-border/70 bg-card shadow-xs relative overflow-hidden">
            <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-full blur-2xl -mr-6 -mt-6 pointer-events-none" />
            <CardContent className="p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                  Saldo Disponible
                </span>
                <Badge className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 text-[10px] font-semibold">
                  Activo
                </Badge>
              </div>
              <div className="flex items-baseline gap-1.5">
                <span className="text-3xl font-extrabold tracking-tight text-foreground">
                  {safeAvailable}
                </span>
                <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400">
                  SP
                </span>
              </div>
              <div className="pt-2 border-t border-border/40 flex items-center justify-between text-xs text-muted-foreground">
                <span>Equivalente</span>
                <span className="font-semibold text-foreground">
                  ${availableUsd} USD
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Card 2: Puntos en Custodia (Escrow) */}
          <Card className="border-border/70 bg-card shadow-xs">
            <CardContent className="p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                  <Lock className="w-3 h-3 text-amber-500" /> En Custodia (Escrow)
                </span>
                <Badge variant="outline" className="text-[10px]">
                  Clases
                </Badge>
              </div>
              <div className="flex items-baseline gap-1.5">
                <span className="text-3xl font-extrabold tracking-tight text-foreground">
                  {safeEscrow}
                </span>
                <span className="text-sm font-bold text-amber-600 dark:text-amber-400">
                  SP
                </span>
              </div>
              <div className="pt-2 border-t border-border/40 flex items-center justify-between text-xs text-muted-foreground">
                <span>Por completar</span>
                <span className="font-semibold text-foreground">
                  ${escrowUsd} USD
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Card 3: Tasa de Cambio Oficial */}
          <Card className="border-border/70 bg-card shadow-xs">
            <CardContent className="p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                  <Scale className="w-3 h-3 text-teal-500" /> Tasa de Cambio
                </span>
                <span className="text-[10px] text-muted-foreground">Garantizada</span>
              </div>
              <div className="flex items-baseline gap-1.5">
                <span className="text-2xl font-bold tracking-tight text-foreground">
                  10 SP
                </span>
                <span className="text-xs text-muted-foreground font-medium">
                  = $1.00 USD
                </span>
              </div>
              <div className="pt-2 border-t border-border/40 text-xs text-muted-foreground">
                Sin fluctuaciones ni especulación.
              </div>
            </CardContent>
          </Card>

          {/* Card 4: Retiros (Cashout) */}
          <Card className="border-border/70 bg-card shadow-xs">
            <CardContent className="p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                  <Percent className="w-3 h-3 text-emerald-500" /> Tarifa de Retiro
                </span>
                <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                  15% Plataforma
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  onClick={openCashoutModal}
                  variant="outline"
                  className="w-full text-xs font-semibold h-8 border-emerald-500/40 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/10"
                >
                  <ArrowDownToLine className="w-3 h-3 mr-1" />
                  Retirar Fondos
                </Button>
              </div>
              <div className="pt-1 text-[11px] text-muted-foreground">
                Mínimo de retiro: 100 SP.
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Quick Action Banners */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/5 flex items-center justify-between">
            <div className="space-y-1">
              <h4 className="text-sm font-bold text-foreground flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-emerald-500" />
                ¿Necesitas puntos para agendar una clase?
              </h4>
              <p className="text-xs text-muted-foreground">
                Recarga al instante con tarjeta de crédito o PayPal y aprende sin esperas.
              </p>
            </div>
            <Button
              size="sm"
              onClick={openTopupModal}
              className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shrink-0 ml-3"
            >
              Comprar SP
            </Button>
          </div>

          <div className="p-4 rounded-xl border border-border/70 bg-muted/20 flex items-center justify-between">
            <div className="space-y-1">
              <h4 className="text-sm font-bold text-foreground flex items-center gap-1.5">
                <ArrowDownToLine className="w-4 h-4 text-amber-500" />
                ¿Eres instructor y acumulaste puntos?
              </h4>
              <p className="text-xs text-muted-foreground">
                Transfiere tus ganancias acumuladas a tu cuenta bancaria local.
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={openCashoutModal}
              className="text-xs font-semibold shrink-0 ml-3"
            >
              Solicitar Retiro
            </Button>
          </div>
        </div>

        {/* Transaction History Section */}
        <div className="pt-2">
          <TransactionHistoryTable />
        </div>
      </div>

      {/* Modals */}
      <TopupModal />
      <CashoutModal />
    </div>
  )
}
