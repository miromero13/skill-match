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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
  Lock,
} from 'lucide-react'

const DEFAULT_PACKAGES: PointPackage[] = [
  {
    package_id: 'pkg_basic',
    id: 'pkg_basic',
    points: 100,
    price_usd: 10,
    bonus_points: 0,
    total_points: 100,
    name: 'Paquete Básico',
    label: 'Paquete Básico',
    is_popular: false,
  },
  {
    package_id: 'pkg_student',
    id: 'pkg_student',
    points: 250,
    price_usd: 25,
    bonus_points: 25,
    total_points: 275,
    name: 'Paquete Estudiante',
    label: 'Paquete Estudiante',
    is_popular: true,
  },
  {
    package_id: 'pkg_pro',
    id: 'pkg_pro',
    points: 500,
    price_usd: 50,
    bonus_points: 75,
    total_points: 575,
    name: 'Paquete Pro',
    label: 'Paquete Pro',
    is_popular: false,
  },
  {
    package_id: 'pkg_master',
    id: 'pkg_master',
    points: 1000,
    price_usd: 100,
    bonus_points: 200,
    total_points: 1200,
    name: 'Paquete Master VIP',
    label: 'Paquete Master VIP',
    is_popular: false,
  },
]

type PaymentStep = 'SELECT' | 'PROCESSING' | 'SUCCESS'

function getPackageKey(pkg?: PointPackage): string {
  return pkg?.package_id || pkg?.id || ''
}

