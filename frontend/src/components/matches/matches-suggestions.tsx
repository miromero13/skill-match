import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { useStore } from "zustand"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { MatchNegotiation } from "@/components/matches/match-negotiation"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { createMatchStore } from "@/stores/match-store"
import type { MatchSuggestion } from "@/types/match"

function SkillExchange({ match }: { match: MatchSuggestion }) {
    // En móvil apila los dos lados. Desde sm los muestra juntos.
    return (
        <div className="grid gap-3 sm:grid-cols-2">
            <div className="min-w-0 rounded-lg border p-3">
                <p className="text-sm font-medium">Tú le enseñas</p>
                <ul className="mt-1 list-disc break-words pl-5 text-sm text-muted-foreground">
                    {match.you_teach.map((name, index) => (
                        <li key={index}>{name} {match.you_verified?.includes(name) && <Badge variant="secondary">Verificada</Badge>}</li>
                    ))}
                </ul>
            </div>
            <div className="min-w-0 rounded-lg border p-3">
                <p className="text-sm font-medium">Te enseña</p>
                <ul className="mt-1 list-disc break-words pl-5 text-sm text-muted-foreground">
                    {match.they_teach.map((name, index) => (
                        <li key={index}>{name} {match.they_verified?.includes(name) && <Badge variant="secondary">Verificada</Badge>}</li>
                    ))}
                </ul>
            </div>
        </div>
    )
}

function MemberIdentity({ name, photo }: { name: string; photo: string | null }) {
    return (
        <div className="flex min-w-0 items-center gap-2">
            <Avatar>
                {photo && <AvatarImage src={photo} alt="" />}
                <AvatarFallback>{name.slice(0, 2).toUpperCase()}</AvatarFallback>
            </Avatar>
            <span className="break-words font-medium">{name}</span>
        </div>
    )
}

export function MatchSuggestions({ preview = false }: { preview?: boolean }) {
    // React conserva esta instancia del store mientras la sección está montada.
    const [store] = useState(createMatchStore)
    const [page, setPage] = useState(1)
    const [retry, setRetry] = useState(0)
    const [selectedId, setSelectedId] = useState<string | null>(null)

    // Cada selector lee solamente el dato que necesita la sección.
    const items = useStore(store, (state) => state.items)
    const count = useStore(store, (state) => state.count)
    const loading = useStore(store, (state) => state.loading)
    const failed = useStore(store, (state) => state.failed)
    const message = useStore(store, (state) => state.message)
    const detail = useStore(store, (state) => state.detail)
    const detailMessage = useStore(store, (state) => state.detailMessage)
    const loadingDetail = useStore(store, (state) => state.loadingDetail)

    useEffect(() => {
        // Carga una página al entrar, cambiar de página o reintentar.
        const controller = new AbortController()
        void store.getState().load(page, controller.signal)
        return () => controller.abort()
    }, [store, page, retry])

    useEffect(() => {
        // Abre el detalle solo cuando se selecciona una tarjeta.
        if (!selectedId) return
        const controller = new AbortController()
        void store.getState().loadDetail(selectedId, controller.signal)
        return () => controller.abort()
    }, [store, selectedId])

    // El feed muestra las primeras tres. La página dedicada muestra la página completa.
    const visibleItems = preview ? items.slice(0, 3) : items

    return (
        <section className="space-y-4" aria-label="Coincidencias de intercambio">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-lg font-semibold">
                    {preview ? "Sugerencias de intercambio" : "Tus Coincidencias"}
                </h2>
                {preview && (
                    <Button variant="outline" asChild>
                        <Link to="/matches">Ver todas</Link>
                    </Button>
                )}
            </div>

            {/* El texto del backend se muestra sin sustituirlo. */}
            <p role={failed ? "alert" : "status"} className="text-sm text-muted-foreground">
                {loading ? "Cargando coincidencias…" : message}
            </p>

            {failed && (
                <Button variant="outline" onClick={() => setRetry((value) => value + 1)}>
                    Reintentar
                </Button>
            )}

            {!loading && !failed && visibleItems.map((match) => (
                <Card key={match.id}>
                    <CardContent className="space-y-3 p-4">
                        <div className="grid gap-3 sm:grid-cols-2">
                            <MemberIdentity name={match.member_name} photo={match.member_avatar_url} />
                            <MemberIdentity name={match.counterpart_name} photo={match.counterpart_avatar_url} />
                        </div>
                        <SkillExchange match={match} />
                        <Button variant="outline" onClick={() => setSelectedId(match.id)}>
                            {match.status === "confirmed" ? "Ver intercambio" : "Ver propuesta"}
                        </Button>
                    </CardContent>
                </Card>
            ))}

            {!preview && !loading && !failed && count > 0 && (
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <Button
                        variant="outline"
                        disabled={page <= 1}
                        onClick={() => setPage((value) => value - 1)}
                    >
                        Anterior
                    </Button>
                    <span className="text-sm">Página {page} · {count} coincidencias</span>
                    <Button
                        variant="outline"
                        disabled={page * 20 >= count}
                        onClick={() => setPage((value) => value + 1)}
                    >
                        Siguiente
                    </Button>
                </div>
            )}

            <Dialog
                open={selectedId !== null}
                onOpenChange={(open) => { if (!open) setSelectedId(null) }}
            >
                <DialogContent className="max-h-[85dvh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>{detail?.counterpart_name ?? "Detalle de coincidencia"}</DialogTitle>
                        <DialogDescription>
                            {loadingDetail ? "Cargando detalle…" : detailMessage}
                        </DialogDescription>
                    </DialogHeader>
                    {detail && detail.id === selectedId && !loadingDetail && (
                        <>
                            <SkillExchange match={detail} />
                            <MatchNegotiation
                                key={detail.id}
                                id={detail.id}
                                onChange={(hide) => {
                                    if (hide) setSelectedId(null)
                                    setRetry((value) => value + 1)
                                }}
                            />
                        </>
                    )}
                </DialogContent>
            </Dialog>
        </section>
    )
}
