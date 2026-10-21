import { Link, useLocation } from "react-router-dom"
import { Home, Users, Calendar, Award, ShieldCheck, Bell, Plus, Search, CreditCard } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuthStore } from "@/stores"
import { ModeToggle } from "@/components/mode-toggle"

export function PlatformHeader() {
  const location = useLocation()
  const path = location.pathname
  const { user, logout } = useAuthStore()

  const navItems = [
    { label: "Inicio", icon: Home, to: "/app", active: path === "/app" },
    { label: "Matches y Comunidad", icon: Users, to: "/app/swaps", active: path === "/app/swaps", badge: 3 },
    { label: "Agenda y Disponibilidad", icon: Calendar, to: "/app/availability", active: path === "/app/availability" },
    { label: "Certificados de IA", icon: Award, to: "/app/certificates", active: path === "/app/certificates" },
    { label: "Pasaporte de Confianza", icon: ShieldCheck, to: "/app/profile", active: path === "/app/profile" },
  ]

  return (
    <header className="sticky top-0 z-40 w-full border-b bg-card text-card-foreground">
      <div className="flex h-14 items-center justify-between px-4 sm:px-6">
        {/* Left: Brand Circular Badge + Rounded Search Pill */}
        <div className="flex items-center gap-3 w-1/4">
          <Link to="/app" className="flex items-center gap-2 shrink-0">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-primary-foreground font-black text-sm shadow-xs">
              SM
            </div>
          </Link>

          <div className="relative hidden xl:block w-64">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Buscar en SkillMatch..."
              className="h-9 w-full rounded-full bg-muted/60 pl-9 pr-4 text-xs border-transparent focus-visible:border-primary focus-visible:bg-background"
            />
          </div>
        </div>

        {/* Center: Facebook-style Top Navigation with Underline Indicator */}
        <nav className="flex items-center justify-center gap-1 sm:gap-2 w-2/4">
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <Tooltip key={item.to}>
                <TooltipTrigger asChild>
                  <Link
                    to={item.to}
                    className={`relative flex h-14 w-12 sm:w-16 items-center justify-center transition-colors ${
                      item.active
                        ? "text-primary border-b-2 border-primary"
                        : "text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                    }`}
                  >
                    <Icon className="h-5 w-5" />
                    {item.badge ? (
                      <span className="absolute top-2.5 right-2 sm:right-3.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-[#E7000B] px-1 text-[9px] font-black text-white">
                        {item.badge}
                      </span>
                    ) : null}
                  </Link>
                </TooltipTrigger>
                <TooltipContent side="bottom" sideOffset={6}>
                  <p className="text-xs font-medium">{item.label}</p>
                </TooltipContent>
              </Tooltip>
            )
          })}
        </nav>

        {/* Right: Wallet Pill + Bell + User Avatar */}
        <div className="flex items-center justify-end gap-2.5 w-1/4">
          {/* Wallet Pill with + Icon */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Link
                to="/app/wallet"
                className="flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs font-semibold hover:bg-muted/50 transition-colors"
              >
                <CreditCard className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="font-bold text-foreground">150 pts</span>
                <div className="flex h-4 w-4 items-center justify-center rounded-full bg-primary text-primary-foreground ml-0.5">
                  <Plus className="h-3 w-3 stroke-[3]" />
                </div>
              </Link>
            </TooltipTrigger>
            <TooltipContent>
              <p className="text-xs">Billetera de SkillPoints (150 pts disponibles)</p>
            </TooltipContent>
          </Tooltip>

          {/* Bell Icon with dot */}
          <Link
            to="/app/notifications"
            className="relative flex h-9 w-9 items-center justify-center rounded-full text-muted-foreground hover:bg-muted/60 hover:text-foreground transition-colors"
          >
            <Bell className="h-5 w-5" />
            <span className="absolute top-2 right-2 h-2 w-2 rounded-full bg-[#E7000B]" />
          </Link>

          <ModeToggle />

          {/* User Avatar Circle */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="relative h-9 w-9 rounded-full p-0">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-primary-foreground font-black text-xs">
                  {user?.fullName?.split(" ").map(n => n[0]).join("").slice(0, 2) || "CM"}
                </div>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel className="font-normal">
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-semibold leading-none">{user?.fullName || "Carlos Méndez"}</p>
                  <p className="text-xs leading-none text-muted-foreground">@carlos.dev</p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link to="/app/profile">Mi Perfil & Pasaporte</Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/app/swaps">Mis Intercambios</Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/app/exam-demo">Sandbox de Evaluación IA</Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => logout()} asChild>
                <Link to="/">Cerrar Sesión</Link>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  )
}
