import { Outlet, useLocation } from "react-router-dom"
import { PlatformHeader } from "@/components/navigation/platform-header"
import { PlatformSidebar } from "@/components/navigation/platform-sidebar"
import { MobileBottomBar } from "@/components/navigation/mobile-bottom-bar"

export function PlatformLayout() {
  const location = useLocation()
  const isFeed =
    location.pathname === "/app" ||
    location.pathname === "/app/"
  const isProfile = location.pathname.startsWith("/app/profile")

  return (
    <div className="flex h-screen flex-col bg-background text-foreground overflow-hidden">
      <PlatformHeader />
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <PlatformSidebar />
        <main
          className={`min-w-0 flex-1 h-full pb-[calc(54px+env(safe-area-inset-bottom,0px))] md:pb-0 ${
            isFeed
              ? "overflow-hidden"
              : isProfile
                ? "overflow-y-auto xl:overflow-hidden"
                : "overflow-y-auto"
          }`}
        >
          <Outlet />
        </main>
      </div>
      <MobileBottomBar />
    </div>
  )
}
