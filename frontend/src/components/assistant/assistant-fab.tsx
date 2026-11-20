import { Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useAssistantStore } from '@/stores/assistant-store'
import { useAuthStore } from '@/stores/auth-store'

export function AssistantFab() {
  const user = useAuthStore((s) => s.user)
  const isOpen = useAssistantStore((s) => s.isOpen)
  const toggleAssistant = useAssistantStore((s) => s.toggleAssistant)

  // Solo mostrar para usuarios con rol MEMBER autenticados
  if (!user || user.role !== 'MEMBER') {
    return null
  }

  return (
    <div
      className="fixed z-[60] bottom-[calc(76px+env(safe-area-inset-bottom,0px))] md:bottom-6 right-5 md:right-6 pointer-events-auto"
      style={{ touchAction: 'manipulation' }}
    >
      <Button
        onClick={() => toggleAssistant()}
        aria-label={isOpen ? 'Cerrar Asistente Virtual' : 'Abrir Asistente Virtual'}
        className="relative h-13 w-13 md:h-14 md:w-14 rounded-full p-0 bg-emerald-600 hover:bg-emerald-700 text-white shadow-xl shadow-emerald-950/40 active:scale-90 transition-transform duration-200 border-2 border-emerald-400/40 flex items-center justify-center cursor-pointer pointer-events-auto"
      >
        <span className="absolute -top-1 -right-1 flex h-3.5 w-3.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-emerald-500 border-2 border-background" />
        </span>
        <Sparkles className="h-6 w-6 text-white animate-pulse" />
      </Button>
    </div>
  )
}
