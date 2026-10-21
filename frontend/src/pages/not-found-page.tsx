import { Link } from "react-router-dom"
import { Compass, Home, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4 text-foreground">
      <Card className="w-full max-w-md text-center shadow-lg border">
        <CardHeader className="space-y-3 pb-4">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-destructive/10 text-destructive">
            <AlertCircle className="h-8 w-8" />
          </div>
          <div className="space-y-1">
            <span className="font-mono text-xs font-bold uppercase tracking-wider text-muted-foreground">
              Error 404
            </span>
            <CardTitle className="text-2xl font-bold tracking-tight">
              Página no encontrada
            </CardTitle>
          </div>
          <CardDescription className="text-sm text-muted-foreground leading-relaxed">
            La ruta a la que estás intentando acceder no existe, fue reubicada o requiere permisos de acceso adicionales.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-2">
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Button asChild variant="default" className="w-full sm:w-auto">
              <Link to="/app" className="flex items-center gap-2">
                <Home className="h-4 w-4" />
                <span>Ir al Feed</span>
              </Link>
            </Button>
            <Button asChild variant="outline" className="w-full sm:w-auto">
              <Link to="/app/search" className="flex items-center gap-2">
                <Compass className="h-4 w-4" />
                <span>Explorar Habilidades</span>
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
