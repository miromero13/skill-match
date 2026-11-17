import { RouterProvider } from "react-router-dom"
import { router } from "@/routes"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Toaster } from "@/components/ui/sonner"
import { RealtimeNotificationBridge } from "@/components/notifications/realtime-notification-bridge"

export function App() {
  return (
    <TooltipProvider>
      <RealtimeNotificationBridge />
      <RouterProvider router={router} />
      <Toaster />
    </TooltipProvider>
  )
}

export default App
