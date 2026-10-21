import * as React from "react"
import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { ModeToggle } from "@/components/mode-toggle"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { ArrowRight, Menu } from "lucide-react"

export function PublicNavbar() {
  const [open, setOpen] = React.useState(false)

  const handleScroll = (e: React.MouseEvent<HTMLAnchorElement>, targetId: string) => {
    e.preventDefault()
    setOpen(false)
    const element = document.getElementById(targetId)
    if (element) {
      element.scrollIntoView({ behavior: "smooth" })
      window.history.pushState(null, "", `#${targetId}`)
    }
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b border-[#E3E7E8] dark:border-border bg-white/95 dark:bg-card/95 backdrop-blur-md">
      <div className="container mx-auto flex h-[54px] sm:h-16 max-w-7xl items-center justify-between px-4 sm:px-8">
        {/* Left Side: Hamburger (Mobile/Tablet < lg) + Brand */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Mobile/Tablet Menu Bar on the LEFT (< lg) */}
          <div className="lg:hidden">
            <Sheet open={open} onOpenChange={setOpen}>
              <SheetTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-[#090B0C] dark:text-foreground -ml-1.5"
                  aria-label="Abrir menú"
                >
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-[280px] sm:w-[320px] p-6 flex flex-col justify-between">
                <div className="space-y-6">
                  <SheetHeader className="p-0 text-left">
                    <SheetTitle className="text-xl font-black text-[#00786F] dark:text-primary">
                      SkillMatch
                    </SheetTitle>
                  </SheetHeader>

                  <nav className="flex flex-col space-y-4 text-sm font-semibold text-foreground">
                    <a
                      href="#como-funciona"
                      onClick={(e) => handleScroll(e, "como-funciona")}
                      className="transition-colors hover:text-[#00786F]"
                    >
                      Cómo Funciona
                    </a>
                    <a
                      href="#ia-demo"
                      onClick={(e) => handleScroll(e, "ia-demo")}
                      className="transition-colors hover:text-[#00786F]"
                    >
                      Validación IA
                    </a>
                    <a
                      href="#catalogo"
                      onClick={(e) => handleScroll(e, "catalogo")}
                      className="transition-colors hover:text-[#00786F]"
                    >
                      Catálogo
                    </a>
                    <a
                      href="#confianza"
                      onClick={(e) => handleScroll(e, "confianza")}
                      className="transition-colors hover:text-[#00786F]"
                    >
                      Confianza & Escrow
                    </a>
                    <a
                      href="#metricas"
                      onClick={(e) => handleScroll(e, "metricas")}
                      className="transition-colors hover:text-[#00786F]"
                    >
                      Estadísticas
                    </a>
                  </nav>
                </div>

                {/* Action Buttons in Mobile Sheet */}
                <div className="flex flex-col gap-2.5 pt-6 border-t">
                  <Button variant="outline" asChild className="w-full text-xs font-semibold justify-center">
                    <Link to="/app" onClick={() => setOpen(false)}>
                      Iniciar Sesión
                    </Link>
                  </Button>
                  <Button
                    asChild
                    className="w-full bg-[#00786F] hover:bg-[#00786F]/90 text-[#F0FDFA] text-xs font-bold justify-center"
                  >
                    <Link to="/app" onClick={() => setOpen(false)} className="flex items-center gap-1.5">
                      <span>Empezar Gratis</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </Button>
                </div>
              </SheetContent>
            </Sheet>
          </div>

          {/* Brand */}
          <Link to="/" className="flex items-center gap-2 shrink-0">
            <span className="font-black text-base sm:text-xl tracking-tight text-[#00786F] dark:text-primary">
              SkillMatch
            </span>
          </Link>
        </div>

        {/* Center Nav for Desktop (>= lg) with responsive gaps and text size to never squish */}
        <nav className="hidden lg:flex items-center gap-4 xl:gap-7 text-[11px] xl:text-xs font-semibold text-muted-foreground">
          <a
            href="#como-funciona"
            onClick={(e) => handleScroll(e, "como-funciona")}
            className="transition-colors hover:text-foreground shrink-0"
          >
            Cómo Funciona
          </a>
          <a
            href="#ia-demo"
            onClick={(e) => handleScroll(e, "ia-demo")}
            className="transition-colors hover:text-foreground shrink-0"
          >
            Validación IA
          </a>
          <a
            href="#catalogo"
            onClick={(e) => handleScroll(e, "catalogo")}
            className="transition-colors hover:text-foreground shrink-0"
          >
            Catálogo
          </a>
          <a
            href="#confianza"
            onClick={(e) => handleScroll(e, "confianza")}
            className="transition-colors hover:text-foreground shrink-0"
          >
            Confianza & Escrow
          </a>
          <a
            href="#metricas"
            onClick={(e) => handleScroll(e, "metricas")}
            className="transition-colors hover:text-foreground shrink-0"
          >
            Estadísticas
          </a>
        </nav>

        {/* Right Actions: Desktop (>= lg) */}
        <div className="hidden lg:flex items-center gap-2 xl:gap-3 shrink-0">
          <ModeToggle />
          <Button variant="ghost" size="sm" asChild className="text-[11px] xl:text-xs font-semibold px-2.5 xl:px-3">
            <Link to="/app">Iniciar Sesión</Link>
          </Button>
          <Button
            size="sm"
            asChild
            className="bg-[#00786F] hover:bg-[#00786F]/90 text-[#F0FDFA] text-[11px] xl:text-xs font-bold h-8 xl:h-9 px-3 xl:px-4 rounded-md xl:rounded-lg shadow-xs"
          >
            <Link to="/app" className="flex items-center gap-1.5">
              <span>Empezar Gratis</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </Button>
        </div>

        {/* Right Actions: Mobile/Tablet (< lg) */}
        <div className="flex lg:hidden items-center gap-2">
          <ModeToggle />
          <Button
            size="sm"
            asChild
            className="bg-[#00786F] hover:bg-[#00786F]/90 text-[#F0FDFA] text-[11px] font-bold h-8 px-3 rounded-md shadow-xs"
          >
            <Link to="/app">Entrar</Link>
          </Button>
        </div>
      </div>
    </header>
  )
}
