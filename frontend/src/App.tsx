import { RouterProvider } from "react-router-dom"
import { router } from "@/routes"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Toaster } from "@/components/ui/sonner"

export function App() {
  return (
    <TooltipProvider>
      <RouterProvider router={router} />
      <Toaster />
    </TooltipProvider>
  )
}

export default App
