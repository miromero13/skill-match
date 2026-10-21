import { Outlet } from "react-router-dom"
import { PublicNavbar } from "@/components/navigation/public-navbar"
import { PublicFooter } from "@/components/navigation/public-footer"

export function PublicLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <PublicNavbar />
      <main className="flex-1">
        <Outlet />
      </main>
      <PublicFooter />
    </div>
  )
}
