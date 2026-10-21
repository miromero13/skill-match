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

### Paso 4: Realizar commits siguiendo la guía de Conventional Commits
Sigue la guía detallada de la **Sección 3** para estructurar tus mensajes.

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
4. Describe brevemente el cambio, el problema que soluciona o la Historia de Usuario asociada, y la evidencia de que las pruebas pasaron localmente.

---

## 3. ¿Cómo hacer un buen Commit en Git?

Para poder crear un commit utilizaremos el comando `git commit`:

```bash
git commit -m "feat(users): enable user profile"
```

El flag `-m` agregado al comando `git commit` nos permitirá agregar un commit a la rama que estamos trabajando y de nueva cuenta aquí vuelve a existir otro conflicto, ya que si no tenemos estructuras, estándares o referencias para poder generarlos, seguramente se volverán un caos.

Ten en consideración lo siguiente: Probablemente el commit que generas hoy, lo tendrás que volver a revisar en algún tiempo: días, semanas, meses o años y si no damos la descripción adecuada, probablemente se vuelva un lío.

Para que esto no suceda, en la comunidad hay distintas sugerencias, sin embargo, una de las más utilizadas, se denomina **conventional commits**.

En términos resumidos, conventional commits sugiere lo siguiente:

### El mensaje del commit deberá seguir una estructura, la cual es:

```
<tipo>[ámbito opcional]: <descripción>

[cuerpo opcional]

[nota(s) al pie opcional(es)]
```

Por lo que las recomendaciones son:

**El commit siempre deberá iniciar con un tipo**, algunos de los tipos disponibles que comúnmente se pueden agregar son:

- **feat:** Agregar nueva funcionalidad.
- **fix:** Al arreglar un error o bug.
- **chore:** Tareas que no sean una nueva funcionalidad como:
  - crear un gitignore
  - actualizar el readme file
  - agregar nueva librería o dependencia
- **test:** Agregar o modificar tests.
- **docs:** Agregar o modificar documentación.
- **refactor:** Refactorizar el código sin alterar su lógica funcional.
- **perf:** Mejorando el rendimiento o performance.

Lo siguiente es que **el ámbito puede ser opcional**, como lo menciona la estructura, por ejemplo: podemos poner `api`, que significa que el ámbito es la api, o `users`, que significaría el módulo de usuarios, etc.

Referencia: [Buenas prácticas para escribir commits en Git](https://midu.dev/buenas-practicas-escribir-commits-git/)

**Se deberá redactar el mensaje del commit OBLIGATORIAMENTE EN INGLÉS**, empezando siempre por un verbo en imperativo (por ejemplo: `add`, `create`, `fix`, `update`, `remove`, `enable`, `refactor`, etc.).

Ejemplos correctos:
- `feat(users): enable user profile`
- `fix(auth): fix token expiration calculation`
- `docs(readme): update env template instructions`
- `test(health): add integration test for database connectivity`

> [!IMPORTANT]
> **El idioma de los mensajes de commit es estrictamente INGLÉS.**
> **NO se usan puntos finales al término de la descripción.**
> **La descripción deberá tener como máximo hasta 50 caracteres.**

---

## 4. Manejo de Secretos y Seguridad

1. **Nunca comitear archivos `.env` reales:**
   - Todo archivo con credenciales privadas, tokens o contraseñas debe permanecer ignorado en `.gitignore`.
   - Actualiza únicamente `env.template` y el bloque `bash` en `backend/README.md` si agregas una nueva variable requerida por el sistema.
2. **Uso de SecretStr:**
   - En el backend, cualquier variable que almacene tokens, contraseñas o claves privadas debe declararse estrictamente como `SecretStr` en `Settings` para evitar fugas en logs o respuestas HTTP.
3. **Restricción de IA Propia:**
   - Queda terminantemente prohibido integrar APIs comerciales cerradas de IA (OpenAI, Anthropic, Gemini). Toda inferencia debe realizarse localmente en infraestructura propia con herramientas open-source (`PyTorch`, `OpenCV`, `librosa`, `ast`).

---

## 5. Contrato de Respuesta Unificado (Backend)

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

## 6. Checklist para Aprobar un Pull Request

Antes de que un PR sea fusionado en `dev`, el revisor debe constatar:
- [ ] El PR apunta a la rama **`dev`** (nunca a `main`).
- [ ] Todos los mensajes de commit están redactados estrictamente en **inglés** bajo Conventional Commits, sin punto final y con un máximo de 50 caracteres en el título.
- [ ] No contiene credenciales ni secretos en el código ni en el historial de commits.
- [ ] Todas las pruebas automatizadas pasan al 100% (`uv run pytest -v`).
- [ ] Los endpoints cumplen con el sobre estándar `APIResponse`.
- [ ] La documentación OpenAPI / Swagger UI (`/docs`) refleja fielmente los contratos de entrada y salida.
- [ ] Se actualizaron `backend/env.template` y `backend/README.md` si se añadieron nuevas variables de entorno.
