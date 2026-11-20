import { useNavigate } from 'react-router-dom'
import { Calendar, CheckCircle2, ChevronRight, Coins, HelpCircle, PlusCircle, Star, User } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useWalletStore } from '@/stores/wallet-store'
import { useAssistantStore } from '@/stores/assistant-store'
import type { ChatActionPayload } from '@/types/assistant'

interface AssistantActionsProps {
  action?: ChatActionPayload | null
}

export function AssistantActions({ action }: AssistantActionsProps) {
  const navigate = useNavigate()
  const openTopupModal = useWalletStore((s) => s.openTopupModal)
  const closeAssistant = useAssistantStore((s) => s.closeAssistant)

  if (!action || !action.data) return null

  if (action.type === 'wallet_topup') {
    const data = action.data
    const available = data.available_points ?? 0
    const usd = data.usd_equivalent ?? 0
    const isVerified = data.is_verified ?? false

    return (
      <Card className="mt-3 p-3.5 bg-emerald-950/20 border-emerald-500/30 rounded-xl space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-emerald-400 font-semibold text-xs uppercase tracking-wider">
            <Coins className="h-4 w-4" />
            <span>Tu Billetera SkillMatch</span>
          </div>
          <Badge
            variant="outline"
            className={
              isVerified
                ? 'border-emerald-500/50 text-emerald-400 bg-emerald-950/40 text-[10px]'
                : 'border-amber-500/50 text-amber-400 bg-amber-950/40 text-[10px]'
            }
          >
            {isVerified ? 'KYC Verificado' : 'KYC Pendiente'}
          </Badge>
        </div>

        <div className="flex items-baseline justify-between pt-1">
          <div>
            <span className="text-2xl font-bold text-foreground">{available}</span>
            <span className="text-xs text-muted-foreground ml-1.5 font-medium">SP disponibles</span>
          </div>
          <span className="text-xs font-semibold text-emerald-400">≈ ${usd} USD</span>
        </div>

        <Button
          onClick={() => {
            closeAssistant()
            openTopupModal()
          }}
          className="w-full h-8 text-xs bg-emerald-600 hover:bg-emerald-700 text-white font-medium cursor-pointer flex items-center justify-center gap-1.5 rounded-lg"
        >
          <PlusCircle className="h-3.5 w-3.5" />
          <span>Recargar SkillPoints</span>
        </Button>
      </Card>
    )
  }

  if (action.type === 'instructor_card') {
    const instructors = action.data.instructors || []
    if (instructors.length === 0) return null

    return (
      <div className="mt-3 space-y-2">
        <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
          Tutores recomendados
        </div>
        {instructors.map((t: any, idx: number) => (
          <Card
            key={t.instructor_id || idx}
            className="p-3 bg-card border-border/70 hover:border-emerald-500/40 rounded-xl transition-colors space-y-2"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <div className="h-8 w-8 rounded-full bg-emerald-950/50 text-emerald-400 border border-emerald-500/30 flex items-center justify-center shrink-0 text-xs font-bold">
                  {t.instructor_name?.charAt(0) || 'T'}
                </div>
                <div className="min-w-0">
                  <div className="text-xs font-semibold truncate text-foreground">
                    {t.instructor_name}
                  </div>
                  <div className="text-[11px] text-muted-foreground truncate">
                    {t.skill_name}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-1 text-[11px] font-medium text-amber-400 bg-amber-950/30 px-1.5 py-0.5 rounded border border-amber-500/20 shrink-0">
                <Star className="h-3 w-3 fill-amber-400" />
                <span>{t.reputation || '5.0'}</span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-1 border-t border-border/40 text-[11px]">
              <span className="text-muted-foreground">
                Nivel: <strong className="text-foreground">{t.level}</strong> ({t.experience_years}a exp)
              </span>
              <span className="font-semibold text-emerald-400">
                {t.accepts_points ? `${t.hourly_rate_sp} SP/h` : 'Intercambio'}
              </span>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                closeAssistant()
                navigate('/app/search')
              }}
              className="w-full h-7 text-[11px] cursor-pointer flex items-center justify-center gap-1 mt-1 border-emerald-500/30 text-emerald-400 hover:bg-emerald-950/30"
            >
              <span>Ver perfil y disponibilidad</span>
              <ChevronRight className="h-3 w-3" />
            </Button>
          </Card>
        ))}
      </div>
    )
  }

  if (action.type === 'sessions_list') {
    const sessions = action.data.sessions || []
    if (sessions.length === 0) return null

    return (
      <div className="mt-3 space-y-2">
        <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
          Próximas Sesiones
        </div>
        {sessions.map((s: any, idx: number) => (
          <Card
            key={s.session_id || idx}
            className="p-3 bg-card border-border/70 rounded-xl space-y-1.5"
          >
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <User className="h-3.5 w-3.5 text-emerald-400" />
                {s.counterpart_name}
              </span>
              <Badge variant="outline" className="text-[10px] border-emerald-500/40 text-emerald-400">
                {s.status}
              </Badge>
            </div>
            <div className="text-[11px] text-muted-foreground flex items-center gap-1.5">
              <Calendar className="h-3 w-3" />
              <span>{new Date(s.starts_at).toLocaleString()}</span>
              <span>•</span>
              <span className="capitalize">{s.modality?.toLowerCase()}</span>
            </div>
          </Card>
        ))}
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            closeAssistant()
            navigate('/app/sessions')
          }}
          className="w-full h-7 text-[11px] cursor-pointer flex items-center justify-center gap-1 border-border/60 text-muted-foreground hover:text-foreground"
        >
          <span>Ir a Mis Sesiones</span>
          <ChevronRight className="h-3 w-3" />
        </Button>
      </div>
    )
  }

  if (action.type === 'faq_info') {
    const topic = action.data.topic || 'Información'
    const explanation = action.data.explanation
    const rules = action.data.rules || []

    return (
      <Card className="mt-3 p-3 bg-muted/40 border-border/60 rounded-xl space-y-2 text-xs">
        <div className="flex items-center gap-1.5 font-semibold text-foreground">
          <HelpCircle className="h-3.5 w-3.5 text-emerald-400" />
          <span>{topic}</span>
        </div>
        {explanation && <p className="text-muted-foreground leading-relaxed">{explanation}</p>}
        {rules.length > 0 && (
          <ul className="space-y-1 pt-1 border-t border-border/40">
            {rules.map((r: string, idx: number) => (
              <li key={idx} className="flex items-start gap-1.5 text-muted-foreground">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0 mt-0.5" />
                <span>{r}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    )
  }

  return null
}
