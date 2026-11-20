import * as React from "react"
import { Outlet, useLocation, useNavigate } from "react-router-dom"
import { PlatformHeader } from "@/components/navigation/platform-header"
import { PlatformSidebar } from "@/components/navigation/platform-sidebar"
import { MobileBottomBar } from "@/components/navigation/mobile-bottom-bar"
import { AssistantFab } from "@/components/assistant/assistant-fab"
import { AssistantChatDrawer } from "@/components/assistant/assistant-chat-drawer"
import { initializeNativePushNotifications } from "@/services/native-push-service"

export function PlatformLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const isFeed =
    location.pathname === "/app" ||
    location.pathname === "/app/"
  const isProfile = location.pathname.startsWith("/app/profile")

  React.useEffect(() => {
    void initializeNativePushNotifications(() => {
      navigate("/app/notifications")
    })
  }, [navigate])

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
      <AssistantFab />
      <AssistantChatDrawer />
    </div>
  )
}
