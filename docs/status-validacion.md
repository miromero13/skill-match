# Estado de las tareas de validación

SM-23, SM-43 y SM-44 están **Listo**, por aceptación explícita del usuario. El estado se actualizó mediante el MCP de Jira configurado en `.pi/mcp.json` y se volvió a consultar después de cada transición.

## Estado sincronizado con Jira

| Historia/tarea | Estado | Alcance |
|---|---|---|
| [SM-23](https://sauterdevs.atlassian.net/browse/SM-23) | **Listo** | Preembarque, instrucciones, requisitos, consentimiento y habilitación de calibración |
| [SM-43](https://sauterdevs.atlassian.net/browse/SM-43) | **Listo** | Supervisión de navegador, cola y bitácora funcionales en la página de ensayo |
| [SM-44](https://sauterdevs.atlassian.net/browse/SM-44) | **Listo** | Calibración secuencial local de cámara/audio, movimiento, identidad y comprobaciones audiovisuales |
| [SM-57](https://sauterdevs.atlassian.net/browse/SM-57) | **Por hacer** | Conectar supervisión de navegador y audiovisual al examen real; [especificación](supervision-exam-integration.md) |
| [SM-49](https://sauterdevs.atlassian.net/browse/SM-49) | **Por hacer** | Implementación de supervisión audiovisual continua; la conexión posterior al examen corresponde a SM-57 |

Se actualizaron las descripciones de SM-43 y SM-44 al alcance entregado. SM-49 conserva su descripción original con una referencia añadida a SM-57. La integración pendiente no reabre las tres historias aceptadas.

## Alcance acordado de SM-44

- Vigencia del reto:45s; movimiento guiado:11s, seguido de3s de silencio ambiente y8s de voz/pausa.
- YuNet/SFace y cotejo1:1 con umbral coseno0.363; posiciones faciales, no flujo óptico completo.
- VAD, modelos locales para varios hablantes/superposición y heurística temporal de boca/audio.
- Comprobaciones pasivas y de etiquetas de cámara como controles experimentales, no garantías PAD, de lectura de labios ni de autenticidad física del dispositivo.

## Evidencia existente

- SM-23: `3f33c1e`, `fb91c57`.
- SM-44: `a7052fd`, `9417ee5`, `da5dc06`, `67a7536`, `1061128` y calibración inicial en `3f33c1e`.
- SM-43: `596f944`, `d668587`, `f01be87`, `efdfc78`.
- Última regresión backend observada:679 correctas/1 omitida por Garage S3/1 aviso Starlette-httpx; base descartable eliminada.
- Última comprobación frontend, job28:197 correctas/1 fallo previo de catálogo en `evidence-navigation.test.tsx:149`; tests exit1, TypeScript/Vite build exit0. Persiste advertencia de chunk>500kB.
- Estas evidencias no se presentan como revisión independiente ni como certificación de eficacia física. No se ejecutaron pruebas adicionales para esta actualización de estados/documentación.

## Commits del pedido de guardar lo existente

- `e2ea0ec`: navegación y scroll de plataforma.
- `92715a7`: snapshot de interfaz de identidad, conservado como trabajo pendiente; no acredita extracción documental automática ni validación integral del contrato.
- `4e024e5`: primera actualización de criterios; el presente cambio corrige ese seguimiento con la aceptación explícita posterior del usuario.

SM-39–42 y SM-45/46 siguen pendientes; SM-47/48 corresponden a otros responsables. No hubo push, migración de la base de aplicación, seed ni modificación de registros de aplicación en esta actualización.
