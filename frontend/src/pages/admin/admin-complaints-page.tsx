/**
 * Consola Administrativa de Resolución de Disputas y Arbitraje (HU-43 / Vistas 18, 20).
 * Diseño Master-Detail con filtros por estado, emisión de dictamen y compensación en SkillPoints.
 * Exclusivo para administradores y protegido por AdminRouteGuard (seguridad por ofuscación 404).
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
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useComplaintStore } from '@/stores/complaint-store'
import {
  COMPLAINT_REASON_LABELS,
  COMPLAINT_STATUS_LABELS,
  type ComplaintStatus,
} from '@/types/complaint'
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Coins,
  ExternalLink,
  Gavel,
  RefreshCw,
  Search,
  ShieldCheck,
  User,
  XCircle,
} from 'lucide-react'

export function AdminComplaintsPage() {
  const {
    adminComplaints,
    adminTotal,
    selectedComplaint,
    isLoadingAdmin,
    isResolving,
    statusFilter,
    setStatusFilter,
    loadAdminComplaints,
    selectComplaint,
    resolveComplaintAction,
  } = useComplaintStore()

  const [searchTerm, setSearchTerm] = useState('')
  const [adminResponse, setAdminResponse] = useState('')
  const [compensateToggle, setCompensateToggle] = useState(false)
  const [pointsAmount, setPointsAmount] = useState<number>(50)
  const [resolveError, setResolveError] = useState<string | null>(null)

  useEffect(() => {
    loadAdminComplaints()
  }, [loadAdminComplaints])

  // Limpiar campos de dictamen al cambiar de queja seleccionada
  useEffect(() => {
    setAdminResponse('')
    setCompensateToggle(false)
    setPointsAmount(50)
    setResolveError(null)
  }, [selectedComplaint?.id])

  const filteredComplaints = adminComplaints.filter((c) => {
    if (!searchTerm.trim()) return true
    const term = searchTerm.toLowerCase()
    return (
      c.title.toLowerCase().includes(term) ||
      (c.user_full_name && c.user_full_name.toLowerCase().includes(term)) ||
      (c.user_email && c.user_email.toLowerCase().includes(term)) ||
      c.reason.toLowerCase().includes(term)
    )
  })

  const getStatusBadge = (status: ComplaintStatus) => {
    switch (status) {
      case 'OPEN':
        return (
          <Badge variant="outline" className="bg-amber-500/10 text-amber-500 border-amber-500/30 gap-1 text-xs">
            <Clock className="h-3 w-3" /> {COMPLAINT_STATUS_LABELS.OPEN}
          </Badge>
        )
      case 'RESOLVED':
        return (
          <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/30 gap-1 text-xs">
            <CheckCircle2 className="h-3 w-3" /> {COMPLAINT_STATUS_LABELS.RESOLVED}
          </Badge>
        )
      case 'DISMISSED':
        return (
          <Badge variant="outline" className="bg-zinc-500/10 text-zinc-400 border-zinc-500/30 gap-1 text-xs">
            <XCircle className="h-3 w-3" /> {COMPLAINT_STATUS_LABELS.DISMISSED}
          </Badge>
        )
    }
  }

  const handleResolve = async (actionStatus: 'RESOLVED' | 'DISMISSED') => {
    if (!selectedComplaint) return
    setResolveError(null)

    if (!adminResponse.trim()) {
      setResolveError('Es obligatorio ingresar la fundamentación o dictamen oficial.')
      return
    }

    const points = actionStatus === 'RESOLVED' && compensateToggle ? pointsAmount : 0

    const ok = await resolveComplaintAction(selectedComplaint.id, {
      status: actionStatus,
      admin_response: adminResponse.trim(),
      points_to_compensate: points,
    })

    if (ok) {
      setAdminResponse('')
      setCompensateToggle(false)
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto p-4 md:p-6">
      {/* Encabezado */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Gavel className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-bold tracking-tight">
              Resolución de Disputas y Quejas
            </h1>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Panel de arbitraje oficial: analiza reclamos radicados por miembros, emite dictámenes vinculantes y acredita compensación en SkillPoints.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => loadAdminComplaints()}
          disabled={isLoadingAdmin}
          className="gap-1.5 self-start sm:self-auto"
        >
          <RefreshCw className={`h-4 w-4 ${isLoadingAdmin ? 'animate-spin' : ''}`} />
          Actualizar
        </Button>
      </div>

      {/* Tabs de Filtro por Estado */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        <Tabs
          value={statusFilter}
          onValueChange={(val) => setStatusFilter(val)}
          className="w-full sm:w-auto"
        >
          <TabsList className="bg-muted">
            <TabsTrigger value="ALL">Todas ({adminTotal})</TabsTrigger>
            <TabsTrigger value="OPEN">Abiertas</TabsTrigger>
            <TabsTrigger value="RESOLVED">Resueltas</TabsTrigger>
            <TabsTrigger value="DISMISSED">Desestimadas</TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="relative w-full sm:w-72">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar por usuario o título..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9 h-9 text-xs"
          />
        </div>
      </div>

      {/* Master-Detail Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Panel Izquierdo: Lista Master */}
        <div className="lg:col-span-5 space-y-3">
          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-1">
            Reclamos en Catálogo ({filteredComplaints.length})
          </div>

          {isLoadingAdmin && adminComplaints.length === 0 ? (
            <div className="p-12 text-center text-sm text-muted-foreground border rounded-xl bg-card">
              Cargando reclamos...
            </div>
          ) : filteredComplaints.length === 0 ? (
            <Card className="p-8 text-center bg-card/50 border-dashed">
              <ShieldCheck className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-sm font-medium">No hay quejas en este filtro</p>
              <p className="text-xs text-muted-foreground mt-1">
                Selecciona otra pestaña o borra los términos de búsqueda.
              </p>
            </Card>
          ) : (
            <div className="space-y-2.5 max-h-[calc(100vh-280px)] overflow-y-auto pr-1">
              {filteredComplaints.map((c) => {
                const isSelected = selectedComplaint?.id === c.id
                return (
                  <div
                    key={c.id}
                    onClick={() => selectComplaint(c)}
                    className={`cursor-pointer rounded-xl border p-3.5 transition-all ${
                      isSelected
                        ? 'border-primary bg-primary/5 shadow-xs'
                        : 'border-border bg-card hover:border-primary/40 hover:bg-muted/40'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-1">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {getStatusBadge(c.status)}
                          <span className="text-2xs px-2 py-0.5 rounded bg-muted text-muted-foreground">
                            {COMPLAINT_REASON_LABELS[c.reason] || c.reason}
                          </span>
                        </div>
                        <h4 className="text-sm font-bold text-foreground line-clamp-1">
                          {c.title}
                        </h4>
                      </div>
                      {c.points_compensated > 0 && (
                        <span className="text-2xs font-bold text-emerald-500 whitespace-nowrap bg-emerald-500/10 px-1.5 py-0.5 rounded">
                          +{c.points_compensated} SP
                        </span>
                      )}
                    </div>

                    <div className="mt-2.5 flex items-center justify-between text-2xs text-muted-foreground pt-2 border-t border-border/40">
                      <span className="flex items-center gap-1">
                        <User className="h-3 w-3" />
                        {c.user_full_name || 'Miembro anónimo'}
                      </span>
                      <span>{new Date(c.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Panel Derecho: Detalle y Arbitraje */}
        <div className="lg:col-span-7">
          {!selectedComplaint ? (
            <Card className="p-16 text-center border-dashed bg-card/30">
              <Gavel className="h-12 w-12 text-muted-foreground mx-auto mb-3 opacity-50" />
              <h3 className="text-base font-semibold">Ningún reclamo seleccionado</h3>
              <p className="text-sm text-muted-foreground mt-1 max-w-sm mx-auto">
                Selecciona una queja del listado para inspeccionar los hechos, revisar las pruebas y emitir dictamen arbitral.
              </p>
            </Card>
          ) : (
            <Card className="bg-card border-border shadow-xs">
              <CardHeader className="border-b border-border/60 pb-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      {getStatusBadge(selectedComplaint.status)}
                      <Badge variant="secondary" className="text-xs font-normal">
                        {COMPLAINT_REASON_LABELS[selectedComplaint.reason]}
                      </Badge>
                      {selectedComplaint.session_reference && (
                        <Badge variant="outline" className="text-xs">
                          Sesión: {selectedComplaint.session_reference}
                        </Badge>
                      )}
                    </div>
                    <CardTitle className="text-lg font-bold">
                      {selectedComplaint.title}
                    </CardTitle>
                  </div>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    ID: {selectedComplaint.id.substring(0, 8)}...
                  </span>
                </div>
                <CardDescription className="text-xs flex items-center gap-4 pt-1">
                  <span>
                    <strong>Miembro denunciante:</strong> {selectedComplaint.user_full_name} ({selectedComplaint.user_email})
                  </span>
                  <span>•</span>
                  <span>
                    <strong>Fecha:</strong> {new Date(selectedComplaint.created_at).toLocaleString()}
                  </span>
                </CardDescription>
              </CardHeader>

              <CardContent className="pt-4 space-y-5">
                {/* Hechos de la Denuncia */}
                <div>
                  <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">
                    Declaración de los Hechos
                  </h4>
                  <div className="p-3.5 rounded-lg bg-muted/40 border border-border/40 text-sm whitespace-pre-line leading-relaxed">
                    {selectedComplaint.description}
                  </div>
                </div>

                {/* Pruebas y Evidencias */}
                <div>
                  <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">
                    Pruebas y Enlaces Aportados
                  </h4>
                  {selectedComplaint.evidence_urls && selectedComplaint.evidence_urls.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {selectedComplaint.evidence_urls.map((url, i) => (
                        <a
                          key={i}
                          href={url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline bg-primary/10 px-3 py-1.5 rounded-md"
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                          {url}
                        </a>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground italic">
                      El denunciante no adjuntó enlaces externos de prueba.
                    </p>
                  )}
                </div>

                {/* Formulario de Arbitraje o Dictamen Existente */}
                {selectedComplaint.status === 'OPEN' ? (
                  <div className="pt-4 border-t border-border space-y-4">
                    <div className="flex items-center gap-2 text-primary font-bold text-sm">
                      <Gavel className="h-4 w-4" />
                      Emitir Dictamen Arbitral
                    </div>

                    {resolveError && (
                      <div className="flex items-center gap-2 p-3 text-xs rounded-lg bg-destructive/10 text-destructive border border-destructive/20">
                        <AlertCircle className="h-4 w-4 shrink-0" />
                        <span>{resolveError}</span>
                      </div>
                    )}

                    <div className="space-y-1.5">
                      <Label htmlFor="admin-response-input" className="text-xs font-semibold">
                        Respuesta / Dictamen Oficial *
                      </Label>
                      <Textarea
                        id="admin-response-input"
                        placeholder="Redacta la resolución oficial del caso. Esta respuesta será visible para el miembro en su Centro de Quejas..."
                        value={adminResponse}
                        onChange={(e) => setAdminResponse(e.target.value)}
                        rows={4}
                      />
                    </div>

                    {/* Toggle de Compensación en Puntos */}
                    <div className="rounded-xl border border-border p-3.5 bg-muted/20 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                          <Label htmlFor="compensate-toggle" className="text-xs font-semibold cursor-pointer">
                            Compensar con SkillPoints (SP)
                          </Label>
                          <p className="text-2xs text-muted-foreground">
                            Acredita puntos oficiales inmediatamente en la billetera del miembro denunciante.
                          </p>
                        </div>
                        <Switch
                          id="compensate-toggle"
                          checked={compensateToggle}
                          onCheckedChange={setCompensateToggle}
                        />
                      </div>

                      {compensateToggle && (
                        <div className="space-y-2 pt-2 border-t border-border/40">
                          <Label className="text-2xs font-semibold text-muted-foreground">
                            Cantidad de SkillPoints a Acreditar:
                          </Label>
                          <div className="flex items-center gap-2">
                            {[25, 50, 100, 200].map((pts) => (
                              <Button
                                key={pts}
                                type="button"
                                variant={pointsAmount === pts ? 'default' : 'outline'}
                                size="sm"
                                onClick={() => setPointsAmount(pts)}
                                className="h-8 text-xs gap-1"
                              >
                                <Coins className="h-3 w-3" /> +{pts} SP
                              </Button>
                            ))}
                            <Input
                              type="number"
                              min={1}
                              max={5000}
                              value={pointsAmount}
                              onChange={(e) => setPointsAmount(Math.max(1, parseInt(e.target.value) || 0))}
                              className="h-8 w-24 text-xs font-bold"
                            />
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Acciones de Resolución */}
                    <div className="flex items-center justify-end gap-3 pt-2">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => handleResolve('DISMISSED')}
                        disabled={isResolving}
                        className="text-muted-foreground hover:text-destructive hover:border-destructive/40"
                      >
                        <XCircle className="h-4 w-4 mr-1.5" />
                        Desestimar Reclamo
                      </Button>
                      <Button
                        type="button"
                        onClick={() => handleResolve('RESOLVED')}
                        disabled={isResolving}
                        className="gap-1.5"
                      >
                        <CheckCircle2 className="h-4 w-4" />
                        {compensateToggle
                          ? `Resolver y Compensar +${pointsAmount} SP`
                          : 'Resolver Favorablemente'}
                      </Button>
                    </div>
                  </div>
                ) : (
                  /* Dictamen Oficial Ya Emitido (Lectura) */
                  <div className="pt-4 border-t border-border space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5 font-bold text-sm text-foreground">
                        <CheckCircle2 className="h-4 w-4 text-primary" />
                        Dictamen Emitido
                      </div>
                      <span className="text-xs text-muted-foreground">
                        Resuelto el{' '}
                        {selectedComplaint.resolved_at
                          ? new Date(selectedComplaint.resolved_at).toLocaleString()
                          : '-'}
                      </span>
                    </div>

                    <div className="p-3.5 rounded-lg border border-border bg-muted/30 space-y-2">
                      <p className="text-xs text-muted-foreground">
                        <strong>Dictamen arbitral registrado:</strong>
                      </p>
                      <p className="text-sm italic text-foreground whitespace-pre-line">
                        "{selectedComplaint.admin_response}"
                      </p>
                      {selectedComplaint.points_compensated > 0 && (
                        <div className="pt-2 flex items-center gap-2 text-xs text-emerald-500 font-bold border-t border-border/40">
                          <Coins className="h-4 w-4" />
                          Se acreditaron +{selectedComplaint.points_compensated} SP en la billetera del miembro.
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
