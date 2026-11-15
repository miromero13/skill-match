import type { ReactNode } from "react"
import { ExternalLink, Link2 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  evidenceTypes,
  safeEvidenceUrl,
  type SkillEvidence,
} from "@/types/skill-evidence"

export function EvidenceLinks({
  items,
  actions,
}: {
  items: SkillEvidence[]
  actions?: (item: SkillEvidence) => ReactNode
}) {
  return (
    <ul className="space-y-3" aria-label="Evidencias externas">
      {items.map((item) => {
        const href = safeEvidenceUrl(item.url)
        return (
          <li
            key={item.id}
            className="min-w-0 rounded-xl border bg-card p-4 shadow-xs"
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <h3 className="min-w-0 flex-1 font-semibold [overflow-wrap:anywhere] break-words">
                {item.title}
              </h3>
              <Badge variant="secondary">
                {evidenceTypes.find((type) => type.value === item.evidence_type)
                  ?.label ?? "Otro"}
              </Badge>
            </div>
            {item.description && (
              <p className="mt-2 text-sm [overflow-wrap:anywhere] break-words whitespace-pre-wrap text-muted-foreground">
                {item.description}
              </p>
            )}
            <p className="mt-3 flex items-start gap-2 text-xs text-muted-foreground">
              <Link2 className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              <span className="min-w-0 break-all">{item.url}</span>
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {href ? (
                <Button asChild variant="outline" size="sm">
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={`Abrir ${item.title} en otra pestaña`}
                  >
                    Abrir enlace{" "}
                    <ExternalLink className="size-3.5" aria-hidden="true" />
                  </a>
                </Button>
              ) : (
                <span className="text-sm text-muted-foreground">
                  Enlace no disponible
                </span>
              )}
              {actions?.(item)}
            </div>
          </li>
        )
      })}
    </ul>
  )
}
