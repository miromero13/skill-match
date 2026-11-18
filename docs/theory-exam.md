# SM-39: banco de preguntas y examen oral

SM-39 está en implementación. La API administrativa de borradores está implementada; todavía no existe un examen oral completo ni un corrector habilitado. No se inicia un examen ni se consume un intento al gestionar preguntas.

## Banco administrativo — primera unidad

Acceso exclusivo ADMIN, con sesión administrativa existente. MEMBER y visitantes reciben404 (`Recurso no encontrado`), sin revelar el contenido del banco.

| Operación | Ruta de esta unidad |
|---|---|
| Crear borrador | `POST /api/admin/theory/questions` |
| Listar borradores | `GET /api/admin/theory/questions` |
| Consultar última versión | `GET /api/admin/theory/questions/{id}` |

Filtros: `skill_id`, `level_number` (1–5), `status`; paginación con `offset` (desde0) y `limit` (1–100, por defecto20). `count` representa el total filtrado antes de paginar, no el tamaño de la página. No se incluye `count` en respuestas individuales ni errores.

El borrador requiere una habilidad/nivel existentes y un enunciado no vacío. Puede completarse después: una referencia vacía no autoriza su publicación ni permite usarlo en un examen.

```json
{
  "skill_id": "<UUID de una habilidad existente>",
  "level_number": 1,
  "kind": "OPEN",
  "prompt": "Explicá la diferencia de mutabilidad entre listas y tuplas.",
  "reference_answer": "Las listas son mutables; las tuplas son inmutables.",
  "criteria": [
    {"name": "Mutabilidad", "weight": 100, "description": "Distingue ambas estructuras y explica la posibilidad de modificación."}
  ],
  "time_limit_seconds": 90,
  "max_score": 20
}
```

Tipos previstos: `OPEN`, `MULTIPLE_CHOICE`, `TRUE_FALSE`. Opciones en `choices`: objetos con `code` y `text`; elección correcta en `correct_choice`. El contenido/rúbrica se devuelve únicamente al ADMIN, nunca mediante endpoints de miembros. Cada fila tiene ID y versión; las unidades siguientes habilitarán revisiones/publicación/archivo sin cambiar versiones usadas por exámenes anteriores.

## Base de datos y ejecución

La migración aditiva `c139a820f174`, posterior a `bc43a710d962`, se preparó y comprobó en una base descartable. No se ejecuta automáticamente en tu base ni se insertan preguntas de ejemplo al arrancar. No hay endpoint de borrado en esta unidad.

Verificación aislada desde `backend/`:

```bash
.venv/bin/python .venv/run_suite_hardening.py tests/test_theory_question_bank.py
```

El runner copia el proyecto, migra una base temporal, ejecuta las pruebas y elimina esa base. Conserva los datos de la aplicación y publica códigos de salida separados de migración/pytest.

Comprobación observada: RED11 por endpoints ausentes (job32, pytest1), luego35 pruebas correctas de banco/preflight/calibración/catálogo (job33, migración0/pytest0); bases descartables eliminadas. Son pruebas ejecutadas por el implementador, no revisión independiente.

## Lo que no entrega esta primera unidad

Publicación y revisiones, pantalla administrativa, inicio atómico, preguntas asignadas, respuestas habladas, transcripción, corrección y resultados siguen pendientes hasta completar sus tareas. No hay nuevas variables de entorno ni dependencias aquí. La política vigente prohíbe llamadas externas de IA; ningún borrador ni respuesta se envía a un proveedor.
