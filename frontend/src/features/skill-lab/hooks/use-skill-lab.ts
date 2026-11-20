import { useCallback, useEffect, useRef, useState } from "react"
import { skillLabApi } from "../api/skill-lab-api"
import { requestFailureMessage } from "../lib/skill-lab-utils"
import type { SkillLabConfig, SkillLabSample } from "../types"

interface SkillLabState {
  config: SkillLabConfig | null
  samples: SkillLabSample[]
  isLoading: boolean
  loadError: string | null
}

/** Estado local de la página del laboratorio (no se infla el estado global). */
export function useSkillLab(skillId: string | undefined) {
  const [state, setState] = useState<SkillLabState>({
    config: null,
    samples: [],
    isLoading: true,
    loadError: null,
  })
  const requestIdRef = useRef(0)

  const reload = useCallback(async () => {
    if (!skillId) return
    const requestId = ++requestIdRef.current
    setState((prev) => ({ ...prev, isLoading: prev.config === null, loadError: null }))
    try {
      const [config, samples] = await Promise.all([
        skillLabApi.getConfig(skillId),
        skillLabApi.listSamples(skillId),
      ])
      if (requestId !== requestIdRef.current) return
      setState({ config, samples, isLoading: false, loadError: null })
    } catch (error) {
      if (requestId !== requestIdRef.current) return
      setState((prev) => ({
        ...prev,
        isLoading: false,
        loadError: requestFailureMessage(error),
      }))
    }
  }, [skillId])

  useEffect(() => {
    void reload()
  }, [reload])

  return { ...state, reload }
}
