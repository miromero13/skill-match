import { useState, useEffect } from "react"
import {
    Sparkles,
    CheckCircle2,
    GraduationCap,
    Clock,
    MapPin,
    ShieldCheck,
    Loader2,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
    Popover,
    PopoverContent,
    PopoverHeader,
    PopoverTitle,
    PopoverTrigger,
} from "@/components/ui/popover"
import { getMatchCompatibility, getUserCompatibility } from "@/services/match-service"
import type { MatchCompatibility } from "@/types/match"
import { cn } from "cn"

interface CompatibilityBadgeProps {
    matchId?: string
    counterpartId?: string
    initialScore?: number | null
    compatibility?: MatchCompatibility | null
    size?: "sm" | "default" | "lg"
    className?: string
}

export function CompatibilityBadge({
    matchId,
    counterpartId,
    initialScore,
    compatibility: propCompatibility,
    size = "default",
    className,
}: CompatibilityBadgeProps) {
    const [data, setData] = useState<MatchCompatibility | null>(propCompatibility ?? null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [isOpen, setIsOpen] = useState(false)

    useEffect(() => {
        if (propCompatibility) {
            setData(propCompatibility)
        }
    }, [propCompatibility])

    const fetchDetails = async () => {
        if (data || loading) return
        if (!matchId && !counterpartId) return

        setLoading(true)
        setError(null)
        try {
            if (matchId) {
                const res = await getMatchCompatibility(matchId)
                setData(res.data)
            } else if (counterpartId) {
                const res = await getUserCompatibility(counterpartId)
                setData(res.data)
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Error al cargar afinidad")
        } finally {
            setLoading(false)
        }
    }

    const handleOpenChange = (open: boolean) => {
        setIsOpen(open)
        if (open) {
            void fetchDetails()
        }
    }

    const currentScore = data?.compatibility_score ?? initialScore ?? null

    const getScoreVariant = (score: number | null) => {
        if (score === null) return "bg-muted text-muted-foreground border-border"
        if (score >= 80) return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20"
        if (score >= 60) return "bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30 hover:bg-amber-500/20"
        return "bg-slate-500/10 text-slate-700 dark:text-slate-400 border-slate-500/30 hover:bg-slate-500/20"
    }

    const sizeClasses = {
        sm: "px-2 py-0.5 text-[11px] gap-1",
        default: "px-2.5 py-1 text-xs gap-1.5",
        lg: "px-3.5 py-1.5 text-sm gap-2 font-medium",
    }

    const badgeNode = (
        <Badge
            variant="outline"
            className={cn(
                "cursor-pointer transition-all border font-semibold shadow-xs select-none",
                sizeClasses[size],
                getScoreVariant(currentScore),
                className
            )}
            onClick={() => {
                if (!isOpen) handleOpenChange(true)
            }}
            data-testid="compatibility-badge"
        >
            <Sparkles className={cn(size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5", "text-current shrink-0")} />
            <span>{currentScore !== null ? `${currentScore}% Match` : "Afinidad"}</span>
        </Badge>
    )

    return (
        <Popover open={isOpen} onOpenChange={handleOpenChange}>
            <PopoverTrigger asChild>{badgeNode}</PopoverTrigger>
            <PopoverContent
                className="w-80 sm:w-96 p-4 text-xs z-50 space-y-3.5"
                align="start"
                data-testid="compatibility-popover"
            >
                <PopoverHeader className="pb-1 border-b border-border">
                    <div className="flex items-center justify-between">
                        <PopoverTitle className="text-sm font-bold flex items-center gap-1.5 text-foreground">
                            <Sparkles className="h-4 w-4 text-primary" />
                            Afinidad de Intercambio
                        </PopoverTitle>
                        {currentScore !== null && (
                            <span className="text-base font-extrabold text-primary">
                                {currentScore}%
                            </span>
                        )}
                    </div>
                    {data?.counterpart_name && (
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                            Cálculo algorítmico con {data.counterpart_name}
                        </p>
                    )}
                </PopoverHeader>

                {loading ? (
                    <div className="flex flex-col items-center justify-center py-6 gap-2 text-muted-foreground">
                        <Loader2 className="h-5 w-5 animate-spin text-primary" />
                        <span>Calculando matriz de afinidad…</span>
                    </div>
                ) : error ? (
                    <div className="py-3 text-center text-destructive text-xs">
                        {error}
                    </div>
                ) : data ? (
                    <div className="space-y-4">
                        {/* Desglose de 4 factores */}
                        <div className="space-y-2.5">
                            <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                                Factores Ponderados (RF-MAT-04)
                            </h4>

                            {/* Factor 1: Afinidad de Habilidades (40%) */}
                            <div className="space-y-1">
                                <div className="flex justify-between items-center text-xs">
                                    <span className="flex items-center gap-1.5 font-medium text-foreground">
                                        <GraduationCap className="h-3.5 w-3.5 text-primary shrink-0" />
                                        Habilidades ({data.factors.skill_affinity.weight}%)
                                    </span>
                                    <span className="font-semibold text-foreground">
                                        {data.factors.skill_affinity.score}/100
                                    </span>
                                </div>
                                <Progress
                                    value={data.factors.skill_affinity.score}
                                    className="h-1.5 bg-muted"
                                />
                                <p className="text-[10px] text-muted-foreground">
                                    {data.factors.skill_affinity.description}
                                </p>
                            </div>

                            {/* Factor 2: Disponibilidad Horaria (25%) */}
                            <div className="space-y-1">
                                <div className="flex justify-between items-center text-xs">
                                    <span className="flex items-center gap-1.5 font-medium text-foreground">
                                        <Clock className="h-3.5 w-3.5 text-primary shrink-0" />
                                        Disponibilidad ({data.factors.schedule_overlap.weight}%)
                                    </span>
                                    <span className="font-semibold text-foreground">
                                        {data.factors.schedule_overlap.score}/100
                                    </span>
                                </div>
                                <Progress
                                    value={data.factors.schedule_overlap.score}
                                    className="h-1.5 bg-muted"
                                />
                                <p className="text-[10px] text-muted-foreground">
                                    {data.factors.schedule_overlap.description}
                                </p>
                            </div>

                            {/* Factor 3: Modalidad y Ubicación (20%) */}
                            <div className="space-y-1">
                                <div className="flex justify-between items-center text-xs">
                                    <span className="flex items-center gap-1.5 font-medium text-foreground">
                                        <MapPin className="h-3.5 w-3.5 text-primary shrink-0" />
                                        Modalidad y Zona ({data.factors.modality_location.weight}%)
                                    </span>
                                    <span className="font-semibold text-foreground">
                                        {data.factors.modality_location.score}/100
                                    </span>
                                </div>
                                <Progress
                                    value={data.factors.modality_location.score}
                                    className="h-1.5 bg-muted"
                                />
                                <p className="text-[10px] text-muted-foreground">
                                    {data.factors.modality_location.description}
                                </p>
                            </div>

                            {/* Factor 4: Reputación y Verificación (15%) */}
                            <div className="space-y-1">
                                <div className="flex justify-between items-center text-xs">
                                    <span className="flex items-center gap-1.5 font-medium text-foreground">
                                        <ShieldCheck className="h-3.5 w-3.5 text-primary shrink-0" />
                                        Verificación IA ({data.factors.reputation_verification.weight}%)
                                    </span>
                                    <span className="font-semibold text-foreground">
                                        {data.factors.reputation_verification.score}/100
                                    </span>
                                </div>
                                <Progress
                                    value={data.factors.reputation_verification.score}
                                    className="h-1.5 bg-muted"
                                />
                                <p className="text-[10px] text-muted-foreground">
                                    {data.factors.reputation_verification.description}
                                </p>
                            </div>
                        </div>

                        {/* Razones explicativas */}
                        {data.match_reasons.length > 0 && (
                            <div className="space-y-1.5 pt-2 border-t border-border">
                                <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                                    Razones de Compatibilidad (RF-MAT-06)
                                </h4>
                                <ul className="space-y-1 text-[11px]">
                                    {data.match_reasons.map((reason, idx) => (
                                        <li key={idx} className="flex items-start gap-1.5 text-foreground">
                                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                                            <span>{reason}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="py-2 text-center text-muted-foreground text-xs">
                        Haz clic para cargar el desglose detallado de compatibilidad.
                    </div>
                )}
            </PopoverContent>
        </Popover>
    )
}
