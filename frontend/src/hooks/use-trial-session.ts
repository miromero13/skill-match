import { useCallback, useEffect, useRef, useState, type RefObject } from "react"
import type { Emit } from "@/hooks/use-av-supervision"
import {
  BrowserMonitor,
  IncidentQueue,
  readBrowserLedger,
  readBrowserTrial,
  sendBrowserIncidents,
  startBrowserTrial,
  trialAction,
  type LedgerIncident,
  type Trial,
} from "@/services/browser-supervision"
import type { GazeZone } from "@/services/gaze-tracking"

/** What the capture needs from a confirmed lease. */
export interface SessionHandle {
  trialId: string
  tabId: string
  emit: Emit
  /** Zone of the trial when it was claimed (null until calibrated); omitted when the capture resumes. */
  gazeZone?: GazeZone | null
}

export interface TrialSessionOptions {
  owner: string | undefined
  areaRef: RefObject<HTMLElement | null>
  /** The lease is confirmed and the first incidents are acknowledged: start capturing. */
  onReady: (session: SessionHandle) => void
  /** The lease (or the incident confirmation) was lost: release the camera and the microphone. */
  onSuspend: () => void
  /** The lease was confirmed again after a suspension: capture may start again. */
  onResume: (session: SessionHandle) => void
  /** The session is over (restart, close or unmount): release everything. */
  onEnd: () => void
}

interface Runtime {
  id: string
  tabId: string
  queue: IncidentQueue
  monitor: BrowserMonitor
  timer: ReturnType<typeof setInterval> | null
  closing: boolean
  release: () => void
}

const LEASE_MS = 15_000
const RENEW_MS = 5_000
const message = (error: unknown) => (error instanceof Error ? error.message : "No se pudo completar la operación.")

