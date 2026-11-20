import { useState } from "react"
import { ShieldAlert, AlertTriangle, ArrowRight, Loader2, Check } from "lucide-react"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Checkbox } from "@/components/ui/checkbox"
import { useUserModerationStore } from "@/stores/user-moderation-store"
import { toast } from "sonner"
import {
    REPORT_REASON_LABELS,
    type ReportReason,
} from "@/types/user-moderation"

interface ReportBlockDialogProps {
    targetUserId: string
    targetUserName: string
    open: boolean
    onOpenChange: (open: boolean) => void
    onSuccess?: () => void
}

export function ReportBlockDialog({
    targetUserId,
    targetUserName,
    open,
    onOpenChange,
    onSuccess,
}: ReportBlockDialogProps) {
    const { reportUser } = useUserModerationStore()
    const [selectedReason, setSelectedReason] = useState<ReportReason>("HARASSMENT")
    const [description, setDescription] = useState("")
    const [blockUserOption, setBlockUserOption] = useState(true)
    const [submitting, setSubmitting] = useState(false)

    const reasons: ReportReason[] = [
        "HARASSMENT",
        "PAYMENT_OUTSIDE",
        "NO_SHOW",
        "SPAM_FRAUD",
        "OTHER",
    ]

    const handleSubmit = async () => {
        if (!description.trim() || description.trim().length < 10) {
            toast.error("Por favor ingresa un detalle adicional explicativo de al menos 10 caracteres.")
            return
        }

        setSubmitting(true)
        try {
            const result = await reportUser(targetUserId, {
                reason: selectedReason,
                description: description.trim(),
                block_user: blockUserOption,
            })

            if (result) {
                toast.success(
                    `Reporte contra ${targetUserName} enviado a moderación.` +
                    (blockUserOption ? " El usuario fue bloqueado preventivamente." : "")
                )
                onOpenChange(false)
                setDescription("")
                onSuccess?.()
            } else {
                toast.error("No se pudo enviar el reporte. Por favor intenta nuevamente.")
            }
        } finally {
            setSubmitting(false)
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md max-h-[90dvh] overflow-y-auto" data-testid="report-block-dialog">
                <DialogHeader>
                    <div className="flex items-center gap-2 text-destructive">
                        <ShieldAlert className="h-5 w-5 shrink-0" />
                        <DialogTitle className="text-sm sm:text-base font-bold uppercase tracking-tight">
                            Bloquear y Reportar a {targetUserName}
                        </DialogTitle>
                    </div>
                    <DialogDescription className="text-xs text-muted-foreground">
                        Al confirmar, se anulará todo contacto, chat y sugerencias de trueque con este usuario.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-2">
                    {/* Selección de motivo de infracción */}
                    <div className="space-y-2">
                        <Label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                            Seleccioná el motivo de la infracción:
                        </Label>
                        <div className="space-y-1.5">
                            {reasons.map((reason) => {
                                const isSelected = selectedReason === reason
                                return (
                                    <div
                                        key={reason}
                                        onClick={() => setSelectedReason(reason)}
                                        className={`flex items-start gap-2.5 p-2.5 rounded-lg border text-xs cursor-pointer transition-colors ${
                                            isSelected
                                                ? "border-destructive/60 bg-destructive/10 text-foreground"
                                                : "border-border hover:bg-muted/50 text-muted-foreground"
                                        }`}
                                        data-testid={`reason-option-${reason}`}
                                    >
                                        <div
                                            className={`h-4 w-4 rounded-full border flex items-center justify-center shrink-0 mt-0.5 ${
                                                isSelected
                                                    ? "border-destructive bg-destructive text-destructive-foreground"
                                                    : "border-muted-foreground/40"
                                            }`}
                                        >
                                            {isSelected && <Check className="h-2.5 w-2.5 stroke-[3]" />}
                                        </div>
                                        <span className="font-medium text-xs leading-tight">
                                            {REPORT_REASON_LABELS[reason]}
                                        </span>
                                    </div>
                                )
                            })}
                        </div>
                    </div>

                    {/* Detalle adicional */}
                    <div className="space-y-1.5">
                        <Label htmlFor="report-description" className="text-xs font-semibold">
                            Detalle adicional de lo ocurrido:
                        </Label>
                        <Textarea
                            id="report-description"
                            placeholder="Describe el incidente (ej. El usuario utilizó lenguaje despectivo cuando intentamos coordinar el horario...)"
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            className="min-h-[85px] text-xs resize-none"
                            data-testid="report-description-input"
                        />
                        <p className="text-[10px] text-muted-foreground text-right">
                            Mínimo 10 caracteres ({description.trim().length}/10)
                        </p>
                    </div>

                    {/* Checkbox de bloqueo preventivo */}
                    <div className="flex items-center space-x-2 pt-1">
                        <Checkbox
                            id="block-user-checkbox"
                            checked={blockUserOption}
                            onCheckedChange={(checked) => setBlockUserOption(Boolean(checked))}
                        />
                        <Label
                            htmlFor="block-user-checkbox"
                            className="text-xs font-medium cursor-pointer"
                        >
                            Bloquear preventivamente a este usuario ahora
                        </Label>
                    </div>

                    {/* Banner de Protección Automática */}
                    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 flex gap-2.5 items-start text-xs text-amber-800 dark:text-amber-300">
                        <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" />
                        <div className="text-[11px] leading-relaxed">
                            <span className="font-semibold block mb-0.5">Protección Automática:</span>
                            El usuario será excluido de tu motor de búsqueda y tus propuestas activas con él serán canceladas de inmediato.
                        </div>
                    </div>
                </div>

                <DialogFooter className="flex flex-col-reverse sm:flex-row gap-2 sm:justify-between pt-2">
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => onOpenChange(false)}
                        disabled={submitting}
                    >
                        Cancelar
                    </Button>
                    <Button
                        type="button"
                        variant="destructive"
                        size="sm"
                        onClick={handleSubmit}
                        disabled={submitting || description.trim().length < 10}
                        className="gap-1.5 font-semibold"
                        data-testid="confirm-report-block-btn"
                    >
                        {submitting ? (
                            <>
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                Enviando a moderación…
                            </>
                        ) : (
                            <>
                                Confirmar Bloqueo y Enviar a Moderación
                                <ArrowRight className="h-3.5 w-3.5" />
                            </>
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
