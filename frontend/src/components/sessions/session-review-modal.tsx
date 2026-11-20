import React, { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { useReputationStore } from "@/stores/reputation-store"
import { useAuthStore } from "@/stores/auth-store"
import {
  Star,
  Coins,
  Clock,
  BookOpen,
  Award,
  Sparkles,
  Loader2,
  CheckCircle2,
} from "lucide-react"

interface StarRatingProps {
  value: number
  onChange: (val: number) => void
  disabled?: boolean
}

function StarRating({ value, onChange, disabled }: StarRatingProps) {
  const [hovered, setHovered] = useState<number | null>(null)

  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((star) => {
        const isFilled = (hovered ?? value) >= star
        return (
          <button
            key={star}
            type="button"
            disabled={disabled}
            onClick={() => onChange(star)}
            onMouseEnter={() => setHovered(star)}
            onMouseLeave={() => setHovered(null)}
            className="p-1 text-muted-foreground/40 hover:text-amber-400 focus:outline-none transition-colors disabled:pointer-events-none"
            aria-label={`${star} estrellas`}
          >
            <Star
              className={`h-6 w-6 transition-transform ${
                isFilled
                  ? "fill-amber-400 text-amber-400 scale-110"
                  : "text-muted-foreground/30 hover:scale-105"
              }`}
            />
          </button>
        )
      })}
    </div>
  )
}

