# Conectar supervisión de navegador y audiovisual al examen real

- **Tipo:** Task
- **Estado:** Por hacer
- **Jira:** [SM-57](https://sauterdevs.atlassian.net/browse/SM-57), creada y consultada mediante MCP
- **Relacionadas:** [SM-43](https://sauterdevs.atlassian.net/browse/SM-43), [SM-49](https://sauterdevs.atlassian.net/browse/SM-49); depende del inicio real de SM-39.

## Objetivo

Conectar al examen real los módulos de supervisión de navegador (SM-43) y audiovisual continua (SM-49), actualmente planteados para un entorno de prueba. SM-43 queda terminada en su alcance de ensayo; SM-49 conserva su implementación propia pendiente. Esta tarea no afirma que SM-49 ya esté implementada ni reabre SM-23/SM-43/SM-44.

## Criterios de aceptación

- [ ] Integrar controles de navegador y supervisión audiovisual continua en el layout y ciclo del examen, reutilizando los módulos de prueba, sin un segundo inicio de examen.
- [ ] Asociar sesión, consentimiento e incidentes a la evaluación y al MEMBER propietario, conservando autorización exclusiva por pestaña y reintentos idempotentes.
- [ ] Publicar registro y consulta de incidentes por evaluación, con tiempos y secuencia del servidor, paginación y sobre APIResponse.
- [ ] Integrar estado y mensajes en el frontend; conectar las vistas de advertencia/expulsión según la política de sanciones que corresponda, sin convertir una interrupción técnica en trampa automática.
- [ ] Activar cámara, micrófono y listeners solo con consentimiento y preparación válidos; detener y liberar al finalizar, cancelar, navegar o fallar.
- [ ] Distinguir pérdida de dispositivo, red o evidencia de posibles incidentes de integridad. No guardar audio/video crudos.
- [ ] Garantizar que preembarque, consentimiento, calibración y ensayo no consuman intentos; el único débito corresponde al inicio atómico/idempotente de SM-39.
- [ ] Verificar el recorrido teoría → práctica → defensa con controles activos, cierre limpio y límites documentados.

## Alcance técnico

La base de SM-43 es `/app/browser-supervision-test` y `/api/browser-supervision/trials`. SM-49 todavía tiene una especificación de implementación continua en `odd/tasks/continuous-supervision.md`; su implementación y la conexión al examen son trabajos distintos. Esta tarea se ejecuta cuando esos componentes y el inicio real estén disponibles.

## Decisión del usuario

> La 23, 44 y 43 ya estan hechas. Edita la info de la 44 y de la 43 y 49 crea un task que diga que hay que conectar porque esta de prubea.
