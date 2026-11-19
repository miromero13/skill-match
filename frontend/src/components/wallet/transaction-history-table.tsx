import * as React from 'react'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useWalletStore } from '@/stores/wallet-store'
import type { PointTransactionType, TransactionFilterType } from '@/types/wallet'
import {
  ArrowUpRight,
  ArrowDownLeft,
  GraduationCap,
  Heart,
  Award,
  Clock,
  Inbox,
  Loader2,
} from 'lucide-react'

const FILTER_OPTIONS: { id: TransactionFilterType; label: string }[] = [
  { id: 'ALL', label: 'Todas' },
  { id: 'TOPUP', label: 'Recargas' },
  { id: 'CLASS_PAYMENT', label: 'Clases' },
  { id: 'CASHOUT', label: 'Retiros' },
  { id: 'TIP', label: 'Propinas' },
  { id: 'ADMIN_REWARD', label: 'Recompensas' },
]

function getTransactionBadge(type: PointTransactionType) {
  switch (type) {
    case 'TOPUP':
      return (
        <Badge className="bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 text-[11px] font-medium">
          <ArrowDownLeft className="w-3 h-3 mr-1" /> Recarga
        </Badge>
      )
    case 'CLASS_PAYMENT':
      return (
        <Badge className="bg-sky-500/10 hover:bg-sky-500/20 text-sky-600 dark:text-sky-400 border border-sky-500/30 text-[11px] font-medium">
          <GraduationCap className="w-3 h-3 mr-1" /> Clase
        </Badge>
      )
    case 'CASHOUT':
      return (
        <Badge className="bg-amber-500/10 hover:bg-amber-500/20 text-amber-600 dark:text-amber-400 border border-amber-500/30 text-[11px] font-medium">
          <ArrowUpRight className="w-3 h-3 mr-1" /> Retiro (Cashout)
        </Badge>
      )
    case 'TIP':
      return (
        <Badge className="bg-purple-500/10 hover:bg-purple-500/20 text-purple-600 dark:text-purple-400 border border-purple-500/30 text-[11px] font-medium">
          <Heart className="w-3 h-3 mr-1" /> Propina
        </Badge>
      )
    case 'ADMIN_REWARD':
      return (
        <Badge className="bg-yellow-500/10 hover:bg-yellow-500/20 text-yellow-600 dark:text-yellow-400 border border-yellow-500/30 text-[11px] font-medium">
          <Award className="w-3 h-3 mr-1" /> Recompensa
        </Badge>
      )
    default:
      return <Badge variant="outline">{type}</Badge>
  }
}

function formatDate(isoString: string): string {
  try {
    const d = new Date(isoString)
    return d.toLocaleDateString('es-ES', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return isoString
  }
}

export function TransactionHistoryTable() {
  const {
    transactions,
    filter,
    setFilter,
    loadTransactions,
    isLoadingTransactions,
  } = useWalletStore()

  React.useEffect(() => {
    loadTransactions()
  }, [loadTransactions])

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h3 className="text-base font-bold text-foreground flex items-center gap-2">
            <Clock className="w-4 h-4 text-emerald-500" /> Historial de Movimientos
          </h3>
          <p className="text-xs text-muted-foreground">
            Registro contable inmutable de todas las transacciones de tu billetera.
          </p>
        </div>

        {/* Filter Tabs */}
        <Tabs
          value={filter}
          onValueChange={(val) => setFilter(val as TransactionFilterType)}
          className="w-full sm:w-auto overflow-x-auto"
        >
          <TabsList className="bg-muted/50 p-1 h-auto flex flex-wrap sm:flex-nowrap">
            {FILTER_OPTIONS.map((opt) => (
              <TabsTrigger
                key={opt.id}
                value={opt.id}
                className="text-xs px-2.5 py-1 data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-sm"
              >
                {opt.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      {isLoadingTransactions ? (
        <div className="py-14 text-center space-y-3">
          <Loader2 className="w-6 h-6 animate-spin text-emerald-500 mx-auto" />
          <p className="text-xs text-muted-foreground">Cargando transacciones...</p>
        </div>
      ) : transactions.length === 0 ? (
        <div className="py-14 text-center rounded-xl border border-dashed border-border/80 bg-muted/20 space-y-3">
          <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mx-auto text-muted-foreground">
            <Inbox className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-semibold text-foreground">
              No hay movimientos registrados
            </p>
            <p className="text-xs text-muted-foreground max-w-sm mx-auto">
              Cuando realices recargas, tomes clases o solicites retiros, aparecerán listados aquí.
            </p>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-border/60 bg-card overflow-hidden shadow-sm">
          {/* Desktop Table View */}
          <div className="hidden sm:block overflow-x-auto">
            <Table>
              <TableHeader className="bg-muted/40">
                <TableRow>
                  <TableHead className="text-xs">Fecha</TableHead>
                  <TableHead className="text-xs">Tipo</TableHead>
                  <TableHead className="text-xs">Concepto / Referencia</TableHead>
                  <TableHead className="text-xs text-right">Monto</TableHead>
                  <TableHead className="text-xs text-right">Saldo Posterior</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {transactions.map((tx) => {
                  const isPositive = tx.amount > 0
                  return (
                    <TableRow key={tx.id} className="hover:bg-muted/30 transition-colors">
                      <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                        {formatDate(tx.created_at)}
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        {getTransactionBadge(tx.transaction_type)}
                      </TableCell>
                      <TableCell className="text-xs">
                        <div className="font-medium text-foreground">
                          {tx.description || 'Movimiento de saldo'}
                        </div>
                        {tx.reference_id && (
                          <div className="text-[10px] font-mono text-muted-foreground">
                            Ref: {tx.reference_id.slice(0, 12)}...
                          </div>
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-right whitespace-nowrap">
                        <span
                          className={`font-bold ${
                            isPositive
                              ? 'text-emerald-600 dark:text-emerald-400'
                              : 'text-rose-600 dark:text-rose-400'
                          }`}
                        >
                          {isPositive ? `+${tx.amount}` : tx.amount} SP
                        </span>
                      </TableCell>
                      <TableCell className="text-xs text-right font-medium text-muted-foreground whitespace-nowrap">
                        {tx.balance_after} SP
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>

          {/* Mobile Card List View */}
          <div className="sm:hidden divide-y divide-border/50">
            {transactions.map((tx) => {
              const isPositive = tx.amount > 0
              return (
                <div key={tx.id} className="p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <div>{getTransactionBadge(tx.transaction_type)}</div>
                    <span
                      className={`text-sm font-bold ${
                        isPositive
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : 'text-rose-600 dark:text-rose-400'
                      }`}
                    >
                      {isPositive ? `+${tx.amount}` : tx.amount} SP
                    </span>
                  </div>
                  <div className="text-xs font-medium text-foreground">
                    {tx.description || 'Movimiento de saldo'}
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1">
                    <span>{formatDate(tx.created_at)}</span>
                    <span>Saldo: {tx.balance_after} SP</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
