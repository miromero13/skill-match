import { ShieldAlert, Timer, Trophy, Activity } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import type {
  ChallengeSegment,
  ChallengeSegmentType,
} from "../state/football-session-machine"

const CHALLENGE_COPY: Record<
  ChallengeSegmentType,
  { title: string; subtitle: string; badgeVariant: "default" | "secondary" | "outline" }
> = {
  LOW: {
    title: "TOQUES BAJOS",
    subtitle: "Mantén el balón por debajo de 1,5 diámetros de altura",
    badgeVariant: "secondary",
  },
  HIGH: {
    title: "TOQUES ALTOS",
    subtitle: "Eleva el balón por encima de 3 diámetros de altura",
    badgeVariant: "default",
  },
  SLOW: {
    title: "RITMO PAUSADO",
    subtitle: "Intervalo entre toques mayor a 1,0 segundo",
    badgeVariant: "outline",
  },
  FAST: {
    title: "RITMO RÁPIDO",
    subtitle: "Toques veloces con intervalo menor a 0,6 segundos",
    badgeVariant: "default",
  },
}

export interface ChallengeHudProps {
  activeCommand: ChallengeSegment | null
  remainingSeconds: number
  approximateTouchCount: number
  isSupervised?: boolean
  totalSegments?: number
}

export function ChallengeHud({
  activeCommand,
  remainingSeconds,
  approximateTouchCount,
  isSupervised = true,
  totalSegments = 4,
}: ChallengeHudProps) {
  const commandInfo = activeCommand
    ? CHALLENGE_COPY[activeCommand.tipo]
    : {
        title: "PREPARADO PARA LA ORDEN",
        subtitle: "Esperando la orden",
        badgeVariant: "outline" as const,
      }

  return (
    <div className="space-y-4 w-full" data-testid="football-challenge-hud">
      {isSupervised && (
        <Alert
          className="border-emerald-500/40 bg-emerald-500/10 text-foreground"
          data-testid="supervision-banner"
        >
          <ShieldAlert className="h-4 w-4 text-emerald-500" />
          <AlertTitle className="text-xs font-semibold uppercase tracking-wide text-emerald-600 dark:text-emerald-400">
            Supervisión Antifraude Activa
          </AlertTitle>
          <AlertDescription className="text-xs text-muted-foreground">
            No cambies de pestaña; mantén el balón en cuadro.
          </AlertDescription>
        </Alert>
      )}

      <Card className="border-border/80 shadow-md overflow-hidden">
        <CardHeader className="pb-2 flex flex-row items-center justify-between bg-secondary/30">
          <div className="flex items-center gap-2">
            <Badge variant={commandInfo.badgeVariant} className="font-mono text-xs">
              {activeCommand
                ? `Tramo ${activeCommand.indice + 1}/${totalSegments} • ${activeCommand.tipo}`
                : "Esperando inicio"}
            </Badge>
          </div>
          <div
            className="flex items-center gap-1.5 font-mono text-sm font-bold text-emerald-600 dark:text-emerald-400"
            data-testid="challenge-countdown"
          >
            <Timer className="w-4 h-4" />
            <span>{Math.max(0, remainingSeconds)}s</span>
          </div>
        </CardHeader>

        <CardContent className="pt-5 pb-6 space-y-5">
          <div className="text-center space-y-1.5">
            <p className="text-xs uppercase tracking-widest text-muted-foreground font-semibold">
              El Entrenador Dice
            </p>
            <CardTitle
              className="text-2xl sm:text-4xl font-extrabold tracking-tight text-foreground"
              data-testid="challenge-command-title"
            >
              {commandInfo.title}
            </CardTitle>
            <p className="text-xs sm:text-sm text-muted-foreground">
              {commandInfo.subtitle}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 pt-2 border-t border-border/60">
            <div className="p-3 rounded-lg bg-secondary/40 flex items-center justify-between">
              <div className="space-y-0.5">
                <span className="text-[11px] text-muted-foreground block">
                  Toques en vivo (aprox.)
                </span>
                <span
                  className="text-xl font-bold font-mono text-foreground"
                  data-testid="live-touch-counter"
                >
                  {approximateTouchCount}
                </span>
              </div>
              <Activity className="w-5 h-5 text-emerald-500 opacity-80" />
            </div>

            <div className="p-3 rounded-lg bg-secondary/40 flex items-center justify-between">
              <div className="space-y-0.5">
                <span className="text-[11px] text-muted-foreground block">
                  Tiempo restante
                </span>
                <span className="text-xl font-bold font-mono text-foreground">
                  {Math.max(0, remainingSeconds)} s
                </span>
              </div>
              <Trophy className="w-5 h-5 text-amber-500 opacity-80" />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