export function SessionReviewModal() {
  const {
    isReviewModalOpen,
    closeReviewModal,
    reviewState,
    isLoadingState,
    isSubmittingReview,
    isSendingTip,
    submitReview,
    sendTip,
  } = useReputationStore()

  const user = useAuthStore((s) => s.user)
  const currentBalance = user?.skillPointsBalance ?? 0

  // Form states
  const [punctuality, setPunctuality] = useState(5)
  const [pedagogy, setPedagogy] = useState(5)
  const [domain, setDomain] = useState(5)
  const [comment, setComment] = useState("")

  // Tip states: 0, 5, 10, 25 o personalizado
  const [selectedTip, setSelectedTip] = useState<number>(0)
  const [tipNote, setTipNote] = useState("")

  const overallRating = Number(((punctuality + pedagogy + domain) / 3.0).toFixed(1))
  const isSubmitting = isSubmittingReview || isSendingTip

  const handleClose = () => {
    if (isSubmitting) return
    closeReviewModal()
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // 1. Enviar la reseña pedagógica
    const review = await submitReview({
      rating_punctuality: punctuality,
      rating_pedagogy: pedagogy,
      rating_domain: domain,
      comment: comment.trim() ? comment.trim() : null,
    })

    if (!review) return

    // 2. Si seleccionó propina voluntaria > 0, enviarla
    if (selectedTip > 0) {
      await sendTip({
        amount: selectedTip,
        note: tipNote.trim() ? tipNote.trim() : null,
      })
    }

    closeReviewModal()
  }

  const tipOptions = [0, 5, 10, 25]

  return (
    <Dialog open={isReviewModalOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[500px] border-border bg-card text-card-foreground">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Badge className="bg-primary/10 text-primary border border-primary/20 font-bold uppercase tracking-wider text-[10px]">
              Feedback Bilateral
            </Badge>
          </div>
          <DialogTitle className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            Calificar Sesión de Intercambio
          </DialogTitle>
          <DialogDescription className="text-muted-foreground text-xs">
            Tu valoración ayuda a calcular el Puntaje de Confianza del tutor y construye una comunidad segura y transparente.
          </DialogDescription>
        </DialogHeader>

        {isLoadingState ? (
          <div className="flex flex-col items-center justify-center py-10 gap-2">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="text-xs text-muted-foreground">Verificando estado de la sesión...</p>
          </div>
        ) : reviewState?.has_reviewed ? (
          <div className="py-8 text-center space-y-3">
            <div className="mx-auto w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <h3 className="font-semibold text-foreground">¡Ya calificaste esta sesión!</h3>
            <p className="text-xs text-muted-foreground max-w-sm mx-auto">
              Muchas gracias por tu tiempo. Tu aporte ya fue contabilizado en el perfil de reputación de tu compañero.
            </p>
            <Button
              variant="outline"
              onClick={closeReviewModal}
              className="mt-4 border-border text-foreground hover:bg-muted"
            >
              Cerrar
            </Button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5 py-2">
            {/* Score Preview Banner */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-muted/60 border border-border">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                <span className="text-xs font-medium text-foreground">Puntaje global resultante:</span>
              </div>
              <div className="flex items-center gap-1.5 font-bold text-amber-500 dark:text-amber-400 text-base">
                <Star className="h-4 w-4 fill-amber-500 dark:fill-amber-400" />
                <span>{overallRating} / 5.0</span>
              </div>
            </div>

            {/* 3 Criterios Pedagógicos */}
            <div className="space-y-4">
              {/* 1. Puntualidad */}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
                    <Clock className="h-3.5 w-3.5 text-primary" />
                    Puntualidad y Asistencia
                  </div>
                  <p className="text-[11px] text-muted-foreground">Llegó a tiempo y respetó el horario</p>
                </div>
                <StarRating value={punctuality} onChange={setPunctuality} disabled={isSubmitting} />
              </div>

              {/* 2. Pedagogía */}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
                    <BookOpen className="h-3.5 w-3.5 text-primary" />
                    Claridad y Pedagogía
                  </div>
                  <p className="text-[11px] text-muted-foreground">Explicó con paciencia y buena metodología</p>
                </div>
                <StarRating value={pedagogy} onChange={setPedagogy} disabled={isSubmitting} />
              </div>

              {/* 3. Dominio */}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
                    <Award className="h-3.5 w-3.5 text-primary" />
                    Dominio del Tema
                  </div>
                  <p className="text-[11px] text-muted-foreground">Demostró solvencia y conocimiento práctico</p>
                </div>
                <StarRating value={domain} onChange={setDomain} disabled={isSubmitting} />
              </div>
            </div>

            {/* Comentario Cualitativo */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-foreground">
                Testimonio o comentario de la clase (opcional)
              </Label>
              <Textarea
                placeholder="Escribe unas palabras sobre tu experiencia de aprendizaje con este tutor..."
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                maxLength={500}
                disabled={isSubmitting}
                className="bg-background border-input text-foreground text-xs min-h-[75px] resize-none focus-visible:ring-primary"
              />
              <div className="flex justify-between text-[10px] text-muted-foreground">
                <span>Mínimo 10 caracteres si decides opinar</span>
                <span>{comment.length} / 500</span>
              </div>
            </div>

            <Separator className="bg-border" />

            {/* Sección de Propina Voluntaria */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <Coins className="h-4 w-4 text-amber-500 dark:text-amber-400" />
                  <span className="text-xs font-semibold text-foreground">
                    ¿Deseas dejarle una propina a tu tutor?
                  </span>
                </div>
                <span className="text-[11px] text-muted-foreground">
                  Saldo: <strong className="text-amber-500 dark:text-amber-400 font-bold">{currentBalance} SP</strong>
                </span>
              </div>

              {/* Pills de propina */}
              <div className="grid grid-cols-4 gap-2">
                {tipOptions.map((amount) => {
                  const isSelected = selectedTip === amount
                  const hasFunds = currentBalance >= amount
                  return (
                    <Button
                      key={amount}
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={isSubmitting || (!hasFunds && amount > 0)}
                      onClick={() => setSelectedTip(amount)}
                      className={`h-9 border text-xs font-bold transition-all ${
                        isSelected
                          ? "bg-[#00786F] hover:bg-[#006058] dark:bg-primary dark:hover:bg-primary/90 text-white font-bold border-transparent shadow-xs"
                          : "bg-background border-border text-foreground hover:bg-muted"
                      } ${!hasFunds && amount > 0 ? "opacity-40" : ""}`}
                    >
                      {amount === 0 ? "Sin propina" : `+${amount} SP`}
                    </Button>
                  )
                })}
              </div>

              {selectedTip > 0 && (
                <div className="space-y-1 pt-1">
                  <input
                    type="text"
                    placeholder="Dedicatoria corta (opcional, ej: ¡Gracias por tu paciencia!)"
                    value={tipNote}
                    onChange={(e) => setTipNote(e.target.value)}
                    maxLength={140}
                    disabled={isSubmitting}
                    className="w-full bg-background border border-input rounded-md px-3 py-1.5 text-[11px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary"
                  />
                  {currentBalance < selectedTip && (
                    <p className="text-[10px] text-destructive font-medium">
                      Saldo insuficiente en tu billetera ({currentBalance} SP).
                    </p>
                  )}
                </div>
              )}
            </div>

            <DialogFooter className="pt-2 gap-2 sm:gap-0">
              <Button
                type="button"
                variant="ghost"
                onClick={closeReviewModal}
                disabled={isSubmitting}
                className="text-muted-foreground hover:text-foreground hover:bg-muted text-xs"
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={isSubmitting || (comment.length > 0 && comment.length < 10) || (selectedTip > currentBalance)}
                className="bg-[#00786F] hover:bg-[#006058] dark:bg-primary dark:hover:bg-primary/90 text-white font-bold text-xs px-5 shadow-sm"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                    Publicando...
                  </>
                ) : (
                  "Publicar Calificación"
                )}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
