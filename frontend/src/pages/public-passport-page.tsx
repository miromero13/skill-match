import { useEffect } from "react"
import { useParams, Link } from "react-router-dom"
import { useAuthStore } from "@/stores/auth-store"
import { usePassportStore } from "@/stores/passport-store"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Separator } from "@/components/ui/separator"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  ShieldCheck,
  QrCode,
  Download,
  Share2,
  CheckCircle2,
  Copy,
  Terminal,
  Video,
  Loader2,
  Calendar,
  Sparkles,
  Award,
  Hash,
  Star,
  BookOpen,
  Clock,
  ArrowRight,
} from "lucide-react"

export function PublicPassportPage() {
  const { uuid: routeUuid } = useParams<{ uuid: string }>()
  const authUser = useAuthStore((s) => s.user)
  const uuid = routeUuid || authUser?.id
  const {
    currentPassport,
    isLoadingPassport,
    passportError,
    loadPassport,
    isQrModalOpen,
    openQrModal,
    closeQrModal,
    copyShareableLink,
  } = usePassportStore()

  useEffect(() => {
    if (uuid) {
      loadPassport(uuid)
    }
  }, [uuid, loadPassport])

  if (isLoadingPassport) {
    return (
      <div className="flex min-h-[75vh] flex-col items-center justify-center gap-3">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground font-medium">
          Verificando firma criptográfica y cargando pasaporte...
        </p>
      </div>
    )
  }

  if (passportError || !currentPassport) {
    return (
      <div className="container max-w-2xl py-20 text-center space-y-4">
        <div className="mx-auto w-12 h-12 rounded-full bg-destructive/10 text-destructive flex items-center justify-center">
          <ShieldCheck className="w-6 h-6" />
        </div>
        <h2 className="text-xl font-bold text-foreground">Pasaporte no disponible</h2>
        <p className="text-sm text-muted-foreground">
          {passportError || "No se encontró un pasaporte público para el identificador consultado."}
        </p>
        <div className="pt-2">
          <Link to="/">
            <Button variant="outline" size="sm">
              Ir al inicio de SkillMatch
            </Button>
          </Link>
        </div>
      </div>
    )
  }

  const p = currentPassport
  const dossier = p.technical_dossier
  const hasAudit = Boolean(dossier.has_technical_audit && dossier.code_challenge && dossier.oral_defense)
  const challenge = dossier.code_challenge
  const codeLines = challenge?.source_code ? challenge.source_code.split("\n") : []

  const getBadgeIcon = (iconName: string) => {
    switch (iconName) {
      case "ShieldCheck":
        return <ShieldCheck className="h-4 w-4 text-primary" />
      case "Star":
        return <Star className="h-4 w-4 text-amber-500 fill-amber-500" />
      case "Award":
      default:
        return <Award className="h-4 w-4 text-indigo-500" />
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground py-6 sm:py-10">
      <div className="container max-w-5xl mx-auto px-4 space-y-6">
        {/* Banner Superior Institucional (Trust Protocol) */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3 sm:px-5 rounded-lg border border-primary/20 bg-primary/5 text-primary text-xs font-semibold">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 shrink-0 text-primary" />
            <span className="tracking-wide">SKILLMATCH TRUST PROTOCOL · CERTIFICADO OFICIAL DE COMPETENCIA</span>
          </div>
          <div className="flex items-center gap-1.5 text-[11px] font-mono text-muted-foreground">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            {p.verification_node}
          </div>
        </div>

        {/* Hero Card: Titular y Datos del Pasaporte */}
        <Card className="border-border bg-card shadow-sm overflow-hidden">
          <CardContent className="p-6 sm:p-8 space-y-6">
            <div className="flex flex-col md:flex-row items-center md:items-start justify-between gap-6">
              {/* Información del candidato */}
              <div className="flex flex-col sm:flex-row items-center sm:items-start gap-4 text-center sm:text-left">
                <Avatar className="h-20 w-20 border-2 border-primary shadow-sm shrink-0">
                  <AvatarImage src={p.avatar_url || undefined} alt={p.full_name} />
                  <AvatarFallback className="bg-primary/10 text-primary font-bold text-2xl">
                    {p.full_name.slice(0, 2).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2">
                    <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-foreground">
                      {p.full_name}
                    </h1>
                    <Badge className="bg-primary/10 text-primary border border-primary/20 text-[10px] font-bold uppercase tracking-wider">
                      Titular Verificado
                    </Badge>
                  </div>
                  <p className="text-xs sm:text-sm text-muted-foreground font-medium">
                    {p.bio || "Miembro de la Comunidad SkillMatch"} {p.location_label ? `· ${p.location_label}` : ""}
                  </p>
                  <div className="flex flex-wrap items-center justify-center sm:justify-start gap-3 pt-2 text-[11px] text-muted-foreground font-mono">
                    <span className="flex items-center gap-1 font-semibold text-foreground">
                      <Hash className="h-3 w-3 text-primary" /> {p.certificate_id}
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3 w-3" /> Emitido: {new Date(p.issued_at).toLocaleDateString()}
                    </span>
                    <span className="flex items-center gap-1 text-primary">
                      Hash: {p.verification_hash}
                    </span>
                  </div>
                </div>
              </div>

              {/* Botones de acción principales */}
              <div className="flex flex-wrap items-center justify-center gap-2 w-full md:w-auto">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={copyShareableLink}
                  className="gap-1.5 text-xs font-semibold"
                >
                  <Share2 className="h-3.5 w-3.5" />
                  Copiar enlace
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={openQrModal}
                  className="gap-1.5 text-xs font-semibold"
                >
                  <QrCode className="h-3.5 w-3.5" />
                  Ver QR
                </Button>
                <a href={p.pdf_download_url} download={`pasaporte-${p.public_uuid}.pdf`}>
                  <Button
                    size="sm"
                    className="bg-[#00786F] hover:bg-[#006058] dark:bg-primary dark:hover:bg-primary/90 text-white font-bold text-xs gap-1.5 shadow-sm"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Descargar PDF
                  </Button>
                </a>
              </div>
            </div>

            <Separator className="bg-border" />

            {/* 4 Indicadores Adaptativos (Auditados o Declarados) */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {hasAudit && challenge ? (
                <>
                  <div className="p-3.5 rounded-lg bg-muted/40 border border-border text-center space-y-1">
                    <span className="text-[10px] text-muted-foreground font-semibold tracking-wider uppercase">
                      Score Código
                    </span>
                    <p className="text-xl font-black text-foreground">
                      {(dossier.technical_score || 0).toFixed(0)} <span className="text-xs text-muted-foreground">/ 100</span>
                    </p>
                    <p className="text-[10px] text-primary font-medium truncate">
                      {dossier.evaluated_skill_name || "Desafío Técnico"}
                    </p>
                  </div>

                  <div className="p-3.5 rounded-lg bg-muted/40 border border-border text-center space-y-1">
                    <span className="text-[10px] text-muted-foreground font-semibold tracking-wider uppercase">
                      Defensa Oral IA
                    </span>
                    <p className="text-xl font-black text-foreground">
                      {(dossier.oral_defense_score || 0).toFixed(0)} <span className="text-xs text-muted-foreground">/ 100</span>
                    </p>
                    <p className="text-[10px] text-primary font-medium truncate">Voz & Liveness Facial</p>
                  </div>

                  <div className="p-3.5 rounded-lg bg-muted/40 border border-border text-center space-y-1">
                    <span className="text-[10px] text-muted-foreground font-semibold tracking-wider uppercase">
                      Suite Docker
                    </span>
                    <p className="text-xl font-black text-foreground">
                      {challenge.docker_report.passed_count}/{challenge.docker_report.total_count}{" "}
                      <span className="text-xs text-emerald-500 font-bold">PASSED</span>
                    </p>
                    <p className="text-[10px] text-muted-foreground font-medium truncate">
                      {challenge.docker_report.execution_time_seconds}s · {challenge.docker_report.coverage_percentage}% Cobertura
                    </p>
                  </div>

                  <div className="p-3.5 rounded-lg bg-muted/40 border border-border text-center space-y-1">
                    <span className="text-[10px] text-muted-foreground font-semibold tracking-wider uppercase">
                      Anti-Fraude
                    </span>
                    <p className="text-xl font-black text-foreground">
                      100% <span className="text-xs text-emerald-500 font-bold">LIMPIO</span>
                    </p>
                    <p className="text-[10px] text-primary font-medium truncate">Sin Infracciones</p>
                  </div>
                </>
              ) : (
                <>
                  <div className="p-3.5 rounded-lg bg-muted/40 border border-border text-center space-y-1">
                    <span className="text-[10px] text-muted-foreground font-semibold tracking-wider uppercase">
                      Habilidades
                    </span>
                    <p className="text-xl font-black text-foreground">
                      {p.skills.length}
                    </p>
                    <p className="text-[10px] text-primary font-medium truncate">Registradas en Perfil</p>
                  </div>

                  <div className="p-3.5 rounded-lg bg-muted/40 border border-border text-center space-y-1">
                    <span className="text-[10px] text-muted-foreground font-semibold tracking-wider uppercase">
                      Auditoría Técnica
                    </span>
                    <p className="text-xl font-black text-amber-500 dark:text-amber-400">
                      Pendiente
                    </p>
                    <p className="text-[10px] text-muted-foreground font-medium truncate">En Docker Sandbox</p>
                  </div>

                  <div className="p-3.5 rounded-lg bg-muted/40 border border-border text-center space-y-1">
                    <span className="text-[10px] text-muted-foreground font-semibold tracking-wider uppercase">
                      Confianza Global
                    </span>
                    <p className="text-xl font-black text-foreground">
                      {p.trust_score.toFixed(0)}%
                    </p>
                    <p className="text-[10px] text-emerald-500 font-medium truncate">
                      {p.overall_rating.toFixed(1)} / 5.0 Estrellas
                    </p>
                  </div>

                  <div className="p-3.5 rounded-lg bg-muted/40 border border-border text-center space-y-1">
                    <span className="text-[10px] text-muted-foreground font-semibold tracking-wider uppercase">
                      Reseñas Alumnos
                    </span>
                    <p className="text-xl font-black text-foreground">
                      {p.total_reviews}
                    </p>
                    <p className="text-[10px] text-primary font-medium truncate">Evaluaciones Auditadas</p>
                  </div>
                </>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Sección de Auditoría Práctica: Condicional según si existe examen verificado o no */}
        {hasAudit && challenge && dossier.oral_defense && dossier.anti_fraud ? (
          <>
            {/* Sección 1: Desafío Práctico en Docker (Código Auditado y Tests) */}
            <Card className="border-border bg-card shadow-sm">
              <CardContent className="p-6 space-y-4">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Terminal className="h-5 w-5 text-primary" />
                    <h2 className="text-base sm:text-lg font-bold text-foreground">
                      1. Desafío Práctico: {challenge.title}
                    </h2>
                  </div>
                  <Badge className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 text-xs font-semibold gap-1">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Pytest {challenge.docker_report.passed_count}/{challenge.docker_report.total_count} Passed
                  </Badge>
                </div>

                <p className="text-xs text-muted-foreground bg-muted/40 p-3 rounded-lg border border-border leading-relaxed">
                  <strong className="text-foreground">Consigna:</strong> {challenge.consigna}
                </p>

                {/* Visor de Código Fuente Auditado */}
                <div className="rounded-lg border border-slate-800 bg-[#0A0E10] text-slate-200 overflow-hidden text-xs font-mono shadow-inner">
                  <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800 bg-[#0F1416] text-[11px] text-slate-400">
                    <span className="font-semibold text-slate-300">{challenge.file_name} (Solución auditada del candidato)</span>
                    <span>{challenge.language}</span>
                  </div>
                  <div className="p-4 overflow-x-auto">
                    <table className="w-full border-collapse">
                      <tbody>
                        {codeLines.map((line, idx) => (
                          <tr key={idx} className="hover:bg-slate-800/40">
                            <td className="pr-4 select-none text-right text-slate-600 w-8 align-top">
                              {idx + 1}
                            </td>
                            <td className="whitespace-pre text-emerald-400/90 font-mono">
                              {line}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Reporte de Pytest en Docker */}
                <div className="space-y-2 p-3.5 rounded-lg bg-muted/30 border border-border text-xs">
                  <div className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider flex items-center justify-between">
                    <span>Docker Runtime · Pytest Suite Audit Report</span>
                    <span className="text-emerald-600 dark:text-emerald-400">
                      {challenge.docker_report.passed_count} PASSED in {challenge.docker_report.execution_time_seconds}s
                    </span>
                  </div>
                  <div className="space-y-1.5 font-mono text-[11px]">
                    {challenge.docker_report.test_cases.map((t) => (
                      <div key={t.name} className="flex items-center justify-between text-muted-foreground">
                        <span className="flex items-center gap-1.5 text-foreground">
                          <CheckCircle2 className="h-3 w-3 text-emerald-500 shrink-0" />
                          PASSED <span className="text-muted-foreground">{t.name}</span>
                        </span>
                        <span>[{t.percentage}%] · {t.duration_seconds}s</span>
                      </div>
                    ))}
                  </div>
                  <div className="pt-2 text-[10px] text-center text-muted-foreground border-t border-border font-semibold">
                    ====== {challenge.docker_report.passed_count} PASSED in {challenge.docker_report.execution_time_seconds}s · COBERTURA TESTEADA: {challenge.docker_report.coverage_percentage}% ======
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Sección 2: Defensa Conceptual en Vivo frente a Cámara */}
            <Card className="border-border bg-card shadow-sm">
              <CardContent className="p-6 space-y-4">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Video className="h-5 w-5 text-primary" />
                    <h2 className="text-base sm:text-lg font-bold text-foreground">
                      2. Defensa Conceptual en Vivo frente a Cámara
                    </h2>
                  </div>
                  <Badge className="bg-primary/10 text-primary border border-primary/20 text-xs font-bold">
                    Score Oral: {(dossier.oral_defense_score || 0).toFixed(0)} / 100 ✓
                  </Badge>
                </div>

                {/* Pregunta formulada por IA */}
                <div className="space-y-1 text-xs">
                  <span className="font-semibold text-muted-foreground uppercase text-[10px] tracking-wider">
                    Pregunta formulada por la IA en tiempo real:
                  </span>
                  <p className="p-3 rounded-lg bg-muted/40 border border-border text-foreground font-medium italic">
                    "{dossier.oral_defense.question}"
                  </p>
                </div>

                {/* Transcripción de la respuesta */}
                <div className="space-y-1 text-xs">
                  <span className="font-semibold text-muted-foreground uppercase text-[10px] tracking-wider">
                    Transcripción auditada de la respuesta oral:
                  </span>
                  <p className="p-3 rounded-lg bg-muted/20 border border-border text-muted-foreground leading-relaxed">
                    "{dossier.oral_defense.candidate_transcript}"
                  </p>
                </div>

                {/* Dictamen del Validador IA */}
                <div className="p-3 rounded-lg bg-primary/5 border border-primary/20 text-xs space-y-1">
                  <span className="font-bold text-primary text-[10px] uppercase tracking-wider flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5" /> Dictamen del Validador IA (Auditoría Pedagógica):
                  </span>
                  <p className="text-foreground leading-relaxed">
                    {dossier.oral_defense.ai_verdict}
                  </p>
                </div>

                {/* Parámetros de Integridad Anti-fraude */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1 text-[11px]">
                  <div className="p-2.5 rounded-md bg-muted/40 border border-border flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                    <span>Liveness Facial 100%</span>
                  </div>
                  <div className="p-2.5 rounded-md bg-muted/40 border border-border flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                    <span>{dossier.anti_fraud.voice_verification_status}</span>
                  </div>
                  <div className="p-2.5 rounded-md bg-muted/40 border border-border flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                    <span>{dossier.anti_fraud.screen_violations_count} Infracciones / Pantalla</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </>
        ) : (
          /* Estado Pendiente de Auditoría Técnica */
          <Card className="border-border bg-card shadow-sm">
            <CardContent className="p-6 sm:p-8 space-y-5">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-amber-500/10 text-amber-500 border border-amber-500/20 shrink-0">
                    <Clock className="h-6 w-6" />
                  </div>
                  <div>
                    <h2 className="text-base sm:text-lg font-bold text-foreground">
                      Auditoría Técnica en Sandbox Docker: Pendiente de Certificación
                    </h2>
                    <p className="text-xs text-muted-foreground">
                      Evaluación práctica automatizada de código y defensa oral frente a cámara.
                    </p>
                  </div>
                </div>
                <Badge variant="outline" className="border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400 text-xs font-semibold">
                  Habilidades Declaradas
                </Badge>
              </div>

              <div className="p-4 rounded-lg bg-muted/30 border border-border space-y-3 text-xs leading-relaxed text-muted-foreground">
                <p>
                  El titular cuenta con <strong className="text-foreground">{p.skills.length} habilidades registradas</strong> en su perfil. Para activar el visor de código fuente auditado en Docker, los resultados de Pytest en tiempo de compilación y la transcripción de defensa oral, se requiere aprobar la evaluación técnica supervisada.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1">
                  <div className="p-3 rounded-md bg-background border border-border space-y-1">
                    <p className="font-semibold text-foreground flex items-center gap-1.5">
                      <Terminal className="h-3.5 w-3.5 text-primary" /> 1. Desafío en Sandbox
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      Resolución en vivo con ejecución aislada en Docker y pruebas unitarias Pytest.
                    </p>
                  </div>
                  <div className="p-3 rounded-md bg-background border border-border space-y-1">
                    <p className="font-semibold text-foreground flex items-center gap-1.5">
                      <Video className="h-3.5 w-3.5 text-primary" /> 2. Defensa Oral IA
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      Preguntas conceptuales adaptativas en tiempo real para verificar autoría genuina.
                    </p>
                  </div>
                  <div className="p-3 rounded-md bg-background border border-border space-y-1">
                    <p className="font-semibold text-foreground flex items-center gap-1.5">
                      <ShieldCheck className="h-3.5 w-3.5 text-primary" /> 3. Biometría Anti-Cheat
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      Liveness facial, verificación de voz única y monitoreo activo de pantalla.
                    </p>
                  </div>
                </div>
              </div>

              {authUser?.id === p.public_uuid && (
                <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-4 rounded-lg bg-primary/5 border border-primary/20">
                  <div className="text-xs space-y-0.5">
                    <p className="font-bold text-primary flex items-center gap-1.5">
                      <Sparkles className="h-4 w-4" /> ¿Eres el titular de este pasaporte?
                    </p>
                    <p className="text-muted-foreground">
                      Rinde la prueba técnica práctica para certificar tus habilidades y destacar en los resultados de búsqueda.
                    </p>
                  </div>
                  <Link to="/app/teaching-skills">
                    <Button size="sm" className="bg-[#00786F] hover:bg-[#006058] dark:bg-primary dark:hover:bg-primary/90 text-white font-bold text-xs gap-1.5 shrink-0 shadow-sm">
                      Gestionar Habilidades <ArrowRight className="h-3.5 w-3.5" />
                    </Button>
                  </Link>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Sección 3: Confianza Comunitaria & Habilidades Acreditadas (HU-40) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Card: Puntaje de Confianza e Insignias */}
          <Card className="border-border bg-card shadow-sm">
            <CardContent className="p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-base text-foreground flex items-center gap-2">
                  <Star className="h-4 w-4 text-amber-500 fill-amber-500" /> Confianza Comunitaria
                </h3>
                <span className="text-xs font-bold text-primary">{p.trust_score}% Confianza</span>
              </div>

              <div className="flex items-center gap-4 p-3 rounded-lg bg-muted/30 border border-border">
                <div className="text-2xl font-black text-amber-500 dark:text-amber-400 flex items-center gap-1">
                  {p.overall_rating.toFixed(1)} <Star className="h-5 w-5 fill-amber-500" />
                </div>
                <div className="text-xs text-muted-foreground">
                  Basado en {p.total_reviews} evaluaciones bilaterales auditadas de estudiantes.
                </div>
              </div>

              {/* Insignias activas */}
              <div className="space-y-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                  Insignias de Confianza Activas:
                </span>
                <div className="flex flex-wrap gap-2">
                  {p.badges.map((b) => (
                    <Badge
                      key={b.code}
                      variant="outline"
                      className="border-primary/30 bg-primary/5 text-primary text-[11px] font-semibold gap-1.5 py-1 px-2.5"
                    >
                      {getBadgeIcon(b.icon)}
                      {b.title}
                    </Badge>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Card: Competencias y Habilidades */}
          <Card className="border-border bg-card shadow-sm">
            <CardContent className="p-6 space-y-4">
              <h3 className="font-bold text-base text-foreground flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-primary" /> Habilidades Registradas
              </h3>

              <div className="space-y-2.5">
                {p.skills.length === 0 ? (
                  <p className="text-xs text-muted-foreground italic">No registra habilidades públicas.</p>
                ) : (
                  p.skills.map((sk) => (
                    <div
                      key={sk.id}
                      className="flex items-center justify-between p-2.5 rounded-lg bg-muted/30 border border-border text-xs"
                    >
                      <div>
                        <p className="font-semibold text-foreground">{sk.name}</p>
                        <p className="text-[10px] text-muted-foreground">{sk.category_name} · {sk.years_of_experience} años exp.</p>
                      </div>
                      <Badge
                        className={
                          sk.status === "VERIFICADA"
                            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 text-[10px] font-bold"
                            : "bg-muted text-muted-foreground border-border text-[10px]"
                        }
                      >
                        {sk.status === "VERIFICADA" ? "✓ Verificada con IA" : "Declarada"}
                      </Badge>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Footer Institucional */}
        <div className="text-center py-6 text-xs text-muted-foreground space-y-1">
          <p>
            Este Pasaporte de Habilidades es emitido soberanamente bajo el protocolo criptográfico de <strong>SkillMatch</strong>.
          </p>
          <p className="font-mono text-[11px]">
            Firma verificable: {p.verification_hash} · URL canónica: {p.public_shareable_url}
          </p>
        </div>
      </div>

      {/* Modal Interactivo de Código QR */}
      <Dialog open={isQrModalOpen} onOpenChange={(open) => !open && closeQrModal()}>
        <DialogContent className="sm:max-w-md border-border bg-card text-card-foreground">
          <DialogHeader className="text-center items-center">
            <div className="w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center mb-1">
              <QrCode className="w-5 h-5" />
            </div>
            <DialogTitle className="text-lg font-bold">Código QR del Pasaporte</DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground text-center">
              Escanea este código con cualquier cámara móvil para verificar al instante las credenciales y el dossier técnico.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col items-center justify-center p-6 bg-white rounded-xl border border-border shadow-xs my-2">
            <img
              src={p.qr_endpoint_url}
              alt={`Código QR del Pasaporte de ${p.full_name}`}
              className="w-56 h-56 object-contain"
            />
            <p className="text-[11px] text-slate-500 font-mono mt-3 text-center truncate max-w-xs">
              {p.public_shareable_url}
            </p>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" size="sm" onClick={copyShareableLink} className="gap-1.5 text-xs">
              <Copy className="h-3.5 w-3.5" /> Copiar Enlace
            </Button>
            <a href={p.qr_endpoint_url} download={`qr-pasaporte-${p.public_uuid}.png`}>
              <Button size="sm" className="bg-[#00786F] hover:bg-[#006058] dark:bg-primary dark:hover:bg-primary/90 text-white font-bold text-xs gap-1.5">
                <Download className="h-3.5 w-3.5" /> Descargar QR
              </Button>
            </a>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
