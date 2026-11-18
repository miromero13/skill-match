import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useAuthStore } from "@/stores/auth-store"
import { BrowserMonitor, IncidentQueue, readBrowserLedger, readBrowserTrial, sendBrowserIncidents,
  startBrowserTrial, trialAction, type LedgerIncident, type Trial } from "@/services/browser-supervision"

interface Runtime {
  id: string
  queue: IncidentQueue
  monitor: BrowserMonitor
  timer: ReturnType<typeof setInterval> | null
  closing: boolean
  release: () => void
}
const labels: Record<string, string> = { AWAY: "Salida / pérdida de foco", RETURN: "Regreso", COPY: "Copiar", CUT: "Cortar", PASTE: "Pegar",
  DROP: "Arrastrar / soltar", CONTEXT_MENU: "Menú contextual", FULLSCREEN_EXIT: "Salida de pantalla completa", OFFLINE: "Sin conexión",
  ONLINE: "Conexión recuperada", PAGE_EXIT: "Salida de página", SESSION_OPEN: "Inicio de prueba", SESSION_RESUME: "Reanudación" }
const message = (error: unknown) => error instanceof Error ? error.message : "No se pudo completar la operación."

export function BrowserSupervisionPage() {
  const owner = useAuthStore(state => state.user?.id)
  const area = useRef<HTMLDivElement>(null)
  const runtime = useRef<Runtime | null>(null)
  const generation = useRef(0)
  const tab = useRef(crypto.randomUUID())
  const [trial, setTrial] = useState<Trial | null>(null)
  const [accepted, setAccepted] = useState(false)
  const [active, setActive] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [pending, setPending] = useState(0)
  const [rows, setRows] = useState<LedgerIncident[]>([])
  const [total, setTotal] = useState(0)
  const lastKey = `sm43:last:${owner}`

  function stop() {
    const current = runtime.current
    runtime.current = null
    if (current) { current.monitor.stop(); if (current.timer) clearInterval(current.timer); current.release() }
  }
  async function ledger(id: string, more = false) {
    const version = generation.current
    const response = await readBrowserLedger(id, more ? (rows.at(-1)?.sequence ?? 0) : 0)
    if (version !== generation.current) return
    setRows(previous => more ? [...previous, ...response.data] : response.data)
    setTotal(response.count ?? 0)
  }
  useEffect(() => {
    const version = ++generation.current
    setTrial(null); setRows([]); setTotal(0); setActive(false)
    try {
      const id = localStorage.getItem(`sm43:last:${owner}`)
      if (id && /^[0-9a-f-]{36}$/i.test(id)) void readBrowserTrial(id).then(async saved => {
        if (version !== generation.current) return
        setTrial(saved)
        await ledger(saved.id)
      }).catch(cause => { if (version === generation.current) setError(message(cause)) })
    } catch { setError("El almacenamiento local no está disponible; no se puede garantizar recuperación.") }
    return () => { generation.current++; stop() }
    // Only ownership changes replace this component's trial lifecycle.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [owner])

  async function start() {
    if (!owner || !area.current) return
    stop(); setActive(false); setBusy(true); setError("")
    const version = ++generation.current
    const tabId = crypto.randomUUID()
    tab.current = tabId
    let claimed: string | null = null
    const requestedAt = performance.now()
    try {
      const result = await startBrowserTrial(tabId)
      claimed = result.trial.id
      if (version !== generation.current) { void trialAction(claimed, tabId, "release", true).catch(() => undefined); return }
      if (performance.now() - requestedAt >= 15000) throw new Error("La activación llegó tarde. Reactivá la prueba para confirmar autorización.")
      const resumed = localStorage.getItem(lastKey) === claimed
      localStorage.setItem(lastKey, claimed)
      setTrial(result.trial); setNotice(result.message)
      const pause = (text: string) => { if (version === generation.current) { setError(text); setActive(false) } }
      let fatal = false
      let deadline = requestedAt + 15000
      let current: Runtime
      const queue = new IncidentQueue(`sm43:queue:${owner}:${claimed}`,
        async events => {
          const response = await sendBrowserIncidents(result.trial.id, tabId, events)
          if (runtime.current !== current || performance.now() >= deadline)
            throw new Error("Confirmación tardía: los incidentes se conservan para reintentar.")
          return response
        }, text => { fatal = true; pause(text) })
      const emit = (event: Parameters<IncidentQueue["add"]>[0]) => {
        if (runtime.current !== current || current.closing) return
        queue.add(event); setPending(queue.size)
        void queue.flush().then(() => { if (runtime.current === current) setPending(queue.size) }).catch(cause => pause(message(cause)))
      }
      const monitor = new BrowserMonitor(area.current, emit, setNotice)
      current = { id: claimed, queue, monitor, timer: null, closing: false,
        release: () => { void trialAction(result.trial.id, tabId, "release", true).catch(() => undefined) } }
      runtime.current = current
      let nextRenew = performance.now() + 5000
      let renewing = false
      const renew = async () => {
        if (renewing || runtime.current !== current || current.closing) return
        renewing = true
        const sentAt = performance.now()
        try {
          await trialAction(current.id, tabId, "heartbeat")
          if (runtime.current !== current || current.closing) return
          deadline = sentAt + 15000
          if (performance.now() >= deadline) throw new Error("La renovación llegó tarde. Reactivá la prueba.")
          await queue.flush()
          if (runtime.current === current && !current.closing) { setPending(queue.size); monitor.start(); setActive(!fatal) }
        } catch (cause) { if (runtime.current === current && !current.closing) { monitor.stop(); pause(message(cause)) } }
        finally { renewing = false }
      }
      current.timer = setInterval(() => {
        if (performance.now() >= deadline) { monitor.stop(); setActive(false); setError("Autorización de pestaña sin confirmar. Reactivá la prueba para continuar.") }
        if (performance.now() >= nextRenew) { nextRenew = performance.now() + 5000; void renew() }
      }, 1000)
      monitor.start()
      queue.add({ kind: resumed ? "SESSION_RESUME" : "SESSION_OPEN" })
      setPending(queue.size)
      await queue.flush()
      if (runtime.current === current) { setPending(queue.size); setActive(!fatal); await ledger(current.id) }
    } catch (cause) {
      if (version === generation.current) {
        setError(message(cause)); setActive(false)
        if (!runtime.current && claimed) void trialAction(claimed, tabId, "release", true).catch(() => undefined)
      }
    } finally { if (version === generation.current) setBusy(false) }
  }
  async function close() {
    const current = runtime.current
    if (!current) return
    setBusy(true); setActive(false); setError("")
    current.closing = true
    current.monitor.stop()
    if (current.timer) clearInterval(current.timer)
    try {
      await current.queue.flush()
      const result = await trialAction(current.id, tab.current, "close")
      if (runtime.current !== current) return
      current.monitor.stop(); if (current.timer) clearInterval(current.timer)
      runtime.current = null
      setTrial(result.trial); setPending(0); setNotice(result.message)
      await ledger(current.id)
    } catch (cause) { setError(message(cause)) }
    finally { setBusy(false) }
  }
  async function fullscreen() {
    try {
      if (!area.current?.requestFullscreen) throw new Error("Este navegador no permite pantalla completa. La prueba puede continuar sin ese modo.")
      await area.current.requestFullscreen()
    } catch (cause) { setError(message(cause)) }
  }

  return <section className="mx-auto w-full max-w-4xl space-y-5 p-4 sm:p-6">
    <h1 className="text-2xl font-semibold">Prueba de supervisión del navegador</h1>
    <p className="text-sm text-muted-foreground">SM-43 · Sesión de prueba, controles reales. No inicia un examen, no consume intentos ni genera sanciones. Sin cámara ni micrófono.</p>
    <Card><CardContent className="space-y-4 p-5">
      <h2 className="font-semibold">Normas de esta prueba</h2>
      <p className="text-sm">Se registran salidas y regresos, duración, portapapeles, arrastrar/soltar, menú contextual, conectividad y salida de pantalla completa. No se guarda lo escrito ni el contenido del portapapeles.</p>
      <p className="text-sm text-muted-foreground">Una pestaña activa por prueba; si recargás o cerrás abruptamente, puede ser necesario esperar hasta 20 segundos para reactivar. Pantalla completa es opcional. Los controles solo bloquean acciones dentro del área supervisada.</p>
      <div className="flex items-start gap-3"><Checkbox id="browser-trial-consent" checked={accepted} disabled={busy || active} onCheckedChange={value => setAccepted(value === true)} />
        <Label htmlFor="browser-trial-consent">Acepto los controles y el registro de incidentes de esta sesión de prueba.</Label></div>
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => void start()} disabled={!accepted || busy || active}>{busy ? "Procesando…" : "Activar prueba"}</Button>
        <Button variant="outline" onClick={() => void close()} disabled={!runtime.current || busy}>Cerrar prueba</Button>
        <Button variant="outline" onClick={() => void fullscreen()} disabled={!active}>Pantalla completa opcional</Button>
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {notice && <p role="status" className="text-sm">{notice}</p>}
      <p className="text-xs text-muted-foreground">Estado: {active ? "supervisión activa" : "área deshabilitada"} · Pendientes de confirmación: {pending}</p>
    </CardContent></Card>
    <div ref={area} className="space-y-3 rounded-xl border bg-card p-5">
      <Label htmlFor="supervised-area">Área supervisada</Label>
      <Textarea id="supervised-area" aria-label="Área supervisada" disabled={!active} placeholder="Escribí una frase, seleccioná texto e intentá copiar, cortar, pegar o arrastrar contenido aquí." className="min-h-36" />
      <p className="text-xs text-muted-foreground">El texto es local y no se envía al backend. Fuera de esta área el portapapeles funciona normalmente.</p>
    </div>
    <Card><CardContent className="space-y-3 p-5">
      <h2 className="font-semibold">Bitácora de prueba · {total} incidentes confirmados</h2>
      {trial && <p className="break-all text-xs text-muted-foreground">Sesión: {trial.id} · {trial.closed_at ? "cerrada" : "abierta"}</p>}
      <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={!trial} onClick={() => { if (trial) void ledger(trial.id).catch(cause => setError(message(cause))) }}>Actualizar bitácora</Button>
        {rows.length < total && <Button variant="outline" onClick={() => { if (trial) void ledger(trial.id, true).catch(cause => setError(message(cause))) }}>Cargar más incidentes</Button>}</div>
      <ol className="max-h-96 space-y-2 overflow-y-auto text-sm" aria-label="Incidentes confirmados">{rows.map(row => <li key={row.event_id} className="rounded-lg border p-3">
        <strong>{row.sequence}. {labels[row.kind]}</strong> · {row.duration_ms} ms
        <p className="text-xs text-muted-foreground">Reportado: {new Date(row.observed_at).toLocaleString()} · Recibido: {new Date(row.received_at).toLocaleString()}</p>
      </li>)}</ol>
      {!rows.length && <p className="text-sm text-muted-foreground">Sin incidentes confirmados para mostrar.</p>}
    </CardContent></Card>
    <Button variant="outline" asChild><Link to="/app/teaching-skills">Salir de la prueba</Link></Button>
  </section>
}
