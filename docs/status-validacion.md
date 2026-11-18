# Estado de las tareas de validación

**Hay implementación comprobada, pero todavía no hay un examen completo ejecutable.** Las casillas `[x]` de `USER_STORIES.md` identifican criterios concretos ya implementados; no significan que toda la historia esté terminada ni que haya sido aprobada para producción.

Este documento es seguimiento local. **Jira no fue actualizado:** esta sesión no tiene conector, CLI ni configuración de acceso disponible. No se inventaron transiciones o números de comentarios. La asignación cubre las diez historias del bloque acordado, no una consulta actual del total de asignaciones del tablero.

## Lo implementado

| Jira | Entrega comprobada | Lo que impide cerrar toda la historia |
|---|---|---|
| SM-23 | Preflight/consentimiento, pertenencia, enrolamiento, cupos, stepper, Zustand y mensajes del servidor | Inicio real de SM-39, revisión independiente y validación integral/responsive. El botón actual es `Registrar consentimiento`; el enlace al perfil usa `/app/profile`, no `/profile` literal del backlog |
| SM-43 | Controles reales de navegador y bitácora en ensayo con TTL24h, permiso exclusivo20s, cola y reenvíos idempotentes | Asociar controles/incidentes al examen real, endpoints y store del examen, vistas de advertencia/expulsión y política de sanciones acordada. La prueba favorable del usuario no sustituye revisión independiente |
| SM-44 | Cámara/audio reales, iluminación/encuadre, reto guiado, cotejo SFace y comprobaciones audiovisuales locales | Prueba física de eficacia, revisión independiente y alinear los criterios:45s de vigencia/11s de movimiento acordados frente a3–5s originales; sin flujo óptico completo ni garantía PAD |

**Criterios marcados ahora:**6 de SM-23,1 de SM-43 y5 de SM-44. No se cambiaron a `[x]` los criterios todavía parciales, el diseño responsive no demostrado ni los de las historias pendientes.

## Lo pendiente

| Jira | Trabajo pendiente |
|---|---|
| SM-49 | Supervisión continua audiovisual. Especificación preparada en `odd/tasks/continuous-supervision.md`; todavía sin implementación nueva |
| SM-39 | Inicio atómico/idempotente, consumo único al fijar `started_at`, banco de preguntas, tiempos/respuestas/calificación |
| SM-40 | Editor, sandbox aislado y ejecución real con tests privados/límites |
| SM-41 | AST, complejidad y calidad; similitud estructural necesita alcance explícito |
| SM-42 | Defensa, preguntas vinculadas a la entrega, respuestas y rúbrica |
| SM-45 | Consolidación, feedback y otorgamiento idempotente del sello |
| SM-46 | Consola administrativa, dictámenes y apelaciones |

SM-47/48 (prácticas de guitarra/deportes) pertenecen a otros responsables. Integrarlas al flujo no implica implementar sus evaluadores.

## Evidencia y commits existentes

- SM-23/backend y calibración inicial: `3f33c1e`.
- Adaptación del preembarque: `fb91c57`.
- Modelos locales y avisos: `a7052fd`; voz/hablantes: `67a7536`; evidencia audiovisual: `1061128`; captura: `9417ee5`; panel/guía: `da5dc06`.
- SM-43: `596f944` (backend), `d668587` (monitor/cola), `f01be87` (vista), `efdfc78` (guía).
- Última regresión backend observada:679 correctas/1 omitida por Garage S3/1 aviso Starlette-httpx, base descartable eliminada. En esta actualización de estado no se cambió ni se volvió a ejecutar el backend.
- Comprobación actual del frontend, job28:197 correctas/1 fallo en `evidence-navigation.test.tsx:149`, mismo caso de catálogo previamente observado; tests exit1. TypeScript/Vite build exit0; advertencia de chunk>500kB persiste. No se reparó ese caso fuera de alcance.

## Cambios de interfaz guardados por pedido del usuario

El pedido «Hace commits de lo que hay» incluye los cambios existentes de navegación, scroll, perfil y tarjeta de identidad. Se guardan sin atribuir su autoría a esta implementación ni certificarlos como historias terminadas.

**Advertencia de identidad:** el frontend actual envía `CI-AUTO` cuando no existe número de documento y agrega una fotografía posterior opcional al contrato TypeScript. Las pruebas de interfaz no acreditan extracción automática del número/nombre, uso de esa fotografía por el backend ni verificación documental integral. Ese bloque se conserva como trabajo pendiente, no como identidad completa/aprobada.

No hubo push, migración de la base de aplicación, seed ni modificación de registros durante esta actualización. Los cambios de documentación no necesitan RED conductual: se verifican contra código/pruebas y mediante comprobaciones estructurales del Markdown.

## Próximo paso

Implementar SM-49 en el ensayo autorizado, después SM-39 e integrar los controles al examen. Para sincronizar Jira hace falta acceso mediante una integración autorizada; mientras tanto solo se completan casillas locales comprobadas, sin cerrar historias incompletas.