/** Lease, heartbeat, browser monitor, incident queue and ledger of one supervised trial. */
export function useTrialSession(options: TrialSessionOptions) {
  const { owner, areaRef } = options
  const latest = useRef(options)
  const generation = useRef(0)
  const runtime = useRef<Runtime | null>(null)
  const tab = useRef("")
  const [trial, setTrial] = useState<Trial | null>(null)
  const [active, setActive] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [pending, setPending] = useState(0)
  const [rows, setRows] = useState<LedgerIncident[]>([])
  const [total, setTotal] = useState(0)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    latest.current = options
  })
  const invalidate = useCallback(() => ++generation.current, [])

  const loadLedger = useCallback(async (id: string, more = false, after = 0) => {
    const version = generation.current
    const response = await readBrowserLedger(id, more ? after : 0)
    if (version !== generation.current) return
    setRows((previous) => (more ? [...previous, ...response.data] : response.data))
    setTotal(response.count ?? 0)
  }, [])

  /** Tears the current lease down; the capture is released first so nothing outlives the session. */
  const stop = useCallback(() => {
    latest.current.onEnd()
    const current = runtime.current
    runtime.current = null
    setOpen(false)
    if (current) {
      current.monitor.stop()
      if (current.timer) clearInterval(current.timer)
      current.release()
    }
  }, [])

  useEffect(() => {
    const version = invalidate()
    void Promise.resolve()
      .then(() => {
        try {
          return localStorage.getItem(`sm43:last:${owner}`)
        } catch {
          throw new Error("El almacenamiento local no está disponible; no se puede garantizar recuperación.")
        }
      })
      .then(async (id) => {
        if (!id || !/^[0-9a-f-]{36}$/i.test(id)) return
        const saved = await readBrowserTrial(id)
        if (version !== generation.current) return
        setTrial(saved)
        await loadLedger(saved.id)
      })
      .catch((cause) => {
        if (version === generation.current) setError(message(cause))
      })
    return () => {
      invalidate()
      stop()
    }
  }, [owner, invalidate, loadLedger, stop])

  /** Claims the lease, starts the browser monitor and the heartbeat, and hands over to the capture once confirmed. */
  const start = useCallback(async () => {
    const area = areaRef.current
    if (!owner || !area) return
    stop()
    setActive(false)
    setBusy(true)
    setError("")
    const version = invalidate()
    const tabId = crypto.randomUUID()
    tab.current = tabId
    let claimed: string | null = null
    const requestedAt = performance.now()
    try {
      const result = await startBrowserTrial(tabId)
      claimed = result.trial.id
      const trialId = claimed
      if (version !== generation.current) {
        void trialAction(trialId, tabId, "release", true).catch(() => undefined)
        return
      }
      if (performance.now() - requestedAt >= LEASE_MS)
        throw new Error("La activación llegó tarde. Reactivá la prueba para confirmar autorización.")
      const lastKey = `sm43:last:${owner}`
      const resumed = localStorage.getItem(lastKey) === trialId
      localStorage.setItem(lastKey, trialId)
      setTrial(result.trial)
      setNotice(result.message)
      let fatal = false
      let suspended = false
      let deadline = requestedAt + LEASE_MS
      const isCurrent = () => runtime.current?.tabId === tabId && !runtime.current.closing
      // Lease or incident confirmation lost: lock the area and release the capture until the lease is back.
      const pause = (text: string) => {
        if (version !== generation.current) return
        setError(text)
        setActive(false)
        if (!suspended) {
          suspended = true
          latest.current.onSuspend()
        }
      }
      const queue = new IncidentQueue(
        `sm43:queue:${owner}:${trialId}`,
        async (events) => {
          const response = await sendBrowserIncidents(trialId, tabId, events)
          if (!isCurrent() || performance.now() >= deadline)
            throw new Error("Confirmación tardía: los incidentes se conservan para reintentar.")
          return response
        },
        (text) => {
          fatal = true
          pause(text)
        },
      )
      const emit: Emit = (event) => {
        if (!isCurrent()) return
        queue.add(event)
        setPending(queue.size)
        void queue
          .flush()
          .then(() => {
            if (isCurrent()) setPending(queue.size)
          })
          .catch((cause) => pause(message(cause)))
      }
      const monitor = new BrowserMonitor(area, emit, setNotice)
      const handle: SessionHandle = { trialId, tabId, emit, gazeZone: result.trial.gaze_zone ?? null }
      const current: Runtime = {
        id: trialId,
        tabId,
        queue,
        monitor,
        timer: null,
        closing: false,
        release: () => {
          void trialAction(trialId, tabId, "release", true).catch(() => undefined)
        },
      }
      runtime.current = current
      setOpen(true)
      let nextRenew = performance.now() + RENEW_MS
      let renewing = false
      const renew = async () => {
        if (renewing || !isCurrent()) return
        renewing = true
        const sentAt = performance.now()
        try {
          await trialAction(trialId, tabId, "heartbeat")
          if (!isCurrent()) return
          deadline = sentAt + LEASE_MS
          if (performance.now() >= deadline) throw new Error("La renovación llegó tarde. Reactivá la prueba.")
          await queue.flush()
          if (isCurrent()) {
            setPending(queue.size)
            monitor.start()
            setActive(!fatal)
            if (suspended && !fatal) {
              suspended = false
              latest.current.onResume({ trialId, tabId, emit })
            }
          }
        } catch (cause) {
          if (isCurrent()) {
            monitor.stop()
            pause(message(cause))
          }
        } finally {
          renewing = false
        }
      }
      current.timer = setInterval(() => {
        if (performance.now() >= deadline) {
          monitor.stop()
          pause("Autorización de pestaña sin confirmar. Reactivá la prueba para continuar.")
        }
        if (performance.now() >= nextRenew) {
          nextRenew = performance.now() + RENEW_MS
          void renew()
        }
      }, 1000)
      monitor.start()
      queue.add({ kind: resumed ? "SESSION_RESUME" : "SESSION_OPEN" })
      setPending(queue.size)
      await queue.flush()
      if (isCurrent() && version === generation.current) {
        setPending(queue.size)
        setActive(!fatal)
        await loadLedger(trialId)
        if (isCurrent() && version === generation.current && !suspended) latest.current.onReady(handle)
      }
    } catch (cause) {
      if (version === generation.current) {
        setError(message(cause))
        setActive(false)
        if (!runtime.current && claimed) void trialAction(claimed, tabId, "release", true).catch(() => undefined)
      }
    } finally {
      if (version === generation.current) setBusy(false)
    }
  }, [owner, areaRef, stop, invalidate, loadLedger])

  const close = useCallback(async () => {
    latest.current.onEnd()
    const current = runtime.current
    if (!current) return
    setBusy(true)
    setActive(false)
    setError("")
    current.closing = true
    current.monitor.stop()
    if (current.timer) clearInterval(current.timer)
    try {
      await current.queue.flush()
      const result = await trialAction(current.id, tab.current, "close")
      if (runtime.current !== current) return
      runtime.current = null
      setOpen(false)
      setTrial(result.trial)
      setPending(0)
      setNotice(result.message)
      await loadLedger(current.id)
    } catch (cause) {
      setError(message(cause))
    } finally {
      setBusy(false)
    }
  }, [loadLedger])

  const refreshLedger = useCallback(() => (trial ? loadLedger(trial.id) : Promise.resolve()), [trial, loadLedger])
  const loadMore = useCallback(
    () => (trial ? loadLedger(trial.id, true, rows.at(-1)?.sequence ?? 0) : Promise.resolve()),
    [trial, rows, loadLedger],
  )
  const tabId = useCallback(() => tab.current, [])

  return {
    trial, setTrial, active, busy, error, setError, notice, setNotice, pending, rows, total, open,
    start, close, refreshLedger, loadMore, tabId,
  }
}
