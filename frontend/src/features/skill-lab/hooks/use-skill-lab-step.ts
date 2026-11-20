import { useCallback, useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import { clampStepNumber, PASO_PARAM } from "../lib/skill-lab-steps"

/**
 * Paso actual del asistente guardado en `?paso=` (1-based, S8). Un valor inválido se corrige con `replace`;
 * navegar entre pasos agrega una entrada al historial para que "Atrás" del navegador vuelva al paso anterior.
 */
export function useSkillLabStep(total: number) {
  const [searchParams, setSearchParams] = useSearchParams()
  const raw = searchParams.get(PASO_PARAM)
  const current = clampStepNumber(raw, total)

  const writeStep = useCallback(
    (step: number, replace: boolean) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.set(PASO_PARAM, String(step))
          return next
        },
        { replace }
      )
    },
    [setSearchParams]
  )

  useEffect(() => {
    if (raw !== String(current)) writeStep(current, true)
  }, [raw, current, writeStep])

  const goTo = useCallback(
    (step: number) => {
      const target = clampStepNumber(String(step), total)
      if (target !== current) writeStep(target, false)
    },
    [current, total, writeStep]
  )

  return { current, goTo }
}
