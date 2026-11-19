import * as React from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useWalletStore } from '@/stores/wallet-store'
import type { CashoutRequest } from '@/types/wallet'
import {
  ArrowDownToLine,
  Building2,
  CheckCircle2,
  AlertCircle,
  ShieldAlert,
  Loader2,
} from 'lucide-react'

export function CashoutModal() {
  const {
    isCashoutModalOpen,
    closeCashoutModal,
    availableBalance,
    pointsPerUsd,
    processCashout,
    isProcessingCashout,
  } = useWalletStore()

  const [pointsInput, setPointsInput] = React.useState<string>('100')
  const [bankName, setBankName] = React.useState<string>('')
  const [accountType, setAccountType] = React.useState<string>('AHORROS')
  const [accountNumber, setAccountNumber] = React.useState<string>('')
  const [holderName, setHolderName] = React.useState<string>('')
  const [holderId, setHolderId] = React.useState<string>('')

  const [completedRequest, setCompletedRequest] = React.useState<CashoutRequest | null>(
    null
  )

  React.useEffect(() => {
    if (isCashoutModalOpen) {
      setPointsInput(availableBalance >= 100 ? '100' : '0')
      setCompletedRequest(null)
    }
  }, [isCashoutModalOpen, availableBalance])

  const pointsNum = parseInt(pointsInput, 10) || 0
  const rate = pointsPerUsd || 10
  const grossUsd = pointsNum / rate
  const feePercentage = 15
  const feeUsd = Number((grossUsd * (feePercentage / 100)).toFixed(2))
  const netUsd = Number((grossUsd - feeUsd).toFixed(2))

  const isMinMet = pointsNum >= 100
  const isBalanceSufficient = pointsNum <= availableBalance
  const isFormValid =
    isMinMet &&
    isBalanceSufficient &&
    bankName.trim().length >= 2 &&
    accountNumber.trim().length >= 6 &&
    holderName.trim().length >= 3 &&
    holderId.trim().length >= 4

  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!isFormValid || isProcessingCashout) return

    try {
      const request = await processCashout({
        points: pointsNum,
        bank_name: bankName.trim(),
        account_type: accountType,
        account_number: accountNumber.trim(),
        account_holder_name: holderName.trim(),
        account_holder_id: holderId.trim(),
      })
      setCompletedRequest(request)
    } catch {
      // Error handled by store/apiClient
    }
  }

  const handleClose = () => {
    setCompletedRequest(null)
    closeCashoutModal()
  }

  return (
    <Dialog open={isCashoutModalOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-lg p-0 overflow-hidden bg-card text-card-foreground border-border shadow-2xl">
        <DialogHeader className="p-6 pb-3 border-b border-border/50 bg-muted/20">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-amber-500/10 text-amber-500">
              <ArrowDownToLine className="w-5 h-5 text-amber-500" />
            </div>
            <div>
              <DialogTitle className="text-xl font-bold tracking-tight">
                Retirar Fondos (Cashout)
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                Convierte tus SkillPoints acumulados por dictar clases o recompensas a dinero real en tu cuenta bancaria.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {!completedRequest ? (
          <form onSubmit={handleConfirm} className="p-6 space-y-5">
            {/* Points input and live calculation card */}
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs">
                <Label htmlFor="points-input" className="font-semibold text-foreground">
                  Cantidad de SkillPoints a retirar
                </Label>
                <span className="text-muted-foreground">
                  Disponible:{' '}
                  <span className="font-bold text-foreground">
                    {availableBalance} SP
                  </span>
                </span>
              </div>

              <div className="relative">
                <Input
                  id="points-input"
                  type="number"
                  min="100"
                  max={availableBalance}
                  step="10"
                  value={pointsInput}
                  onChange={(e) => setPointsInput(e.target.value)}
                  className="pr-14 text-base font-bold"
                  placeholder="Mínimo 100 SP"
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-bold text-emerald-600 dark:text-emerald-400">
                  SP
                </div>
              </div>

              {/* Dynamic Calculation breakdown */}
              <div className="p-3.5 rounded-xl bg-muted/40 border border-border/50 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Total Bruto ({pointsNum} SP / 10)</span>
                  <span className="font-semibold text-foreground">
                    ${grossUsd.toFixed(2)} USD
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground flex items-center gap-1">
                    Comisión de plataforma ({feePercentage}%)
                  </span>
                  <span className="font-semibold text-amber-600 dark:text-amber-400">
                    -${feeUsd.toFixed(2)} USD
                  </span>
                </div>
                <div className="pt-2 border-t border-border/40 flex items-center justify-between text-sm">
                  <span className="font-bold text-foreground">Monto neto a transferir</span>
                  <span className="text-base font-extrabold text-emerald-600 dark:text-emerald-400">
                    ${netUsd.toFixed(2)} USD
                  </span>
                </div>
              </div>

              {!isMinMet && (
                <div className="flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  <span>El retiro mínimo permitido es de 100 SP ($10.00 USD brutos).</span>
                </div>
              )}

              {!isBalanceSufficient && (
                <div className="flex items-center gap-1.5 text-xs text-destructive">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  <span>No cuentas con saldo suficiente en tu billetera disponible.</span>
                </div>
              )}
            </div>

            {/* Bank details */}
            <div className="space-y-3 pt-1 border-t border-border/40">
              <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5" /> Datos de la cuenta bancaria de destino
              </label>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor="bank-name" className="text-[11px] font-medium text-muted-foreground">
                    Entidad Bancaria
                  </Label>
                  <Input
                    id="bank-name"
                    placeholder="Ej. Banco Santander / BCP"
                    value={bankName}
                    onChange={(e) => setBankName(e.target.value)}
                    className="text-xs"
                    required
                  />
                </div>

                <div className="space-y-1">
                  <Label htmlFor="account-type" className="text-[11px] font-medium text-muted-foreground">
                    Tipo de Cuenta
                  </Label>
                  <Select value={accountType} onValueChange={setAccountType}>
                    <SelectTrigger id="account-type" className="text-xs">
                      <SelectValue placeholder="Selecciona tipo" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="AHORROS">Cuenta de Ahorros</SelectItem>
                      <SelectItem value="CORRIENTE">Cuenta Corriente</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-1">
                <Label htmlFor="account-number" className="text-[11px] font-medium text-muted-foreground">
                  Número de Cuenta o IBAN / CLABE
                </Label>
                <Input
                  id="account-number"
                  placeholder="Ej. 123456789012"
                  value={accountNumber}
                  onChange={(e) => setAccountNumber(e.target.value)}
                  className="text-xs"
                  required
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor="holder-name" className="text-[11px] font-medium text-muted-foreground">
                    Nombre del Titular
                  </Label>
                  <Input
                    id="holder-name"
                    placeholder="Tal como figura en el banco"
                    value={holderName}
                    onChange={(e) => setHolderName(e.target.value)}
                    className="text-xs"
                    required
                  />
                </div>

                <div className="space-y-1">
                  <Label htmlFor="holder-id" className="text-[11px] font-medium text-muted-foreground">
                    DNI / CI / Pasaporte
                  </Label>
                  <Input
                    id="holder-id"
                    placeholder="Documento de identidad"
                    value={holderId}
                    onChange={(e) => setHolderId(e.target.value)}
                    className="text-xs"
                    required
                  />
                </div>
              </div>
            </div>

            {/* Antifraud disclaimer */}
            <div className="flex items-start gap-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-700 dark:text-amber-300">
              <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
              <span>
                Por políticas antifraude de SkillMatch, los retiros pasan por validación previa y se acreditan en tu banco en 24 a 48 horas laborables.
              </span>
            </div>

            {/* Footer Buttons */}
            <div className="flex items-center justify-end gap-3 pt-2">
              <Button type="button" variant="outline" onClick={handleClose} className="text-xs">
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={!isFormValid || isProcessingCashout}
                className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs px-5 shadow-sm"
              >
                {isProcessingCashout ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                    Registrando Solicitud...
                  </>
                ) : (
                  <>
                    <ArrowDownToLine className="w-3.5 h-3.5 mr-1.5" />
                    Solicitar Retiro (${netUsd.toFixed(2)} USD)
                  </>
                )}
              </Button>
            </div>
          </form>
        ) : (
          <div className="p-8 text-center space-y-5">
            <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-500">
              <CheckCircle2 className="w-10 h-10 text-emerald-500" />
            </div>
            <div className="space-y-2">
              <h4 className="font-bold text-lg text-foreground">
                ¡Solicitud de Retiro Registrada!
              </h4>
              <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                Hemos bloqueado los{' '}
                <span className="font-semibold text-foreground">
                  {completedRequest.points} SP
                </span>{' '}
                solicitados. Recibirás{' '}
                <span className="font-bold text-emerald-600 dark:text-emerald-400">
                  ${completedRequest.net_usd.toFixed(2)} USD
                </span>{' '}
                en tu cuenta{' '}
                <span className="font-medium text-foreground">
                  {completedRequest.bank_name} ({completedRequest.account_number_masked})
                </span>
                .
              </p>
              <div className="p-3 rounded-lg bg-muted/40 border border-border/50 text-xs text-muted-foreground text-left max-w-xs mx-auto space-y-1">
                <div>
                  <span className="font-semibold text-foreground">ID Solicitud:</span>{' '}
                  <span className="font-mono text-[11px]">{completedRequest.id.slice(0, 8)}...</span>
                </div>
                <div>
                  <span className="font-semibold text-foreground">Estado:</span>{' '}
                  <span className="text-amber-500 font-bold">En revisión antifraude</span>
                </div>
              </div>
            </div>
            <Button
              onClick={handleClose}
              className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs px-6"
            >
              Cerrar y Ver Historial
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