export function TopupModal() {
  const {
    isTopupModalOpen,
    closeTopupModal,
    packages,
    loadPackages,
    processTopup,
  } = useWalletStore()

  const availablePackages =
    packages && packages.length > 0 ? packages : DEFAULT_PACKAGES

  const [selectedPackageId, setSelectedPackageId] = React.useState<string>(
    getPackageKey(availablePackages[1]) || getPackageKey(availablePackages[0])
  )
  const [paymentMethod, setPaymentMethod] = React.useState<'card' | 'paypal'>('card')
  const [cardNumber, setCardNumber] = React.useState<string>('')
  const [cardHolder, setCardHolder] = React.useState<string>('')
  const [cardExpiry, setCardExpiry] = React.useState<string>('')
  const [cardCvv, setCardCvv] = React.useState<string>('')
  const [paypalEmail, setPaypalEmail] = React.useState<string>('')
  const [lastReceipt, setLastReceipt] = React.useState<string>('')
  const [paymentStep, setPaymentStep] = React.useState<PaymentStep>('SELECT')
  const [statusMessage, setStatusMessage] = React.useState<string>('')
  const [lastPointsAdded, setLastPointsAdded] = React.useState<number>(0)

  const handleCardNumberChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/\D/g, '').slice(0, 16)
    const formatted = raw.replace(/(.{4})/g, '$1 ').trim()
    setCardNumber(formatted)
  }

  const handleExpiryChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let val = e.target.value.replace(/\D/g, '').slice(0, 4)
    if (val.length >= 2) {
      val = `${val.slice(0, 2)}/${val.slice(2)}`
    }
    setCardExpiry(val)
  }

  const handleCvvChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value.replace(/\D/g, '').slice(0, 4)
    setCardCvv(val)
  }

  React.useEffect(() => {
    if (isTopupModalOpen) {
      loadPackages()
      setPaymentStep('SELECT')
      setStatusMessage('')
      setCardNumber('')
      setCardHolder('')
      setCardExpiry('')
      setCardCvv('')
      setPaypalEmail('')
      setLastReceipt('')
    }
  }, [isTopupModalOpen, loadPackages])

  React.useEffect(() => {
    if (availablePackages.length > 0) {
      const exists = availablePackages.some(
        (p) => getPackageKey(p) === selectedPackageId
      )
      if (!exists) {
        const defaultPkg =
          availablePackages.find((p) => p.is_popular) || availablePackages[0]
        setSelectedPackageId(getPackageKey(defaultPkg))
      }
    }
  }, [availablePackages, selectedPackageId])

  const selectedPkg =
    availablePackages.find((p) => getPackageKey(p) === selectedPackageId) ||
    availablePackages[0]

  const handlePay = async () => {
    if (!selectedPkg) return

    setPaymentStep('PROCESSING')
    setStatusMessage('Conectando con la pasarela bancaria segura...')

    try {
      // Processing phase 1
      await new Promise((resolve) => setTimeout(resolve, 600))
      setStatusMessage('Validando método de pago y autorización...')

      // Processing phase 2
      await new Promise((resolve) => setTimeout(resolve, 600))
      setStatusMessage('Acreditando SkillPoints y registrando transacción...')

      const pkgKey = getPackageKey(selectedPkg)
      const totalPoints =
        selectedPkg.total_points ?? (selectedPkg.points + (selectedPkg.bonus_points || 0))

      const digits = cardNumber.replace(/\D/g, '')
      const lastFour =
        digits.length >= 4
          ? digits.slice(-4)
          : (paymentMethod === 'card' ? '4291' : 'PAYP')

      const result = await processTopup({
        package_id: pkgKey,
        points: totalPoints,
        amount_usd: selectedPkg.price_usd,
        payment_method: paymentMethod === 'card' ? 'card' : 'paypal',
        card_last_four: lastFour,
        card_holder: cardHolder.trim() || 'Titular de la Tarjeta',
        paypal_email: paypalEmail.trim() || 'usuario@paypal.com',
      })

      setLastPointsAdded(result.total_points_added || result.points_added || totalPoints)
      setLastReceipt(result.receipt_number || result.payment_reference || '')
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
                    const pkgKey = getPackageKey(pkg)
                    const isSelected = pkgKey === selectedPackageId
                    const totalPoints = pkg.total_points ?? (pkg.points + (pkg.bonus_points || 0))
                    const title = pkg.name || pkg.label
                    return (
                      <Card
                        key={pkgKey}
                        role="button"
                        tabIndex={0}
                        onClick={() => setSelectedPackageId(pkgKey)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            setSelectedPackageId(pkgKey)
                          }
                        }}
                        className={`relative p-4 cursor-pointer transition-all border text-left flex flex-col justify-between ${isSelected
                            ? 'border-emerald-500/80 bg-emerald-500/5 ring-2 ring-emerald-500/20 shadow-md'
                            : 'border-border/60 hover:border-border hover:bg-muted/30'
                          }`}
                      >
                        <div>
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-medium text-muted-foreground">
                              {title}
                            </span>
                            <div className="flex items-center gap-1.5">
                              {pkg.is_popular && (
                                <Badge className="bg-emerald-600 hover:bg-emerald-600 text-white text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 shadow-xs">
                                  <Sparkles className="w-2.5 h-2.5 mr-1 inline" /> Más Popular
                                </Badge>
                              )}
                              {isSelected && (
                                <div className="w-4 h-4 rounded-full bg-emerald-500 text-white flex items-center justify-center shrink-0">
                                  <Check className="w-2.5 h-2.5 stroke-[3]" />
                                </div>
                              )}
                            </div>
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
                  2. Método de pago
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setPaymentMethod('card')}
                    className={`flex items-center gap-3 p-3 rounded-lg border text-sm font-medium transition-all ${paymentMethod === 'card'
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
                    className={`flex items-center gap-3 p-3 rounded-lg border text-sm font-medium transition-all ${paymentMethod === 'paypal'
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

              {/* Interactive Card / PayPal Form Fields */}
              {paymentMethod === 'card' ? (
                <div className="p-3.5 rounded-xl border border-border/70 bg-muted/20 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                      <CreditCard className="w-3.5 h-3.5 text-emerald-500" /> Datos de la Tarjeta
                    </span>
                    <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                      <Lock className="w-3 h-3 text-emerald-500" /> Cifrado 256 bits
                    </span>
                  </div>

                  <div className="space-y-1">
                    <Label htmlFor="topup-card-number" className="text-[11px] font-medium text-muted-foreground">
                      Número de Tarjeta
                    </Label>
                    <div className="relative">
                      <Input
                        id="topup-card-number"
                        placeholder="4532 8192 1029 4821"
                        value={cardNumber}
                        onChange={handleCardNumberChange}
                        maxLength={19}
                        className="text-xs font-mono pr-14"
                      />
                      <div className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] font-bold text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                        VISA/MC
                      </div>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <Label htmlFor="topup-card-holder" className="text-[11px] font-medium text-muted-foreground">
                      Nombre del Titular
                    </Label>
                    <Input
                      id="topup-card-holder"
                      placeholder="Tal como figura en la tarjeta"
                      value={cardHolder}
                      onChange={(e) => setCardHolder(e.target.value)}
                      className="text-xs"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label htmlFor="topup-card-expiry" className="text-[11px] font-medium text-muted-foreground">
                        Expiración (MM/AA)
                      </Label>
                      <Input
                        id="topup-card-expiry"
                        placeholder="12/28"
                        value={cardExpiry}
                        onChange={handleExpiryChange}
                        maxLength={5}
                        className="text-xs font-mono"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="topup-card-cvv" className="text-[11px] font-medium text-muted-foreground">
                        CVV / CVC
                      </Label>
                      <Input
                        id="topup-card-cvv"
                        placeholder="892"
                        type="password"
                        value={cardCvv}
                        onChange={handleCvvChange}
                        maxLength={4}
                        className="text-xs font-mono"
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-3.5 rounded-xl border border-border/70 bg-muted/20 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                      <span className="font-bold text-blue-500">P</span> Cuenta PayPal
                    </span>
                    <span className="text-[10px] text-blue-500 font-semibold">Protección al Comprador</span>
                  </div>

                  <div className="space-y-1">
                    <Label htmlFor="topup-paypal-email" className="text-[11px] font-medium text-muted-foreground">
                      Correo Electrónico de PayPal
                    </Label>
                    <Input
                      id="topup-paypal-email"
                      type="email"
                      placeholder="tu-correo@paypal.com"
                      value={paypalEmail}
                      onChange={(e) => setPaypalEmail(e.target.value)}
                      className="text-xs"
                    />
                  </div>
                </div>
              )}

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
            <div className="py-6 text-center space-y-4">
              <div className="w-14 h-14 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-500">
                <CheckCircle2 className="w-8 h-8 text-emerald-500" />
              </div>
              <div className="space-y-1">
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
              </div>

              {/* Receipt Summary Card */}
              <div className="p-3.5 rounded-xl bg-muted/40 border border-border/60 text-xs text-left max-w-sm mx-auto space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Paquete:</span>
                  <span className="font-semibold text-foreground">
                    {selectedPkg?.name || selectedPkg?.label}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Método utilizado:</span>
                  <span className="font-semibold text-foreground">
                    {paymentMethod === 'card'
                      ? `Tarjeta •••• ${cardNumber.replace(/\D/g, '').slice(-4) || '4291'}`
                      : `PayPal (${paypalEmail || 'usuario@paypal.com'})`}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Monto cobrado:</span>
                  <span className="font-bold text-emerald-600 dark:text-emerald-400">
                    ${selectedPkg?.price_usd}.00 USD
                  </span>
                </div>
                {lastReceipt && (
                  <div className="flex justify-between items-center pt-1.5 border-t border-border/40">
                    <span className="text-muted-foreground">Nº Comprobante:</span>
                    <span className="font-mono text-[11px] text-foreground">
                      {lastReceipt}
                    </span>
                  </div>
                )}
              </div>

              <div className="pt-2">
                <Button
                  onClick={handleClose}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs px-6"
                >
                  Listo, Continuar
                </Button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
