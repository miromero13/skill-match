import { useEffect, useState } from "react"
import { useStore } from "zustand"
import { createStore } from "zustand/vanilla"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { ApiError } from "@/types/api"
import {
  decideProposal, dismissMatch, readMessages, readProposal, sendMessage, sendProposal,
  type MatchMessage, type MatchProposal,
} from "@/services/match-proposal-service"

export function MatchNegotiation({ id, onChange }: { id: string; onChange: (hide: boolean) => void }) {
  const [store] = useState(() => createStore<{ proposal: MatchProposal | null }>()(() => ({ proposal: null })))
  const proposal = useStore(store, (state) => state.proposal)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [retry, setRetry] = useState(0)
  const [counter, setCounter] = useState(false)
  const [date, setDate] = useState("")

  useEffect(() => {
    const controller = new AbortController()
    void readProposal(id, controller.signal).then((response) => {
      if (!controller.signal.aborted) store.setState({ proposal: response.data })
    }).catch((err: unknown) => {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "No se pudo cargar la propuesta.")
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false)
    })
    return () => controller.abort()
  }, [id, retry, store])

  async function submit(action: "propose" | "accept" | "decline" | "dismiss") {
    setBusy(true)
    setError("")
    try {
      if (action === "dismiss") {
        await dismissMatch(id)
        onChange(true)
        return
      }
      if (action !== "propose" && !proposal) return
      const response = action === "propose"
        ? await sendProposal(id, new Date(date).toISOString(), proposal?.id)
        : await decideProposal(id, action, proposal!.id)
      store.setState({ proposal: response.data })
      setCounter(false)
      onChange(action === "decline")
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo completar la acción.")
      if (err instanceof ApiError && err.statuscode === 409) {
        setCounter(false)
        setLoading(true)
        setRetry((value) => value + 1)
      }
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <p role="status">Cargando propuesta…</p>

  return (
    <div className="space-y-4 border-t pt-4">
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {error && !proposal ? (
        <Button variant="outline" onClick={() => { setError(""); setLoading(true); setRetry((value) => value + 1) }}>
          Reintentar
        </Button>
      ) : null}

      {proposal && (
        <div>
          <p className="font-medium">{proposal.status === "accepted" ? "Intercambio aceptado" : proposal.status === "declined" ? "Propuesta rechazada" : "Revisar propuesta"}</p>
          <p className="text-sm">{new Date(proposal.starts_at).toLocaleString()}</p>
          {proposal.status === "pending" && proposal.proposed_by_you && (
            <p className="text-sm text-muted-foreground">Esperando la respuesta de la otra persona.</p>
          )}
        </div>
      )}

      {(!proposal && !error || counter) && (
        <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); void submit("propose") }}>
          <Label htmlFor="match-slot">{counter ? "Nuevo horario" : "Horario para el intercambio"}</Label>
          <Input id="match-slot" type="datetime-local" required value={date}
                 onChange={(event) => setDate(event.target.value)} disabled={busy} />
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={busy}>{counter ? "Enviar contraoferta" : "Proponer intercambio"}</Button>
            {counter
              ? <Button type="button" variant="outline" disabled={busy} onClick={() => setCounter(false)}>Cancelar</Button>
              : <Button type="button" variant="outline" disabled={busy} onClick={() => void submit("dismiss")}>Descartar</Button>}
          </div>
        </form>
      )}

      {proposal?.status === "pending" && !proposal.proposed_by_you && !counter && (
        <div className="flex flex-wrap gap-2">
          <Button disabled={busy} onClick={() => void submit("accept")}>Aceptar</Button>
          <Button variant="outline" disabled={busy} onClick={() => { setDate(""); setCounter(true) }}>Contraproponer</Button>
          <Button variant="destructive" disabled={busy} onClick={() => void submit("decline")}>Rechazar</Button>
        </div>
      )}

      {proposal?.contact_enabled && <MatchConversation id={id} />}
    </div>
  )
}

function MatchConversation({ id }: { id: string }) {
  const [messages, setMessages] = useState<MatchMessage[]>([])
  const [body, setBody] = useState("")
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [refresh, setRefresh] = useState(0)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    const controller = new AbortController()
    void readMessages(id, page, controller.signal).then((response) => {
      if (!controller.signal.aborted) {
        setMessages([...response.data].reverse())
        setTotal(response.count ?? 0)
        setError("")
      }
    }).catch((err: unknown) => {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "No se pudieron cargar los mensajes.")
    })
    return () => controller.abort()
  }, [id, page, refresh])

  async function send() {
    setSending(true)
    try {
      await sendMessage(id, body)
      setBody("")
      setPage(1)
      setRefresh((value) => value + 1)
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo enviar el mensaje.")
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-medium">Mensajes del intercambio</h3>
        <Button variant="outline" size="sm" onClick={() => setRefresh((value) => value + 1)}>Actualizar</Button>
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <ul className="max-h-48 space-y-2 overflow-y-auto" aria-label="Mensajes">
        {messages.map((message) => (
          <li key={message.id} className="break-words rounded-md border p-2 text-sm">
            <strong>{message.sent_by_you ? "Tú" : "Otra persona"}</strong>
            <p className="whitespace-pre-wrap">{message.body}</p>
          </li>
        ))}
      </ul>
      {total > 30 && (
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={page * 30 >= total} onClick={() => setPage(page + 1)}>Más antiguos</Button>
          <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>Más recientes</Button>
        </div>
      )}
      <form className="space-y-2" onSubmit={(event) => { event.preventDefault(); void send() }}>
        <Label htmlFor="match-message">Mensaje</Label>
        <Textarea id="match-message" value={body} onChange={(event) => setBody(event.target.value)} maxLength={2000} />
        <Button type="submit" disabled={sending || !body.trim()}>Enviar mensaje</Button>
      </form>
    </div>
  )
}
