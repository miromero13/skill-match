import { useState, useEffect, useRef, type FormEvent } from 'react'
import { Send, Mic, MicOff, Loader2 } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

interface AssistantInputProps {
  onSendMessage: (text: string) => void
  isLoading: boolean
}

export function AssistantInput({ onSendMessage, isLoading }: AssistantInputProps) {
  const [text, setText] = useState('')
  const [isListening, setIsListening] = useState(false)
  const [speechSupported, setSpeechSupported] = useState(false)
  const recognitionRef = useRef<any>(null)

  useEffect(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (SpeechRecognition) {
      setSpeechSupported(true)
      const recognition = new SpeechRecognition()
      recognition.continuous = false
      recognition.interimResults = false
      recognition.lang = 'es-ES'

      recognition.onresult = (event: any) => {
        const transcript = event.results[0]?.[0]?.transcript
        if (transcript) {
          setText((prev) => (prev ? `${prev} ${transcript}` : transcript))
        }
        setIsListening(false)
      }

      recognition.onerror = () => {
        setIsListening(false)
      }

      recognition.onend = () => {
        setIsListening(false)
      }

      recognitionRef.current = recognition
    }
  }, [])

  const toggleSpeech = () => {
    if (!speechSupported || !recognitionRef.current) return

    if (isListening) {
      recognitionRef.current.stop()
      setIsListening(false)
    } else {
      try {
        recognitionRef.current.start()
        setIsListening(true)
      } catch {
        setIsListening(false)
      }
    }
  }

  const handleSubmit = (e?: FormEvent) => {
    if (e) e.preventDefault()
    if (!text.trim() || isLoading) return
    onSendMessage(text.trim())
    setText('')
    if (isListening && recognitionRef.current) {
      recognitionRef.current.stop()
      setIsListening(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="relative flex items-center gap-1.5 p-2 bg-background border-t border-border shrink-0">
      {speechSupported && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={toggleSpeech}
          aria-label={isListening ? 'Detener dictado por voz' : 'Iniciar dictado por voz'}
          className={`h-9 w-9 shrink-0 rounded-full cursor-pointer transition-colors ${
            isListening
              ? 'bg-rose-500/20 text-rose-500 hover:bg-rose-500/30 animate-pulse'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted'
          }`}
        >
          {isListening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
        </Button>
      )}

      <Input
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSubmit()
          }
        }}
        placeholder={isListening ? 'Escuchando tu voz...' : 'Pregunta sobre tus sesiones, saldo o tutores...'}
        disabled={isLoading}
        className="flex-1 h-9.5 text-xs bg-muted/40 border-border/70 focus-visible:ring-emerald-500 rounded-full px-3.5 placeholder:text-muted-foreground/70"
      />

      <Button
        type="submit"
        size="icon"
        disabled={!text.trim() || isLoading}
        aria-label="Enviar mensaje"
        className="h-9 w-9 shrink-0 rounded-full bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-40 cursor-pointer transition-transform active:scale-90"
      >
        {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
      </Button>
    </form>
  )
}
