import { useEffect, useRef } from 'react'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Sparkles, Trash2, Bot, User, Loader2 } from 'lucide-react'
import { useAssistantStore } from '@/stores/assistant-store'
import { AssistantInput } from './assistant-input'
import { AssistantActions } from './assistant-actions'
import type { ChatHistoryItem } from '@/types/assistant'

export function AssistantChatDrawer() {
  const isOpen = useAssistantStore((s) => s.isOpen)
  const closeAssistant = useAssistantStore((s) => s.closeAssistant)
  const messages = useAssistantStore((s) => s.messages)
  const isLoading = useAssistantStore((s) => s.isLoading)
  const suggestedPrompts = useAssistantStore((s) => s.suggestedPrompts)
  const sendMessage = useAssistantStore((s) => s.sendMessage)
  const clearConversation = useAssistantStore((s) => s.clearConversation)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTo({
        top: scrollContainerRef.current.scrollHeight,
        behavior,
      })
    } else {
      messagesEndRef.current?.scrollIntoView({ behavior })
    }
  }

  // Auto-scroll al recibir mensajes
  useEffect(() => {
    if (isOpen) {
      const timer = setTimeout(() => {
        scrollToBottom('smooth')
      }, 60)
      return () => clearTimeout(timer)
    }
  }, [messages, isLoading, isOpen])

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && closeAssistant()}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[420px] p-0 flex flex-col h-[100dvh] max-h-[100dvh] overflow-hidden bg-background border-l border-border/80 shadow-2xl z-[100] gap-0"
      >
        {/* Encabezado */}
        <SheetHeader className="px-4 py-3 border-b border-border flex flex-row items-center justify-between space-y-0 bg-muted/20 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-full bg-emerald-600 text-white flex items-center justify-center shadow-sm">
              <Bot className="h-4.5 w-4.5" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <SheetTitle className="text-sm font-bold text-foreground">
                  SkillMatch Copilot
                </SheetTitle>
                <Badge
                  variant="outline"
                  className="text-[9px] px-1 py-0 border-emerald-500/40 text-emerald-400 bg-emerald-950/30"
                >
                  Gemini Flash
                </Badge>
              </div>
              <p className="text-[11px] text-muted-foreground flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 inline-block" />
                Asistente oficial inteligente
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1 pr-6">
            {messages.length > 0 && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => void clearConversation()}
                title="Limpiar conversación"
                aria-label="Limpiar conversación"
                className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10 cursor-pointer rounded-full"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>
        </SheetHeader>

        {/* Lista de Mensajes con Scroll Fluido y Táctil */}
        <div
          ref={scrollContainerRef}
          data-slot="assistant-messages-container"
          className="flex-1 min-h-0 overflow-y-auto px-4 py-3.5 space-y-3.5 overscroll-contain touch-pan-y"
          style={{ WebkitOverflowScrolling: 'touch' }}
        >
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-4 my-auto min-h-[300px]">
              <div className="h-14 w-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center">
                <Sparkles className="h-7 w-7" />
              </div>
              <div className="space-y-1">
                <h4 className="text-sm font-semibold text-foreground">
                  ¡Hola! ¿En qué puedo ayudarte hoy?
                </h4>
                <p className="text-xs text-muted-foreground max-w-[280px]">
                  Puedo consultar tu saldo de puntos, tus próximas sesiones, buscar tutores o responder dudas sobre SkillMatch.
                </p>
              </div>

              {/* Píldoras de bienvenida */}
              <div className="w-full space-y-1.5 pt-2">
                <p className="text-[10px] uppercase font-semibold text-muted-foreground tracking-wider">
                  Preguntas sugeridas
                </p>
                <div className="flex flex-col gap-1.5">
                  {suggestedPrompts.map((prompt, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => void sendMessage(prompt)}
                      className="text-left text-xs p-2.5 rounded-xl bg-muted/50 hover:bg-emerald-950/30 hover:border-emerald-500/40 border border-border/70 text-foreground transition-all cursor-pointer"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-3.5 pb-2">
              {messages.map((msg: ChatHistoryItem) => {
                const isUser = msg.role === 'user'
                return (
                  <div
                    key={msg.id}
                    className={`flex gap-2.5 ${isUser ? 'justify-end' : 'justify-start'}`}
                  >
                    {!isUser && (
                      <div className="h-7 w-7 rounded-full bg-emerald-600/90 text-white flex items-center justify-center shrink-0 mt-0.5 text-xs">
                        <Bot className="h-3.5 w-3.5" />
                      </div>
                    )}

                    <div className={`max-w-[85%] ${isUser ? 'items-end' : 'items-start'}`}>
                      <div
                        className={`rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed whitespace-pre-wrap ${
                          isUser
                            ? 'bg-emerald-600 text-white rounded-tr-xs'
                            : 'bg-muted/70 text-foreground border border-border/60 rounded-tl-xs shadow-xs'
                        }`}
                      >
                        {msg.content}
                      </div>

                      {/* Tarjetas de acciones interactivas */}
                      {!isUser && msg.action && <AssistantActions action={msg.action} />}

                      <span className="text-[9px] text-muted-foreground/60 px-1 mt-0.5 block">
                        {new Date(msg.timestamp).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>

                    {isUser && (
                      <div className="h-7 w-7 rounded-full bg-muted text-muted-foreground flex items-center justify-center shrink-0 mt-0.5 text-xs">
                        <User className="h-3.5 w-3.5" />
                      </div>
                    )}
                  </div>
                )
              })}

              {isLoading && (
                <div className="flex gap-2.5 justify-start">
                  <div className="h-7 w-7 rounded-full bg-emerald-600/90 text-white flex items-center justify-center shrink-0 text-xs">
                    <Bot className="h-3.5 w-3.5" />
                  </div>
                  <div className="rounded-2xl rounded-tl-xs px-3.5 py-2.5 bg-muted/70 border border-border/60 text-xs flex items-center gap-2 text-muted-foreground">
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-emerald-500" />
                    <span>Pensando y consultando datos...</span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Píldoras de sugerencias rápidas arriba del input cuando hay mensajes */}
        {messages.length > 0 && suggestedPrompts.length > 0 && !isLoading && (
          <div className="px-3 py-1.5 flex gap-1.5 overflow-x-auto no-scrollbar border-t border-border/40 bg-muted/10 shrink-0">
            {suggestedPrompts.slice(0, 3).map((prompt, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => void sendMessage(prompt)}
                className="shrink-0 text-[10px] font-medium px-2.5 py-1 rounded-full bg-muted/60 hover:bg-emerald-950/40 hover:text-emerald-400 border border-border/60 text-muted-foreground transition-colors cursor-pointer"
              >
                {prompt}
              </button>
            ))}
          </div>
        )}

        {/* Entrada de mensaje */}
        <AssistantInput onSendMessage={(txt) => void sendMessage(txt)} isLoading={isLoading} />
      </SheetContent>
    </Sheet>
  )
}
