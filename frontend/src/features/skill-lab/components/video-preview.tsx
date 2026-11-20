import { useCallback, useEffect, useRef, useState, type ReactNode, type SyntheticEvent } from "react"
import { Loader2, VideoOff } from "lucide-react"
import { cn } from "cn"
import { AspectRatio } from "@/components/ui/aspect-ratio"
import { Card } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { skillLabApi } from "../api/skill-lab-api"

/** Margen ante desfase de reloj: un error cerca del vencimiento se trata como token vencido. */
const EXPIRY_MARGIN_MS = 30_000

type PreviewState =
  | { kind: "loading" }
  | { kind: "ready"; url: string; expiresAt: number }
  | { kind: "unavailable" }

function PreviewFrame({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <Card className={cn("gap-0 overflow-hidden py-0", className)}>
      <AspectRatio ratio={16 / 9} className="bg-black">
        {children}
      </AspectRatio>
    </Card>
  )
}

function UnavailableState() {
  return (
    <div className="flex size-full items-center justify-center gap-1.5 bg-muted text-xs text-muted-foreground">
      <VideoOff className="size-4" />
      Video no disponible
    </div>
  )
}

interface SampleVideoProps {
  sampleId: string
  label: string
  className?: string
}

function SampleVideo({ sampleId, label, className }: SampleVideoProps) {
  const [state, setState] = useState<PreviewState>({ kind: "loading" })
  const requestRef = useRef(0)
  const resumeAtRef = useRef(0)

  const request = useCallback(
    (requestId: number) => {
      skillLabApi.getSamplePreviewUrl(sampleId).then(
        (preview) => {
          if (requestRef.current !== requestId) return
          const expiresAt = Date.parse(preview.expires_at)
          setState({ kind: "ready", url: preview.url, expiresAt: Number.isNaN(expiresAt) ? 0 : expiresAt })
        },
        () => {
          if (requestRef.current === requestId) setState({ kind: "unavailable" })
        }
      )
    },
    [sampleId]
  )

  useEffect(() => {
    request(++requestRef.current)
    return () => {
      requestRef.current += 1
    }
  }, [request])

  const handleError = (event: SyntheticEvent<HTMLVideoElement>) => {
    // Solo un token vencido justifica pedir otra URL (una vez por URL); otro error es definitivo.
    if (state.kind !== "ready" || Date.now() < state.expiresAt - EXPIRY_MARGIN_MS) {
      setState({ kind: "unavailable" })
      return
    }
    resumeAtRef.current = event.currentTarget.currentTime
    setState({ kind: "loading" })
    request(++requestRef.current)
  }

  const handleLoadedMetadata = (event: SyntheticEvent<HTMLVideoElement>) => {
    if (resumeAtRef.current > 0) {
      event.currentTarget.currentTime = resumeAtRef.current
      resumeAtRef.current = 0
    }
  }

  return (
    <PreviewFrame className={className}>
      {state.kind === "ready" ? (
        <video
          key={state.url}
          src={state.url}
          aria-label={label}
          controls
          playsInline
          preload="metadata"
          onError={handleError}
          onLoadedMetadata={handleLoadedMetadata}
          className="size-full object-contain"
        />
      ) : state.kind === "loading" ? (
        <div className="flex size-full items-center justify-center" role="status" aria-label="Cargando video">
          <Loader2 className="size-5 animate-spin text-white/70" />
        </div>
      ) : (
        <UnavailableState />
      )}
    </PreviewFrame>
  )
}

/**
 * Reproduce una muestra guardada (S10). Pide la URL firmada al montarse (se monta al abrirse);
 * si el token vence durante la reproducción, pide una nueva una sola vez.
 */
export function VideoPreview({ sampleId, label = "Vista previa del video", className }: {
  sampleId: string
  label?: string
  className?: string
}) {
  return <SampleVideo key={sampleId} sampleId={sampleId} label={label} className={className} />
}

interface LocalVideoPreviewProps {
  file: File
  label?: string
  className?: string
}

function LocalVideo({ file, label, className }: Required<Pick<LocalVideoPreviewProps, "file" | "label">> & {
  className?: string
}) {
  const [failed, setFailed] = useState(false)
  const canPreview = typeof URL.createObjectURL === "function"

  const attachSource = useCallback(
    (video: HTMLVideoElement | null) => {
      if (!video || !canPreview) return
      const objectUrl = URL.createObjectURL(file)
      video.src = objectUrl
      return () => {
        video.removeAttribute("src")
        URL.revokeObjectURL(objectUrl)
      }
    },
    [file, canPreview]
  )

  return (
    <PreviewFrame className={className}>
      {canPreview && !failed ? (
        <video
          ref={attachSource}
          aria-label={label}
          controls
          playsInline
          preload="metadata"
          onError={() => setFailed(true)}
          className="size-full object-contain"
        />
      ) : (
        <UnavailableState />
      )}
    </PreviewFrame>
  )
}

/** Vista previa local de un archivo antes de subirlo; libera el object URL al cambiar o desmontar. */
export function LocalVideoPreview({ file, label = "Vista previa del archivo", className }: LocalVideoPreviewProps) {
  return (
    <LocalVideo
      key={`${file.name}-${file.size}-${file.lastModified}`}
      file={file}
      label={label}
      className={className}
    />
  )
}

interface SamplePreviewDialogProps {
  sampleId: string | null
  title: string
  description?: string
  onClose: () => void
}

/** Diálogo con el reproductor de una muestra; el video solo se pide mientras está abierto. */
export function SamplePreviewDialog({ sampleId, title, description, onClose }: SamplePreviewDialogProps) {
  return (
    <Dialog open={sampleId !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        {sampleId !== null && <VideoPreview sampleId={sampleId} label={title} />}
      </DialogContent>
    </Dialog>
  )
}
