import * as React from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { useWalletStore } from '@/stores/wallet-store'
import type { PointPackage } from '@/types/wallet'
import {
  Coins,
  CreditCard,
  Sparkles,
  CheckCircle2,
  Loader2,
  ShieldCheck,
  Check,
} from 'lucide-react'

const DEFAULT_PACKAGES: PointPackage[] = [
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
  {
    id: 'sp_500',
    points: 500,
    price_usd: 48,
    bonus_points: 40,
    label: 'Paquete Avanzado',
    is_popular: false,
  },
  {
    id: 'sp_1000',
    points: 1000,
    price_usd: 90,
    bonus_points: 100,
    label: 'Paquete Maestro',
    is_popular: false,
  },
]

type PaymentStep = 'SELECT' | 'PROCESSING' | 'SUCCESS'

export function TopupModal() {
  const {
    isTopupModalOpen,
    closeTopupModal,
    packages,
    loadPackages,
    processTopup,
  } = useWalletStore()

  const availablePackages = (packages && packages.length > 0) ? packages : DEFAULT_PACKAGES
  const [selectedPackageId, setSelectedPackageId] = React.useState<string>(
    availablePackages[1]?.id || 'sp_250'
  )
  const [paymentMethod, setPaymentMethod] = React.useState<'card' | 'paypal'>('card')
  const [paymentStep, setPaymentStep] = React.useState<PaymentStep>('SELECT')
  const [statusMessage, setStatusMessage] = React.useState<string>('')
  const [lastPointsAdded, setLastPointsAdded] = React.useState<number>(0)

  React.useEffect(() => {
    if (isTopupModalOpen) {
      loadPackages()
      setPaymentStep('SELECT')
      setStatusMessage('')
    }
  }, [isTopupModalOpen, loadPackages])

  const selectedPkg =
    availablePackages.find((p) => p.id === selectedPackageId) || availablePackages[0]

  const handlePay = async () => {
    if (!selectedPkg) return

    setPaymentStep('PROCESSING')
    setStatusMessage('Conectando con la pasarela bancaria segura...')

    try {
      // Realistic simulation phase 1
      await new Promise((resolve) => setTimeout(resolve, 600))
      setStatusMessage('Validando método de pago y autorización...')

      // Realistic simulation phase 2
      await new Promise((resolve) => setTimeout(resolve, 600))
      setStatusMessage('Acreditando SkillPoints y registrando transacción...')

      const totalPoints = selectedPkg.points + (selectedPkg.bonus_points || 0)
      const result = await processTopup({
        package_id: selectedPkg.id,
        points: totalPoints,
        amount_usd: selectedPkg.price_usd,
        payment_method: paymentMethod === 'card' ? 'CREDIT_CARD_SIMULATED' : 'PAYPAL_SIMULATED',
      })

      setLastPointsAdded(result.points_added)
      setPaymentStep('SUCCESS')
    } catch {
      setPaymentStep('SELECT')
    }
  }

  const handleClose = () => {
    setPaymentStep('SELECT')
    closeTopupModal()
  }

  return (
    <Dialog open={isTopupModalOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-xl p-0 overflow-hidden bg-card text-card-foreground border-border shadow-2xl">
        <DialogHeader className="p-6 pb-2 border-b border-border/50 bg-muted/20">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-primary/10 text-primary">
              <Coins className="w-5 h-5 text-emerald-500 dark:text-emerald-400" />
            </div>
            <div>
              <DialogTitle className="text-xl font-bold tracking-tight">
                Recargar SkillPoints (SP)
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                Adquiere puntos oficiales para agendar clases con instructores y potenciar tus habilidades.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="p-6 space-y-6">
          {paymentStep === 'SELECT' && (
            <>
              {/* Packages Grid */}
              <div className="space-y-3">
                <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  1. Selecciona tu paquete de puntos
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {availablePackages.map((pkg) => {
                    const isSelected = pkg.id === selectedPackageId
                    const totalPoints = pkg.points + (pkg.bonus_points || 0)
                    return (
                      <Card
                        key={pkg.id}
                        role="button"
                        tabIndex={0}
                        onClick={() => setSelectedPackageId(pkg.id)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            setSelectedPackageId(pkg.id)
                          }
                        }}
                        className={`relative p-4 cursor-pointer transition-all border text-left flex flex-col justify-between ${
                          isSelected
                            ? 'border-emerald-500/80 bg-emerald-500/5 ring-2 ring-emerald-500/20 shadow-md'
                            : 'border-border/60 hover:border-border hover:bg-muted/30'
                        }`}
                      >
                        {pkg.is_popular && (
                          <div className="absolute -top-2.5 right-3">
                            <Badge className="bg-emerald-600 hover:bg-emerald-600 text-white text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 shadow-sm">
                              <Sparkles className="w-2.5 h-2.5 mr-1 inline" /> Más Popular
                            </Badge>
                          </div>
                        )}
                        <div>
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-muted-foreground">
                              {pkg.label}
                            </span>
                            {isSelected && (
                              <div className="w-4 h-4 rounded-full bg-emerald-500 text-white flex items-center justify-center">
                                <Check className="w-2.5 h-2.5 stroke-[3]" />
                              </div>
                            )}
                          </div>
                          <div className="mt-2 flex items-baseline gap-1.5">
                            <span className="text-2xl font-bold tracking-tight text-foreground">
                              {totalPoints}
                            </span>
                            <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                              SP
                            </span>
                            {pkg.bonus_points > 0 && (
                              <span className="text-[11px] font-medium text-emerald-700 dark:text-emerald-300 ml-1">
                                (+{pkg.bonus_points} bonus)
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="mt-4 pt-2.5 border-t border-border/40 flex items-center justify-between">
                          <span className="text-xs text-muted-foreground">Precio final</span>
                          <span className="text-sm font-bold text-foreground">
                            ${pkg.price_usd}.00 USD
                          </span>
                        </div>
                      </Card>
                    )
                  })}
                </div>
              </div>

              {/* Payment Methods */}
              <div className="space-y-3">
                <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  2. Método de pago simulado
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setPaymentMethod('card')}
                    className={`flex items-center gap-3 p-3 rounded-lg border text-sm font-medium transition-all ${
                      paymentMethod === 'card'
                        ? 'border-emerald-500/80 bg-emerald-500/5 text-foreground ring-1 ring-emerald-500/30'
                        : 'border-border/60 hover:bg-muted/40 text-muted-foreground'
                    }`}
                  >
                    <CreditCard className="w-4 h-4 text-emerald-500" />
                    <div className="text-left">
                      <div className="font-semibold text-xs text-foreground">Tarjeta Débito/Crédito</div>
                      <div className="text-[10px] text-muted-foreground">Visa, Mastercard</div>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => setPaymentMethod('paypal')}
                    className={`flex items-center gap-3 p-3 rounded-lg border text-sm font-medium transition-all ${
                      paymentMethod === 'paypal'
                        ? 'border-emerald-500/80 bg-emerald-500/5 text-foreground ring-1 ring-emerald-500/30'
                        : 'border-border/60 hover:bg-muted/40 text-muted-foreground'
                    }`}
                  >
                    <div className="w-4 h-4 font-bold text-xs text-blue-500 flex items-center justify-center">
                      P
                    </div>
                    <div className="text-left">
                      <div className="font-semibold text-xs text-foreground">PayPal</div>
                      <div className="text-[10px] text-muted-foreground">Saldo o Tarjetas</div>
                    </div>
                  </button>
                </div>
              </div>

              {/* Security info */}
              <div className="flex items-center gap-2 p-2.5 rounded-lg bg-muted/40 border border-border/50 text-xs text-muted-foreground">
                <ShieldCheck className="w-4 h-4 text-emerald-500 shrink-0" />
                <span>
                  Transacción protegida por pasarela con cifrado bancario TLS de 256 bits y acreditación inmediata.
                </span>
              </div>

              {/* Action Button */}
              <div className="flex items-center justify-end gap-3 pt-2">
                <Button variant="outline" onClick={handleClose} className="text-xs">
                  Cancelar
                </Button>
                <Button
                  onClick={handlePay}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs px-5 shadow-sm"
                >
                  <CreditCard className="w-3.5 h-3.5 mr-1.5" />
                  Pagar ${selectedPkg?.price_usd}.00 USD
                </Button>
              </div>
            </>
          )}

          {paymentStep === 'PROCESSING' && (
            <div className="py-10 text-center space-y-5">
              <div className="relative inline-flex items-center justify-center">
                <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center animate-pulse">
                  <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
                </div>
              </div>
              <div className="space-y-1.5 max-w-sm mx-auto">
                <h4 className="font-bold text-base text-foreground">
                  Procesando Pago Seguro
                </h4>
                <p className="text-xs text-muted-foreground transition-all">
                  {statusMessage}
                </p>
              </div>
              <div className="flex items-center justify-center gap-1.5 text-[11px] text-muted-foreground">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                <span>Por favor no cierres esta ventana...</span>
              </div>
            </div>
          )}

          {paymentStep === 'SUCCESS' && (
            <div className="py-8 text-center space-y-5">
              <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-500">
                <CheckCircle2 className="w-10 h-10 text-emerald-500" />
              </div>
              <div className="space-y-1.5">
                <h4 className="font-bold text-lg text-foreground">
                  ¡Recarga Completada con Éxito!
                </h4>
                <p className="text-sm text-muted-foreground">
                  Se han acreditado{' '}
                  <span className="font-bold text-emerald-600 dark:text-emerald-400">
                    +{lastPointsAdded} SkillPoints
                  </span>{' '}
                  a tu billetera.
                </p>
                <p className="text-xs text-muted-foreground">
                  Hemos enviado una notificación en pantalla y registrado el comprobante de auditoría.
                </p>
              </div>
              <Button
                onClick={handleClose}
                className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs px-6"
              >
                Listo, Continuar
              </Button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
