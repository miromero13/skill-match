import { useEffect, useState } from "react"
import { ShieldCheck, UserX, Unlock, Loader2, ArrowLeft } from "lucide-react"
import { Link } from "react-router-dom"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useUserModerationStore } from "@/stores/user-moderation-store"
import { toast } from "sonner"
import { REPORT_REASON_LABELS, type ReportReason } from "@/types/user-moderation"

export function PrivacySettingsPage() {
    const { blockedUsers, count, loading, fetchBlockedUsers, unblockUser } =
        useUserModerationStore()
    const [unblockingId, setUnblockingId] = useState<string | null>(null)

    useEffect(() => {
        void fetchBlockedUsers()
    }, [fetchBlockedUsers])

    const handleUnblock = async (userId: string, name: string) => {
        setUnblockingId(userId)
        try {
            const ok = await unblockUser(userId)
            if (ok) {
                toast.success(`Has desbloqueado a ${name}.`)
            } else {
                toast.error("No se pudo desbloquear al usuario.")
            }
        } finally {
            setUnblockingId(null)
        }
    }

    return (
        <div className="container mx-auto max-w-4xl py-6 px-4 space-y-6" data-testid="privacy-settings-page">
            {/* Header de navegación */}
            <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" asChild>
                    <Link to="/profile" title="Volver al perfil">
                        <ArrowLeft className="h-4 w-4" />
                    </Link>
                </Button>
                <div>
                    <h1 className="text-xl sm:text-2xl font-bold tracking-tight">
                        Privacidad y Seguridad
                    </h1>
                    <p className="text-xs sm:text-sm text-muted-foreground">
                        Administra tus restricciones de interacción y usuarios bloqueados preventivamente.
                    </p>
                </div>
            </div>

            <Card>
                <CardHeader className="p-4 sm:p-6 pb-3 border-b border-border">
                    <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                            <CardTitle className="text-base font-semibold flex items-center gap-2">
                                <UserX className="h-4 w-4 text-destructive" />
                                Usuarios Bloqueados
                            </CardTitle>
                            <CardDescription className="text-xs">
                                Los miembros bloqueados no pueden enviarte mensajes, sugerencias ni interactuar en trueques.
                            </CardDescription>
                        </div>
                        <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                            {count} bloqueado(s)
                        </span>
                    </div>
                </CardHeader>

                <CardContent className="p-4 sm:p-6 space-y-3">
                    {loading ? (
                        <div className="flex flex-col items-center justify-center py-12 gap-2 text-muted-foreground">
                            <Loader2 className="h-6 w-6 animate-spin text-primary" />
                            <span className="text-xs">Cargando lista de bloqueos…</span>
                        </div>
                    ) : count === 0 ? (
                        <div className="flex flex-col items-center justify-center py-12 text-center space-y-2" data-testid="empty-blocked-users">
                            <div className="h-10 w-10 rounded-full bg-primary/10 text-primary flex items-center justify-center">
                                <ShieldCheck className="h-5 w-5" />
                            </div>
                            <h3 className="text-sm font-semibold text-foreground">
                                No tienes usuarios bloqueados actualmente
                            </h3>
                            <p className="text-xs text-muted-foreground max-w-sm">
                                Si detectas conductas inapropiadas o acoso, puedes bloquear perfiles desde sus tarjetas o propuestas.
                            </p>
                        </div>
                    ) : (
                        <div className="divide-y divide-border">
                            {blockedUsers.map((user) => {
                                const initials = user.full_name
                                    .split(" ")
                                    .map((n) => n[0])
                                    .slice(0, 2)
                                    .join("")
                                    .toUpperCase()
                                const isUnblocking = unblockingId === user.user_id
                                const reasonText = user.reason
                                    ? REPORT_REASON_LABELS[user.reason as ReportReason] || user.reason
                                    : "Bloqueo preventivo"

                                return (
                                    <div
                                        key={user.user_id}
                                        className="py-3 flex items-center justify-between gap-3 flex-wrap"
                                        data-testid={`blocked-user-row-${user.user_id}`}
                                    >
                                        <div className="flex items-center gap-3 min-w-0">
                                            <Avatar className="h-10 w-10 border border-border shrink-0">
                                                <AvatarImage src={user.avatar_url || undefined} alt={user.full_name} />
                                                <AvatarFallback className="text-xs font-semibold">
                                                    {initials}
                                                </AvatarFallback>
                                            </Avatar>
                                            <div className="min-w-0">
                                                <h4 className="text-sm font-semibold text-foreground truncate">
                                                    {user.full_name}
                                                </h4>
                                                <p className="text-xs text-muted-foreground truncate">
                                                    {reasonText} · Bloqueado el{" "}
                                                    {new Date(user.blocked_at).toLocaleDateString("es-ES", {
                                                        day: "numeric",
                                                        month: "short",
                                                        year: "numeric",
                                                    })}
                                                </p>
                                            </div>
                                        </div>

                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            onClick={() => handleUnblock(user.user_id, user.full_name)}
                                            disabled={isUnblocking}
                                            className="gap-1.5 text-xs shrink-0"
                                            data-testid={`unblock-btn-${user.user_id}`}
                                        >
                                            {isUnblocking ? (
                                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                            ) : (
                                                <Unlock className="h-3.5 w-3.5" />
                                            )}
                                            Desbloquear
                                        </Button>
                                    </div>
                                )
                            })}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}
