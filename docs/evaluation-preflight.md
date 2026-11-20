# Pre-embarque compartido de evaluaciones — SM-23

Las instrucciones y el consentimiento son comunes a todas las habilidades. Leerlas o aceptarlas **no consume un intento**. El inicio efectivo del examen, después de la calibración, consume el intento de forma irreversible; abandonar después no lo devuelve.

## Endpoints disponibles

Ambos requieren una sesión MEMBER y el identificador de la habilidad **ofrecida por ese miembro**, no el identificador del catálogo.

| Método y ruta | Efecto |
|---|---|
| `GET /api/evaluations/skills/{teaching_skill_id}/preflight` | Consulta instrucciones, requisitos y cupos sin crear una evaluación |
| `POST /api/evaluations/skills/{teaching_skill_id}/consent` | Registra consentimiento e inicializa `PENDING_CALIBRATION`, sin consumir cupos |

El POST recibe:

```json
{
  "biometric_consent": true,
  "integrity_consent": true,
  "attempt_rule_accepted": true,
  "policy_version": "v1.0"
}
```

Debe existir enrolamiento facial previo. Se registra fecha del servidor, versión de política, IP de conexión y user-agent. Repetir el consentimiento devuelve la misma evaluación sin cambiar su aceptación original. Los rechazos usan `statuscode`, `message` y `data: null`.

## Consumo del intento

El historial de cupos se calcula a partir de `started_at`, nunca de la mera existencia de una evaluación ni de su estado de preparación. Una evaluación iniciada cuenta aunque luego termine abandonada o fallida. Se mantienen tres habilidades gratuitas y un intento gratuito por habilidad; no se implementa recarga ni pago.

**Límite de esta entrega:** no existe aquí un endpoint de inicio ni un atajo de calibración. SM-44 debe verificar el ambiente e identidad, y el inicio real de SM-39 deberá, de forma atómica e idempotente, revalidar cupos y registrar `started_at` una sola vez. No atribuir esta entrega a un examen ya ejecutable ni a un descuento real ya conectado.

La duración estimada no se inventa: se informa como no configurada mientras no exista la configuración de la prueba. La interfaz tampoco presenta una cámara de demostración como calibración real.

## Interfaz y referencias del prototipo

La preparación usa las vistas exportadas de OpenPencil **04A/04B/04C** (web) y **06A/06B/06C** (móvil), disponibles en `docs/prototipo/png/`. Se conserva la tarjeta central, el indicador de tres pasos, los paneles de fondo suave y las acciones inferiores; en móvil se apilan los campos y la vista de cámara.

1. **Instrucciones:** habilidad real, temario, etapas, requisitos, duración configurada y cupos. No se inventa un selector de nivel ni una duración que el backend aún no proporciona.
2. **Normas:** tres consentimientos explícitos y aviso de consumo irreversible al iniciar. `Registrar consentimiento` habilita la calibración solo después de la confirmación del servidor.
3. **Calibración:** vista previa con guía facial, estado del micrófono y resultados reales de la captura. No se muestran verificaciones exitosas antes de comprobarlas. `Volver a Normas` cierra los dispositivos y permite revisar las condiciones, sin revocar el consentimiento ya registrado. `Comenzar primera prueba` permanece deshabilitado: el inicio real de SM-39 todavía no está integrado.

La adaptación visual no sustituye una comparación en navegador ni pruebas con cámara física.

## Migración y datos

La revisión `9b742e18ac30` agrega la tabla vacía `evaluations`. Su padre es `006744e724ff`, una migración de merge ya presente en el árbol de trabajo del usuario. No se modifican esos merges ni se aplican migraciones automáticamente a la base local.

No se incluyen seeders. Las pruebas de aceptación crean y revierten su propio esquema aislado. Antes de usar esta función en la aplicación real, debe estar aplicada la migración con los merges anteriores presentes.

## Verificación

Pruebas públicas: `cd backend && .venv/bin/python -m pytest tests/test_evaluation_preflight.py -q`.

Cubren consulta sin consumo, consentimiento repetido, enrolamiento, propiedad, autenticación, política vigente y agotamiento por inicios anteriores. El examen completo y su transición de inicio necesitan las historias siguientes.
