import { useEffect, useState } from "react"
import type { MetricTypeInfo } from "@/types/catalog"
import { skillLabApi } from "../api/skill-lab-api"
import { DEFAULT_METRIC_TYPES } from "../lib/skill-lab-utils"

/** Tipos de medición del motor; si el endpoint falla se usan los dos códigos base. */
export function useMetricTypes(): MetricTypeInfo[] {
  const [metricTypes, setMetricTypes] = useState<MetricTypeInfo[]>(DEFAULT_METRIC_TYPES)

  useEffect(() => {
    let cancelled = false
    skillLabApi
      .getMetricTypes()
      .then((items) => {
        if (!cancelled && Array.isArray(items) && items.length > 0) setMetricTypes(items)
      })
      .catch(() => {
        // Se mantiene el respaldo local.
      })
    return () => {
      cancelled = true
    }
  }, [])

  return metricTypes
}
