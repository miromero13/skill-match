import { useEffect, useRef, useState } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Video,
  Mic,
  Code,
  UploadCloud,
  Play,
  Square,
  Trash2,
  ShieldCheck,
  Hash,
  Cpu,
  RefreshCw,
  FileCheck,
  CheckCircle2,
  AlertCircle,
  FileCode,
} from "lucide-react"
import { useDatasetCaptureStore } from "@/stores/dataset-capture-store"

export function AdminDatasetCapturePage() {
  const {
    isRecording,
    recordingDurationSeconds,
    recordingMode,
    recordedBlob,
    recordedFileName,
    recordedFileHash,
    mediaStream,
    discipline,
    challenge,
    hardwareInfo,
    signedConsent,
    codeContent,
    participantId,
    levelLabel,
    manualTouchCount,
    noiseLevel,
    surface,
    split,
    samples,
    totalCount,
    isLoading,
    isUploading,
    error,
    lastUploadMessage,
    clearLastUploadMessage,
    setRecordingMode,
    setDiscipline,
    setChallenge,
    setHardwareInfo,
    setSignedConsent,
    setCodeContent,
    setParticipantId,
    setLevelLabel,
    setManualTouchCount,
    setNoiseLevel,
    setSurface,
    setSplit,
    setMediaStream,
    setRecordedBlob,
    setRecordingDurationSeconds,
    setIsRecording,
    resetRecording,
    fetchSamples,
    uploadCurrentCapture,
    deleteSampleById,
  } = useDatasetCaptureStore()

  const videoPreviewRef = useRef<HTMLVideoElement>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const timerIntervalRef = useRef<number | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const [filterDiscipline, setFilterDiscipline] = useState<string>("all")

  useEffect(() => {
    fetchSamples()
  }, [fetchSamples])

  // Sincronizar video preview con mediaStream
  useEffect(() => {
    if (videoPreviewRef.current && mediaStream) {
      videoPreviewRef.current.srcObject = mediaStream
    }
  }, [mediaStream])

  // Limpieza al desmontar
  useEffect(() => {
    return () => {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current)
      if (mediaStream) {
        mediaStream.getTracks().forEach((track) => track.stop())
      }
    }
  }, [mediaStream])

  const formatTimer = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60)
    const secs = totalSeconds % 60
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`
  }

  const startMediaRecording = async (mode: "video" | "audio") => {
    resetRecording()
    try {
      if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
        throw new Error("El navegador o dispositivo no soporta captura multimedia nativa.")
      }

      const constraints: MediaStreamConstraints =
        mode === "video"
          ? { video: { width: 1280, height: 720 }, audio: true }
          : { audio: true }

      const stream = await navigator.mediaDevices.getUserMedia(constraints)
      setMediaStream(stream)

      const mimeType =
        mode === "video"
          ? MediaRecorder.isTypeSupported("video/mp4")
            ? "video/mp4"
            : "video/webm"
          : MediaRecorder.isTypeSupported("audio/wav")
          ? "audio/wav"
          : "audio/webm"

      const recorder = new MediaRecorder(stream, { mimeType })
      mediaRecorderRef.current = recorder
      chunksRef.current = []

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          chunksRef.current.push(event.data)
        }
      }

      recorder.onstop = async () => {
        const ext = mode === "video" ? "mp4" : "wav"
        const finalBlob = new Blob(chunksRef.current, { type: mimeType })
        await setRecordedBlob(finalBlob, `sample-${discipline}-${Date.now()}.${ext}`)
        stream.getTracks().forEach((track) => track.stop())
        setMediaStream(null)
      }

      recorder.start(500)
      setIsRecording(true)
      setRecordingDurationSeconds(0)

      timerIntervalRef.current = window.setInterval(() => {
        setRecordingDurationSeconds(useDatasetCaptureStore.getState().recordingDurationSeconds + 1)
      }, 1000)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "No se pudo acceder a los dispositivos de captura"
      useDatasetCaptureStore.setState({ error: msg })
    }
  }

  const stopMediaRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop()
    }
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current)
      timerIntervalRef.current = null
    }
    setIsRecording(false)
  }

  const handleManualFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const ext = file.name.split(".").pop()?.toLowerCase()
    if (!ext || !["mp4", "wav", "py"].includes(ext)) {
      useDatasetCaptureStore.setState({
        error: "Formato no permitido. Solo se aceptan archivos .mp4, .wav o .py.",
      })
      return
    }

    if (ext === "py") {
      const text = await file.text()
      setCodeContent(text)
      setRecordingMode("code")
    }

    await setRecordedBlob(file, file.name)
  }

  const handleUploadSubmit = async () => {
    const success = await uploadCurrentCapture()
    if (success) {
      chunksRef.current = []
    }
  }

  const filteredSamples =
    filterDiscipline === "all"
      ? samples
      : samples.filter((s) => s.discipline.toLowerCase() === filterDiscipline.toLowerCase())

  return (
    <div className="space-y-6 p-4 sm:p-6 max-w-7xl mx-auto">
      {/* Encabezado Principal */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/60 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="outline" className="border-emerald-500/40 text-emerald-500 bg-emerald-500/10">
              <ShieldCheck className="w-3.5 h-3.5 mr-1" /> Panel Exclusivo ADMIN
            </Badge>
            <Badge variant="secondary" className="font-mono text-xs">
              RF-IA-18 / HU-17
            </Badge>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
            Ingesta y Captura de Muestras Multimedia
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Herramienta multiplataforma para datasets internos de IA (Música, Fútbol y Programación) con validación de hash SHA-256 y consentimiento explícito.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => fetchSamples(filterDiscipline === "all" ? undefined : filterDiscipline)}
          disabled={isLoading}
          className="self-start md:self-auto"
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
          Refrescar Datasets
        </Button>
      </div>

      {/* Banner de Éxito con mensaje exacto del Backend */}
      {lastUploadMessage && (
        <Alert className="border-emerald-500/50 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 flex items-start justify-between">
          <div className="flex items-start gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-600 mt-0.5" />
            <div>
              <AlertTitle className="font-semibold">Servidor SkillMatch</AlertTitle>
              <AlertDescription className="text-sm">{lastUploadMessage}</AlertDescription>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={clearLastUploadMessage}
            className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
          >
            Cerrar
          </Button>
        </Alert>
      )}

      {/* Banner de Error */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Atención</AlertTitle>
          <AlertDescription className="text-sm">{error}</AlertDescription>
        </Alert>
      )}

      {/* Grid Central Responsive */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Columna Izquierda: Panel de Grabación & Ingesta */}
        <div className="lg:col-span-7 space-y-6">
          <Card className="border-border/60 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg font-semibold flex items-center justify-between">
                <span>1. Captura de Prueba Piloto</span>
                {isRecording && (
                  <Badge variant="destructive" className="animate-pulse flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-white animate-ping" />
                    REC {formatTimer(recordingDurationSeconds)}
                  </Badge>
                )}
              </CardTitle>
              <CardDescription>
                Selecciona la modalidad de captura o importa un archivo multimedia local (.mp4, .wav, .py).
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <Tabs
                value={recordingMode}
                onValueChange={(val) => {
                  resetRecording()
                  setRecordingMode(val as "video" | "audio" | "code")
                }}
              >
                <TabsList className="grid grid-cols-3 w-full">
                  <TabsTrigger value="video" className="flex items-center gap-1.5 text-xs sm:text-sm">
                    <Video className="w-4 h-4 text-emerald-500" />
                    Video (Fútbol)
                  </TabsTrigger>
                  <TabsTrigger value="audio" className="flex items-center gap-1.5 text-xs sm:text-sm">
                    <Mic className="w-4 h-4 text-sky-500" />
                    Audio (Música)
                  </TabsTrigger>
                  <TabsTrigger value="code" className="flex items-center gap-1.5 text-xs sm:text-sm">
                    <Code className="w-4 h-4 text-violet-500" />
                    Código (AST)
                  </TabsTrigger>
                </TabsList>

                {/* Tab Video */}
                <TabsContent value="video" className="space-y-4 pt-3">
                  <div className="relative aspect-video rounded-lg overflow-hidden bg-neutral-950 flex items-center justify-center border border-border">
                    {mediaStream ? (
                      <video
                        ref={videoPreviewRef}
                        autoPlay
                        muted
                        playsInline
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="text-center p-6 text-muted-foreground space-y-2">
                        <Video className="w-12 h-12 mx-auto stroke-1 opacity-50 text-emerald-400" />
                        <p className="text-sm">Cámara inactiva. Pulsa &quot;Iniciar Grabación de Video&quot; para abrir la cámara web o del móvil.</p>
                      </div>
                    )}

                    {isRecording && (
                      <div className="absolute top-3 left-3 bg-red-600/90 text-white font-mono text-xs px-2.5 py-1 rounded-md shadow">
                        REC {formatTimer(recordingDurationSeconds)}
                      </div>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {!isRecording ? (
                      <Button
                        type="button"
                        onClick={() => startMediaRecording("video")}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white"
                      >
                        <Play className="w-4 h-4 mr-1.5 fill-current" />
                        Iniciar Grabación de Video
                      </Button>
                    ) : (
                      <Button type="button" variant="destructive" onClick={stopMediaRecording}>
                        <Square className="w-4 h-4 mr-1.5 fill-current" />
                        Detener y Procesar Muestra
                      </Button>
                    )}
                  </div>
                </TabsContent>

                {/* Tab Audio */}
                <TabsContent value="audio" className="space-y-4 pt-3">
                  <div className="p-8 rounded-lg bg-neutral-950 text-center border border-border space-y-3">
                    <Mic className={`w-14 h-14 mx-auto stroke-1 ${isRecording ? "text-red-500 animate-bounce" : "text-sky-400 opacity-60"}`} />
                    <p className="text-sm text-muted-foreground">
                      {isRecording
                        ? `Grabando espectro de audio... ${formatTimer(recordingDurationSeconds)}`
                        : "Micrófono listo para capturar audio de instrumentos o voz."}
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {!isRecording ? (
                      <Button
                        type="button"
                        onClick={() => startMediaRecording("audio")}
                        className="bg-sky-600 hover:bg-sky-700 text-white"
                      >
                        <Mic className="w-4 h-4 mr-1.5" />
                        Iniciar Grabación de Audio
                      </Button>
                    ) : (
                      <Button type="button" variant="destructive" onClick={stopMediaRecording}>
                        <Square className="w-4 h-4 mr-1.5 fill-current" />
                        Detener y Guardar Audio (.wav)
                      </Button>
                    )}
                  </div>
                </TabsContent>

                {/* Tab Código */}
                <TabsContent value="code" className="space-y-4 pt-3">
                  <div className="space-y-2">
                    <Label htmlFor="code-editor" className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
                      <FileCode className="w-3.5 h-3.5 text-violet-500" />
                      Editor de Código Python (.py) para Dataset AST
                    </Label>
                    <Textarea
                      id="code-editor"
                      rows={8}
                      className="font-mono text-xs bg-neutral-950 text-emerald-400 border-border"
                      value={codeContent}
                      onChange={(e) => {
                        setCodeContent(e.target.value)
                        setRecordedBlob(new Blob([e.target.value], { type: "text/x-python" }), "script.py")
                      }}
                      placeholder="def solution(): ..."
                    />
                  </div>
                </TabsContent>
              </Tabs>

              {/* Subida Alternativa de Archivo */}
              <div className="pt-2 border-t border-border/60">
                <Label htmlFor="file-upload" className="text-xs font-medium text-muted-foreground block mb-1.5">
                  O importa un archivo pregrabado (.mp4, .wav, .py):
                </Label>
                <Input
                  id="file-upload"
                  type="file"
                  accept=".mp4,.wav,.py,video/mp4,audio/wav,text/x-python"
                  onChange={handleManualFileUpload}
                  className="cursor-pointer file:cursor-pointer text-xs"
                />
              </div>

              {/* Vista previa de archivo capturado y Hash SHA-256 */}
              {recordedBlob && (
                <div className="p-3.5 rounded-lg bg-secondary/50 border border-border/80 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <FileCheck className="w-4 h-4 text-emerald-500" />
                      <span className="text-xs font-medium text-foreground truncate max-w-[200px]">
                        {recordedFileName}
                      </span>
                      <Badge variant="outline" className="text-[10px] uppercase">
                        {(recordedBlob.size / 1024).toFixed(1)} KB
                      </Badge>
                    </div>
                    <Button variant="ghost" size="sm" onClick={resetRecording} className="h-7 text-xs text-muted-foreground hover:text-destructive">
                      Descartar
                    </Button>
                  </div>

                  <div className="flex items-center gap-1.5 text-[11px] font-mono text-muted-foreground bg-background/60 p-2 rounded border border-border/40 overflow-x-auto">
                    <Hash className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                    <span className="shrink-0 text-foreground font-semibold">SHA-256:</span>
                    <span className="truncate">{recordedFileHash || "Calculando hash..."}</span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Formulario de Metadatos y Consentimiento */}
          <Card className="border-border/60 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg font-semibold">2. Metadatos & Consentimiento Explícito</CardTitle>
              <CardDescription>
                Registra la procedencia, disciplina, reto y hardware conforme a la gobernanza de IA interna.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="discipline-select" className="text-xs font-medium">Disciplina</Label>
                  <Select value={discipline} onValueChange={setDiscipline}>
                    <SelectTrigger id="discipline-select" className="w-full">
                      <SelectValue placeholder="Selecciona disciplina" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="musica">Música e Instrumentos</SelectItem>
                      <SelectItem value="futbol">Deportes y Fútbol</SelectItem>
                      <SelectItem value="programacion">Programación y Software</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="challenge-input" className="text-xs font-medium">Reto / Desafío</Label>
                  <Input
                    id="challenge-input"
                    value={challenge}
                    onChange={(e) => setChallenge(e.target.value)}
                    placeholder="Ej. Guitarra Acústica - Arpegios"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="hardware-input" className="text-xs font-medium flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5 text-muted-foreground" />
                  Hardware / Periféricos Utilizados
                </Label>
                <Input
                  id="hardware-input"
                  value={hardwareInfo}
                  onChange={(e) => setHardwareInfo(e.target.value)}
                  placeholder="Ej. Logitech C920 Webcam + Micrófono Samson Go"
                />
              </div>

              {discipline === "futbol" && (
                <div className="p-3.5 rounded-lg border border-border/80 bg-secondary/20 space-y-3">
                  <p className="text-xs font-semibold text-foreground">
                    Etiquetado de Muestra de Fútbol (Sección 10 — Sin Fuga por Participante)
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="space-y-1">
                      <Label htmlFor="participant-id-input" className="text-xs">
                        ID Participante
                      </Label>
                      <Input
                        id="participant-id-input"
                        value={participantId}
                        onChange={(e) => setParticipantId(e.target.value)}
                        placeholder="Ej. P-014"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="manual-touch-input" className="text-xs">
                        Conteo Manual de Toques
                      </Label>
                      <Input
                        id="manual-touch-input"
                        type="number"
                        min={0}
                        value={manualTouchCount ?? ""}
                        onChange={(e) =>
                          setManualTouchCount(
                            e.target.value === "" ? null : Number(e.target.value)
                          )
                        }
                        placeholder="Ej. 24"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="level-label-select" className="text-xs">
                        Nivel Provisional
                      </Label>
                      <Select value={levelLabel} onValueChange={setLevelLabel}>
                        <SelectTrigger id="level-label-select">
                          <SelectValue placeholder="Nivel" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Principiante">Principiante</SelectItem>
                          <SelectItem value="Intermedio">Intermedio</SelectItem>
                          <SelectItem value="Avanzado">Avanzado</SelectItem>
                          <SelectItem value="Experto">Experto</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="space-y-1">
                      <Label htmlFor="noise-level-select" className="text-xs">
                        Ruido Ambiental
                      </Label>
                      <Select value={noiseLevel} onValueChange={setNoiseLevel}>
                        <SelectTrigger id="noise-level-select">
                          <SelectValue placeholder="Ruido" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="bajo">Bajo</SelectItem>
                          <SelectItem value="medio">Medio</SelectItem>
                          <SelectItem value="alto">Alto</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="surface-input" className="text-xs">
                        Superficie
                      </Label>
                      <Input
                        id="surface-input"
                        value={surface}
                        onChange={(e) => setSurface(e.target.value)}
                        placeholder="Ej. Césped sintético"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="split-select" className="text-xs">
                        Partición (Split)
                      </Label>
                      <Select value={split} onValueChange={setSplit}>
                        <SelectTrigger id="split-select">
                          <SelectValue placeholder="Split" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="train">Train</SelectItem>
                          <SelectItem value="val">Validation</SelectItem>
                          <SelectItem value="test">Test</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
              )}

              {/* Consentimiento firmado obligatorio */}
              <div className="flex items-start gap-3 p-3.5 rounded-lg border border-emerald-500/30 bg-emerald-500/5">
                <Switch
                  id="consent-switch"
                  checked={signedConsent}
                  onCheckedChange={setSignedConsent}
                  className="mt-0.5"
                />
                <div className="space-y-1">
                  <Label htmlFor="consent-switch" className="text-xs font-semibold cursor-pointer text-foreground">
                    Consentimiento Informado Firmado (Requisito Legal Estricto)
                  </Label>
                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                    Certifico que el sujeto participante firmó explícitamente el consentimiento para capturar audio, video o código y destinarlo exclusivamente al entrenamiento de los modelos de IA de SkillMatch.
                  </p>
                </div>
              </div>

              {/* Botón de Subida */}
              <Button
                type="button"
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2.5"
                disabled={isUploading || !signedConsent || (!recordedBlob && recordingMode !== "code")}
                onClick={handleUploadSubmit}
              >
                {isUploading ? (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    Validando Hash SHA-256 y Almacenando en Servidor...
                  </>
                ) : (
                  <>
                    <UploadCloud className="w-4 h-4 mr-2" />
                    Subir Muestra al Dataset de IA (Multipart)
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Columna Derecha: Catálogo de Muestras Capturadas */}
        <div className="lg:col-span-5 space-y-6">
          <Card className="border-border/60 shadow-sm">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg font-semibold">Muestras Ingestadas</CardTitle>
                  <CardDescription>
                    Total recolectado: {totalCount} {totalCount === 1 ? "muestra" : "muestras"}
                  </CardDescription>
                </div>
                <Select value={filterDiscipline} onValueChange={setFilterDiscipline}>
                  <SelectTrigger className="w-[140px] text-xs">
                    <SelectValue placeholder="Disciplina" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todas</SelectItem>
                    <SelectItem value="musica">Música</SelectItem>
                    <SelectItem value="futbol">Fútbol</SelectItem>
                    <SelectItem value="programacion">Código</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {filteredSamples.length === 0 ? (
                <div className="text-center py-12 px-4 text-muted-foreground space-y-2">
                  <UploadCloud className="w-10 h-10 mx-auto stroke-1 opacity-40 text-muted-foreground" />
                  <p className="text-sm">No hay muestras recolectadas para esta categoría.</p>
                  <p className="text-xs">Las capturas subidas se listarán aquí con su hash y metadatos.</p>
                </div>
              ) : (
                <div className="overflow-x-auto max-h-[640px] overflow-y-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs">Formato & Reto</TableHead>
                        <TableHead className="text-xs">Hash SHA-256</TableHead>
                        <TableHead className="text-xs text-right">Acción</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredSamples.map((sample) => (
                        <TableRow key={sample.id}>
                          <TableCell className="py-3">
                            <div className="space-y-0.5">
                              <div className="flex items-center gap-1.5">
                                <Badge variant="secondary" className="text-[10px] font-mono uppercase">
                                  .{sample.file_format}
                                </Badge>
                                <span className="text-xs font-semibold text-foreground truncate max-w-[130px]">
                                  {sample.challenge}
                                </span>
                              </div>
                              <p className="text-[11px] text-muted-foreground capitalize">
                                {sample.discipline} • {(sample.file_size_bytes / 1024).toFixed(0)} KB
                              </p>
                              <p className="text-[10px] text-muted-foreground truncate max-w-[160px]">
                                {sample.hardware_info}
                              </p>
                            </div>
                          </TableCell>
                          <TableCell className="py-3">
                            <div className="font-mono text-[10px] text-muted-foreground bg-muted/60 p-1.5 rounded max-w-[130px] truncate" title={sample.file_hash_sha256}>
                              {sample.file_hash_sha256.slice(0, 12)}...{sample.file_hash_sha256.slice(-8)}
                            </div>
                          </TableCell>
                          <TableCell className="py-3 text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                              onClick={() => deleteSampleById(sample.id)}
                              title="Eliminar muestra defectuosa"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
