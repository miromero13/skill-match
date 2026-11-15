import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Card, CardContent } from "@/components/ui/card"
import { useAuthStore } from "@/stores/auth-store"
import { TeachingSkillsSection } from "@/pages/teaching-skills-page"

export function ProfilePage() {
  const user = useAuthStore((state) => state.user)
  const initials =
    user?.fullName
      .split(" ")
      .map((word) => word[0])
      .join("")
      .slice(0, 2) || "SM"
  return (
    <div className="mx-auto max-w-4xl py-4 md:py-6">
      <Card className="mx-4 md:mx-6">
        <CardContent className="flex items-center gap-4 p-5">
          <Avatar className="size-14">
            <AvatarImage src={user?.avatarUrl} alt="" />
            <AvatarFallback className="bg-primary/10 font-semibold text-primary">
              {initials}
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold break-words">
              {user?.fullName || "Mi perfil"}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Tus habilidades y los enlaces que respaldan tu experiencia.
            </p>
          </div>
        </CardContent>
      </Card>
      <TeachingSkillsSection />
    </div>
  )
}
