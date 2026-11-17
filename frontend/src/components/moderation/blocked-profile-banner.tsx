import { useState } from "react"
import { ShieldAlert, Unlock, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useUserModerationStore } from "@/stores/user-moderation-store"
import { toast } from "sonner"

interface BlockedProfileBannerProps {
    userId: string
    userName: string
    blockedAt?: string | null
    onUnblocked?: () => void
}

export function BlockedProfileBanner({
    userId,
    userName,
    blockedAt,
    onUnblocked,
}: BlockedProfileBannerProps) {
    const { unblockUser } = useUserModerationStore()
    const [loading, setLoading] = useState(false)

    const formattedDate = blockedAt
        ? new Date(blockedAt).toLocaleDateString("es-ES", {
              day: "numeric",
              month: "long",
              year: "numeric",
          })
        : "recientemente"

    const handleUnblock = async () => {
        setLoading(true)
        try {
            const ok = await unblockUser(userId)
            if (ok) {
                toast.success(`Has desbloqueado a ${userName}.`)
                onUnblocked?.()
            } else {
                toast.error("No se pudo desbloquear al usuario.")
            }
        } finally {
            setLoading(false)
        }
    }

    return (
        <div
            className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-destructive flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs"
            data-testid="blocked-profile-banner"
        >
            <div className="flex items-start gap-3">
                <ShieldAlert className="h-5 w-5 shrink-0 mt-0.5 text-destructive" />
                <div className="space-y-0.5">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-destructive">
                        Usuario Bloqueado
                    </h4>
                    <p className="text-xs text-foreground leading-relaxed">
                        Bloqueaste a este usuario el {formattedDate}. No puede enviarte propuestas, chats ni acceder a tus horarios. La queja está en auditoría.
                    </p>
                </div>
            </div>

            <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleUnblock}
                disabled={loading}
                className="shrink-0 border-destructive/40 text-destructive hover:bg-destructive/10 gap-1.5"
                data-testid="unblock-user-btn"
            >
                {loading ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                    <Unlock className="h-3.5 w-3.5" />
                )}
                Desbloquear
            </Button>
        </div>
    )
}
