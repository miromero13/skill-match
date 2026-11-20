/**
 * Vista del Centro de Quejas y Mediación para Miembros (HU-43 / Vistas 24A, 26A).
 * Permite radicar quejas, consultar el estado de arbitraje y verificar compensaciones en SkillPoints.
 */
import { useEffect, useState } from 'react'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useComplaintStore } from '@/stores/complaint-store'
import { CreateComplaintDialog } from '@/components/complaints/create-complaint-dialog'
import {
  COMPLAINT_REASON_LABELS,
  COMPLAINT_STATUS_LABELS,
  type ComplaintStatus,
} from '@/types/complaint'
import {
  CheckCircle2,
  Clock,
  Coins,
  ExternalLink,
  MessageSquare,
  PlusCircle,
  RefreshCw,
  Scale,
  ShieldCheck,
  XCircle,
} from 'lucide-react'

export function ComplaintsPage() {
  const { memberComplaints, memberTotal, isLoadingMember, loadMyComplaints } =
    useComplaintStore()
  const [isDialogOpen, setIsDialogOpen] = useState(false)

  useEffect(() => {
    loadMyComplaints()
  }, [loadMyComplaints])

  const openCount = memberComplaints.filter((c) => c.status === 'OPEN').length
  const resolvedCount = memberComplaints.filter((c) => c.status === 'RESOLVED').length
  const totalCompensated = memberComplaints.reduce(
    (acc, curr) => acc + curr.points_compensated,
    0
  )

  const getStatusBadge = (status: ComplaintStatus) => {
    switch (status) {
      case 'OPEN':
        return (
          <Badge variant="outline" className="bg-amber-500/10 text-amber-500 border-amber-500/30 gap-1">
            <Clock className="h-3 w-3" /> {COMPLAINT_STATUS_LABELS.OPEN}
          </Badge>
        )
      case 'RESOLVED':
        return (
          <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/30 gap-1">
            <CheckCircle2 className="h-3 w-3" /> {COMPLAINT_STATUS_LABELS.RESOLVED}
          </Badge>
        )
      case 'DISMISSED':
        return (
          <Badge variant="outline" className="bg-zinc-500/10 text-zinc-400 border-zinc-500/30 gap-1">
            <XCircle className="h-3 w-3" /> {COMPLAINT_STATUS_LABELS.DISMISSED}
          </Badge>
        )
    }
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Scale className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-bold tracking-tight">Centro de Quejas y Mediación</h1>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Radica reclamos formales sobre sesiones o acuerdos y consulta los dictámenes arbitrales emitidos.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadMyComplaints()}
            disabled={isLoadingMember}
            className="gap-1.5"
          >
            <RefreshCw className={`h-4 w-4 ${isLoadingMember ? 'animate-spin' : ''}`} />
            Actualizar
          </Button>
          <Button onClick={() => setIsDialogOpen(true)} className="gap-1.5">
            <PlusCircle className="h-4 w-4" />
            Radicar Nueva Queja
          </Button>
        </div>
      </div>

      {/* Métricas Resumen */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="bg-card border-border shadow-xs">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Reclamos Radicados</CardDescription>
            <CardTitle className="text-2xl font-bold">{memberTotal}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">Historial completo de quejas</p>
          </CardContent>
        </Card>

        <Card className="bg-card border-border shadow-xs">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">En Revisión / Abiertas</CardDescription>
            <CardTitle className="text-2xl font-bold text-amber-500">{openCount}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">Pendientes de dictamen arbitral</p>
          </CardContent>
        </Card>

        <Card className="bg-card border-border shadow-xs">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">SkillPoints Compensados</CardDescription>
            <CardTitle className="text-2xl font-bold text-emerald-500">
              +{totalCompensated} SP
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">{resolvedCount} resueltas favorablemente</p>
          </CardContent>
        </Card>
      </div>

      {/* Lista de Quejas */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight">Mis Reclamos y Disputas</h2>

        {isLoadingMember && memberComplaints.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground text-sm">
            Cargando historial de quejas...
          </div>
        ) : memberComplaints.length === 0 ? (
          <Card className="p-10 text-center border-dashed border-border bg-card/40">
            <ShieldCheck className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <h3 className="font-semibold text-base mb-1">No tienes quejas registradas</h3>
            <p className="text-sm text-muted-foreground max-w-md mx-auto mb-4">
              Si experimentaste un incumplimiento en una sesión de trueque o un inconveniente con los puntos,
              puedes radicar una solicitud de mediación formal.
            </p>
            <Button onClick={() => setIsDialogOpen(true)} variant="outline">
              Radicar Queja
            </Button>
          </Card>
        ) : (
          <div className="space-y-4">
            {memberComplaints.map((c) => (
              <Card key={c.id} className="bg-card border-border overflow-hidden">
                <CardHeader className="pb-3 border-b border-border/40">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        {getStatusBadge(c.status)}
                        <Badge variant="secondary" className="text-xs font-normal">
                          {COMPLAINT_REASON_LABELS[c.reason] || c.reason}
                        </Badge>
                        {c.points_compensated > 0 && (
                          <Badge className="bg-emerald-500 text-white gap-1 text-xs font-bold">
                            <Coins className="h-3 w-3" /> +{c.points_compensated} SP Compensados
                          </Badge>
                        )}
                      </div>
                      <CardTitle className="text-base font-bold text-foreground">
                        {c.title}
                      </CardTitle>
                    </div>
                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                      Radicada el {new Date(c.created_at).toLocaleDateString()} a las{' '}
                      {new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                </CardHeader>

                <CardContent className="pt-4 space-y-4">
                  <div>
                    <h4 className="text-xs font-semibold text-muted-foreground mb-1 uppercase tracking-wider">
                      Detalle de los Hechos
                    </h4>
                    <p className="text-sm text-foreground/90 whitespace-pre-line bg-muted/30 p-3 rounded-lg border border-border/30">
                      {c.description}
                    </p>
                  </div>

                  {c.evidence_urls && c.evidence_urls.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-muted-foreground mb-1.5 uppercase tracking-wider">
                        Pruebas Aportadas
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {c.evidence_urls.map((url, i) => (
                          <a
                            key={i}
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline bg-primary/10 px-2.5 py-1 rounded-md"
                          >
                            <ExternalLink className="h-3 w-3" />
                            {url.length > 40 ? `${url.substring(0, 40)}...` : url}
                          </a>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Dictamen oficial si la queja fue resuelta o desestimada */}
                  {c.status !== 'OPEN' && (
                    <div className="mt-4 rounded-xl border border-primary/20 bg-primary/5 p-4 space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 text-primary font-semibold text-xs uppercase tracking-wide">
                          <MessageSquare className="h-4 w-4" />
                          Dictamen Arbitral Oficial
                        </div>
                        {c.resolved_at && (
                          <span className="text-xs text-muted-foreground">
                            Emitido el {new Date(c.resolved_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-foreground whitespace-pre-line italic">
                        "{c.admin_response}"
                      </p>
                      {c.points_compensated > 0 && (
                        <div className="pt-2 flex items-center gap-2 text-xs text-emerald-600 font-semibold border-t border-primary/10">
                          <Coins className="h-4 w-4" />
                          Se acreditaron +{c.points_compensated} SP inmediatamente en tu Billetera oficial.
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      <CreateComplaintDialog
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onSuccess={() => loadMyComplaints()}
      />
    </div>
  )
}
