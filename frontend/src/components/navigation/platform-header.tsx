import { useEffect } from "react"
import { NotificationBell } from "@/components/notifications/notification-bell"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { Home, Users, Calendar, Award, ShieldCheck, Plus, Search, CreditCard, LogOut } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
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
import { useWalletStore } from "@/stores/wallet-store"
import { logoutSession } from "@/services/auth-service"
import { ModeToggle } from "@/components/mode-toggle"

export function PlatformHeader() {
  const location = useLocation()
  const navigate = useNavigate()
  const path = location.pathname
  const { user } = useAuthStore()

  const handleLogout = async () => {
    await logoutSession()
    navigate("/login", { replace: true })
  }

  const userInitials =
    user?.fullName
      ?.split(" ")
      .map((n) => n[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() || "MB"

  const balancePoints = user?.skillPointsBalance ?? 0

  useEffect(() => {
    if (user?.id) {
      useWalletStore.getState().loadBalance()
    }
  }, [user?.id])


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
        <div className="flex items-center gap-3 shrink-0 xl:w-72">
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
        <nav className="hidden md:flex flex-1 min-w-0 items-center justify-center gap-1 lg:gap-2">
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <Tooltip key={item.to}>
                <TooltipTrigger asChild>
                  <Link
                    to={item.to}
                    className={`relative flex h-14 w-11 md:w-12 lg:w-14 shrink-0 items-center justify-center transition-colors ${
                      item.active
                        ? "text-primary border-b-2 border-primary"
                        : "text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                    }`}
                  >
                    <Icon className="size-[22px] stroke-[2.1]" />
                    {item.badge ? (
                      <span className="absolute top-2.5 right-1 md:right-1.5 lg:right-2 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-[#E7000B] px-1 text-[9px] font-black text-white">
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
        <div className="flex items-center justify-end gap-1.5 sm:gap-2 lg:gap-2.5 shrink-0 xl:w-72">
          {/* Wallet Pill with + Icon */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Link
                to="/app/wallet"
                className="flex items-center gap-1 sm:gap-1.5 rounded-full border border-border bg-card px-2.5 sm:px-3 py-1 text-xs font-semibold hover:bg-muted/50 transition-colors shrink-0"
              >
                <CreditCard className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-muted-foreground shrink-0" />
                <span className="font-bold text-foreground whitespace-nowrap">{balancePoints} SP</span>
                <div className="flex h-3.5 w-3.5 sm:h-4 sm:w-4 items-center justify-center rounded-full bg-primary text-primary-foreground ml-0.5 shrink-0">
                  <Plus className="h-2.5 w-2.5 sm:h-3 sm:w-3 stroke-[3]" />
                </div>
              </Link>
            </TooltipTrigger>
            <TooltipContent>
              <p className="text-xs">Billetera de SkillPoints ({balancePoints} SP disponibles)</p>
            </TooltipContent>
          </Tooltip>

          <NotificationBell />

          <ModeToggle />

          {/* User Avatar Circle */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="relative h-9 w-9 rounded-full p-0 shrink-0">
                <Avatar className="h-9 w-9">
                  {user?.avatarUrl ? (
                    <AvatarImage src={user.avatarUrl} alt={user.fullName} />
                  ) : null}
                  <AvatarFallback className="bg-primary text-primary-foreground font-black text-xs">
                    {userInitials}
                  </AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel className="font-normal">
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-semibold leading-none">{user?.fullName || "Miembro de la Comunidad"}</p>
                  {user?.email && (
                    <p className="text-xs leading-none text-muted-foreground">{user.email}</p>
                  )}
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link to="/app/profile">Mi Perfil & Pasaporte</Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/app/teaching-skills">Mis Habilidades para Enseñar</Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/app/learning-skills">Habilidades que Deseo Aprender</Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/app/swaps">Mis Intercambios</Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={handleLogout}
                className="cursor-pointer text-destructive focus:text-destructive flex items-center justify-between"
              >
                <span>Cerrar Sesión</span>
                <LogOut className="h-4 w-4" />
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  )
}
