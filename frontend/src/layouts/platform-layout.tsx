import { Outlet } from "react-router-dom"
import { PlatformHeader } from "@/components/navigation/platform-header"
import { PlatformSidebar } from "@/components/navigation/platform-sidebar"
import { MobileBottomBar } from "@/components/navigation/mobile-bottom-bar"

export function PlatformLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <PlatformHeader />
      <div className="flex flex-1">
        <PlatformSidebar />
        <main className="flex-1 overflow-y-auto pb-[54px] md:pb-0">
          <Outlet />
        </main>
      </div>
      <MobileBottomBar />
    </div>
  )
}
