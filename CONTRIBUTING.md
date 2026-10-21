# Guía de Contribución para Desarrolladores — SkillMatch

¡Bienvenido al equipo de ingeniería de **SkillMatch**! Para mantener un repositorio profesional, ordenado, seguro y libre de conflictos o regresiones, todos los colaboradores y agentes de desarrollo deben seguir estrictamente el flujo de trabajo y las normas descritas en este documento.

---

## 1. Reglas de Oro de Ramas y Commits (No Negociables)

1. **Prohibido trabajar o pushear directamente sobre las ramas `main` y `dev`:**
   - La rama `main` refleja el código estable en producción.
   - La rama `dev` es la rama de integración continua del equipo.
   - Ningún commit debe ser realizado directamente sobre `main` o `dev`. Todo cambio ingresa **exclusivamente mediante Pull Requests (PR)** aprobados y revisados.
2. **Cada desarrollador debe trabajar en su propia rama dedicada:**
   - Cada colaborador cuenta con su rama personal de trabajo (por ejemplo, `dev-luis`).
   - Para tareas o historias de usuario específicas, se recomienda crear ramas con prefijo semántico que partan de `dev`:
     - `feat/<id-historia>-<descripcion-corta>` (ej. `feat/hu-03-backend-init`)
     - `fix/<id-defecto>-<descripcion-corta>` (ej. `fix/cors-origin-issue`)
     - `docs/<descripcion-corta>` (ej. `docs/contributing-guide`)
     - O en su defecto, avanzar en su rama de desarrollador (ej. `dev-<nombre>`).
3. **El destino de todo Pull Request es siempre la rama `dev`:**
   - Todo PR de nueva funcionalidad o corrección debe apuntar **hacia la rama `dev`**, nunca directo a `main`.
   - La promoción de `dev` a `main` se realiza únicamente al consolidar los entregables de cada Sprint mediante un PR de release.

---

## 2. Flujo de Trabajo Git Paso a Paso (Git Workflow)

### Paso 1: Actualizar la base local
Antes de comenzar cualquier desarrollo, sincroniza tu repositorio local con la rama de integración `dev`:
```bash
git checkout dev
git pull origin dev
```

### Paso 2: Crear o cambiar a tu rama de trabajo
Crea una rama de feature a partir de `dev` o cámbiate a tu rama personal (ej. `dev-luis`):
```bash
# Opción A: Crear rama de feature/tarea específica (Recomendada)
git checkout -b feat/hu-XX-nombre-tarea

# Opción B: Usar tu rama de desarrollador asignada
git checkout dev-luis
git merge dev  # Asegúrate de incorporar los últimos cambios de dev
```

### Paso 3: Desarrollar con pruebas y estándares locales
- Escribe código modular respetando las pautas de [`AGENTS.md`](AGENTS.md) y [`docs/architecture/`](docs/architecture/).
- Asegúrate de que las pruebas pasen antes de hacer commit:
  ```bash
  # En backend:
  cd backend
  uv run pytest -v
  ```

### Paso 4: Realizar commits atómicos bajo Conventional Commits
Utiliza mensajes de commit descriptivos con la convención estándar:
- `feat(...)`: Nueva funcionalidad o capacidad.
- `fix(...)`: Corrección de un defecto o bug.
- `docs(...)`: Cambios exclusivos en documentación.
- `refactor(...)`: Reestructuración de código sin alterar su comportamiento.
- `test(...)`: Incorporación o ajuste de pruebas unitarias/integración.

Ejemplo:
```bash
git add backend/
git commit -m "feat(backend): add auth endpoints for google oauth and whatsapp otp (HU-07)"
```

### Paso 5: Mantener tu rama sincronizada antes de subirla
Antes de abrir el Pull Request, asegúrate de no tener conflictos con los últimos cambios de `dev`:
```bash
git fetch origin dev
git merge origin/dev
```

### Paso 6: Publicar tu rama y abrir el Pull Request hacia `dev`
```bash
git push -u origin <tu-rama>
```
1. Ingresa a GitHub y crea un nuevo Pull Request.
2. **Selecciona como rama base (`base branch`): `dev`**.
3. **Selecciona como rama de origen (`compare branch`): `<tu-rama>`** (ej. `dev-luis` o `feat/hu-XX`).
4. Completa la plantilla del PR describiendo:
   - Qué problema resuelve o qué HU implementa.
   - Qué cambios introduce.
   - Evidencia de pruebas ejecutadas con éxito.

---

## 3. Manejo de Secretos y Seguridad

1. **Nunca comitear archivos `.env` reales:**
   - Todo archivo con credenciales privadas, tokens o contraseñas debe permanecer ignorado en `.gitignore`.
   - Actualiza únicamente `env.template` si agregas una nueva variable requerida por el sistema.
2. **Uso de SecretStr:**
   - En el backend, cualquier variable que almacene tokens, contraseñas o claves privadas debe declararse estrictamente como `SecretStr` en `Settings` para evitar fugas en logs o respuestas HTTP.
3. **Restricción de IA Propia:**
   - Queda terminantemente prohibido integrar APIs comerciales cerradas de IA (OpenAI, Anthropic, Gemini). Toda inferencia debe realizarse localmente en infraestructura propia con herramientas open-source (`PyTorch`, `OpenCV`, `librosa`, `ast`).

---

## 4. Contrato de Respuesta Unificado (Backend)

Todo endpoint desarrollado en el backend debe devolver obligatoriamente el sobre unificado `APIResponse[T]`:
```json
{
  "statuscode": 200,
  "message": "Operación completada exitosamente",
  "data": { ... },
  "count": null
}
```
- No uses campos `error` personalizados.
- Los errores son interceptados por los manejadores globales en `app/core/exceptions.py`.

---

## 5. Checklist para Aprobar un Pull Request

Antes de que un PR sea fusionado en `dev`, el revisor debe constatar:
- [ ] El PR apunta a la rama `dev` (no a `main`).
- [ ] No contiene credenciales ni secretos en el código ni en el historial de commits.
- [ ] Todas las pruebas automatizadas pasan al 100%.
- [ ] Los endpoints cumplen con el sobre estándar `APIResponse`.
- [ ] La documentación OpenAPI / Swagger UI (`/docs`) refleja fielmente los contratos de entrada y salida.
