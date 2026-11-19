import { Link } from "react-router-dom"
import { useAuthStore } from "@/stores/auth-store"
import {
  Wallet,
  ArrowLeftRight,
  Award,
  Star,
  AlertTriangle,
  Clock,
  ArrowLeft,
  Coins,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

interface ComingSoonPageProps {
  title: string
  subtitle: string
  description: string
  featureKey: "wallet" | "swaps" | "certificates" | "reputation" | "complaints"
}

const FEATURE_CONFIGS = {
  wallet: {
    icon: Wallet,
    tag: "Billetera de Tokens",
  },
  swaps: {
    icon: ArrowLeftRight,
    tag: "Intercambios",
  },
  certificates: {
    icon: Award,
    tag: "Acreditaciones",
  },
  reputation: {
    icon: Star,
    tag: "Comunidad",
  },
  complaints: {
    icon: AlertTriangle,
    tag: "Soporte y Mediación",
  },
}

export function ComingSoonPage({
  title,
  subtitle,
  description,
  featureKey,
}: ComingSoonPageProps) {
  const user = useAuthStore((s) => s.user)
  const config = FEATURE_CONFIGS[featureKey]
  const Icon = config.icon

  return (
    <div className="flex-1 p-4 lg:p-8 bg-muted/20 min-h-screen flex items-center justify-center">
      <Card className="w-full max-w-xl mx-auto border shadow-sm bg-card rounded-2xl">
        <CardHeader className="text-center pb-2 space-y-3">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            <Icon className="h-7 w-7" />
          </div>
          <div className="space-y-1">
            <div className="flex items-center justify-center gap-2">
              <Badge variant="outline" className="text-xs uppercase font-bold tracking-wider text-muted-foreground">
                {config.tag}
              </Badge>
              <Badge className="bg-amber-500/15 text-amber-500 hover:bg-amber-500/20 border-amber-500/30 text-xs font-semibold gap-1">
                <Clock className="h-3 w-3" />
                <span>Próximamente</span>
              </Badge>
            </div>
            <CardTitle className="text-2xl font-bold tracking-tight text-foreground">
              {title}
            </CardTitle>
            <CardDescription className="text-sm text-muted-foreground max-w-md mx-auto">
              {subtitle}
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent className="space-y-6 pt-4 text-center">
          {/* Si es la billetera, mostramos el saldo real de la cuenta */}
          {featureKey === "wallet" && (
            <div className="p-4 rounded-xl border bg-muted/30 flex items-center justify-between gap-4 text-left">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-primary/10 text-primary">
                  <Coins className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-medium">Saldo en billetera</p>
                  <p className="text-xl font-black text-foreground">
                    {user?.skillPointsBalance ?? 0} <span className="text-xs font-normal text-muted-foreground">SkillPoints</span>
                  </p>
                </div>
              </div>
              <Badge variant="secondary" className="text-[10px]">Cuenta Activa</Badge>
            </div>
          )}

          <div className="p-4 rounded-xl border border-dashed bg-muted/20 text-xs text-muted-foreground leading-relaxed">
            {description}
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <Button asChild variant="outline" size="sm" className="w-full sm:w-auto text-xs gap-1.5">
              <Link to="/app">
                <ArrowLeft className="h-3.5 w-3.5" />
                <span>Volver al Inicio</span>
              </Link>
            </Button>
            <Button asChild size="sm" className="w-full sm:w-auto text-xs">
              <Link to="/app/search">Explorar Instructores</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
