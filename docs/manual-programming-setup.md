# Preparar manualmente la validación de programación

El backend no ejecuta seeders al arrancar. Esta guía carga únicamente lo necesario para desarrollar validación de programación y anticopia, sin guitarra ni deportes. No ejecutes estos pasos hasta que quieras dejar de tener la base vacía.

## 1. Crear el primer administrador, una sola vez

No existe un registro público de administradores. Cuando no hay ninguno, es necesario un alta manual local; los siguientes administradores se crean desde la administración existente.

Configurá `ADMIN_EMAIL`, `ADMIN_PASSWORD` y `ADMIN_FULL_NAME` en `backend/.env` con tus propios datos y una contraseña segura. No uses el correo de tu cuenta Google de miembro: son cuentas distintas. Estas variables no crean registros al iniciar el backend.

Desde `backend/`, ejecutá explícitamente este comando. No es un seeder de arranque y no carga catálogo ni usuarios de prueba:

```bash
.venv/bin/python - <<'PY'
import asyncio
from sqlalchemy import select
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal, async_engine
from app.models import User, UserRole

async def main():
    try:
        async with AsyncSessionLocal() as db:
            existing = await db.scalar(select(User.id).where(User.role == UserRole.ADMIN))
            if existing is not None:
                raise RuntimeError("Ya existe un administrador; usá la administración existente.")
            email = settings.ADMIN_EMAIL.strip().lower()
            if await db.scalar(select(User.id).where(User.email == email)) is not None:
                raise RuntimeError("El correo ya pertenece a otra cuenta; elegí otro correo.")
            db.add(User(
                email=email,
                full_name=settings.ADMIN_FULL_NAME,
                hashed_password=get_password_hash(settings.ADMIN_PASSWORD.get_secret_value()),
                role=UserRole.ADMIN,
                provider="institutional",
                is_active=True,
                is_locked=False,
                failed_login_attempts=0,
            ))
            await db.commit()
            print("Administrador creado manualmente.")
    finally:
        await async_engine.dispose()

asyncio.run(main())
PY
```

No ingreses contraseñas en texto plano en `users.hashed_password` ni conviertas tu cuenta Google a ADMIN.

## 2. Arrancar la aplicación e ingresar como administrador

1. Iniciá backend y frontend según sus README.
2. Ingresá por el acceso administrativo con las credenciales del paso anterior.
3. Si usás Swagger (`http://localhost:8000/docs`), obtené el token mediante `POST /api/admin/auth/login` y usalo en **Authorize**.

El arranque no debe agregar categorías, habilidades ni otros usuarios. Si falta una dependencia del backend, resolvé esa instalación antes de seguir; no reemplaces el flujo real por datos SQL ficticios.

## 3. Crear la categoría de programación

Desde el catálogo administrativo o `POST /api/admin/catalog/categories`:

```json
{
  "name": "Programación",
  "description": "Evaluación de programación en Python",
  "is_active": true
}
```

Guardá el `data.id` de la respuesta como `CATEGORY_ID`.

## 4. Crear el tipo de desafío

Usá `POST /api/admin/catalog/challenge-types`:

```json
{
  "name": "Sandbox de Código AST",
  "code": "CODE_AST",
  "evaluation_modality": "SANDBOX",
  "description": "Pruebas de código Python y análisis AST",
  "is_active": true
}
```

Guardá el `data.id` como `CHALLENGE_TYPE_ID`. Esto registra el tipo de evaluación, no implementa el sandbox.

## 5. Crear y activar una sola habilidad

Usá el catálogo administrativo o `POST /api/admin/catalog/skills`, reemplazando los dos identificadores por los UUID reales:

```json
{
  "category_id": "CATEGORY_ID",
  "challenge_type_id": "CHALLENGE_TYPE_ID",
  "name": "Python",
  "description": "Fundamentos y resolución de problemas en Python",
  "min_approval_threshold": 80,
  "is_ready_to_publish": false
}
```

El servicio crea cinco niveles cuando omitís `levels`: Principiante, Elemental, Intermedio, Avanzado y Master Pedagogo. Es comportamiento de esta operación manual, no un seeder. No inventes todavía rúbricas definitivas ni preguntas de examen.

Guardá el `data.id` como `SKILL_ID`. La habilidad se crea inactiva: activala con `PATCH /api/admin/catalog/skills/{SKILL_ID}/status` y cuerpo `{"is_active": true}` para que pueda seleccionarse como habilidad ofrecida. `is_ready_to_publish` y `is_active` son campos distintos; activar el catálogo no significa que el motor de evaluación esté terminado.

## 6. Crear tu cuenta de miembro con Google

1. Cerrá la sesión administrativa o usá otro perfil del navegador.
2. Ingresá con Google usando un correo diferente al administrador.
3. Completá tu perfil desde la aplicación.
4. Realizá el enrolamiento facial con tu cámara usando la funcionalidad del perfil.
5. Comprobá que el perfil informe el enrolamiento completado; no marques el indicador directamente en SQL ni pegues embeddings inventados.

El rostro registrado será la referencia para SM-44; todavía no reemplaza la prueba de vida al comenzar una evaluación.

## 7. Agregar Python como habilidad que enseñás

Desde **Mis habilidades**, seleccioná Python en las habilidades ofrecidas, elegí tu nivel declarado y completá los campos que solicite el formulario.

La API asociada es `POST /api/users/me/teaching-skills`; podés consultar el resultado con `GET /api/users/me/teaching-skills` usando tu sesión MEMBER. Guardá el identificador de esa oferta como `TEACHING_SKILL_ID`: no es el mismo identificador que `SKILL_ID` del catálogo.

No agregues Python únicamente como habilidad que querés aprender. No marques la oferta como verificada: eso debe hacerlo el resultado de la evaluación.

## 8. Punto de partida para tus tareas

Antes de desarrollar el flujo, comprobá:

- [ ] Existe un administrador creado manualmente.
- [ ] Existe la categoría Programación y un tipo de desafío CODE_AST.
- [ ] Existe Python activo en el catálogo.
- [ ] Podés ingresar como MEMBER con Google.
- [ ] Tu perfil tiene enrolamiento facial real.
- [ ] Tenés Python como habilidad ofrecida, todavía sin certificar.

A partir de ahí, el orden funcional es SM-23 (instrucciones y consentimiento) → SM-44 (calibración e identidad) → SM-39 (teoría) → SM-40 (código) → SM-41 y detección de similitud explícita → SM-42 (defensa) → SM-45 (resultado y sello). SM-43 y SM-49 supervisan transversalmente el examen; SM-46 permite auditoría y apelación.

Estos pasos preparan los prerrequisitos; no prueban que las historias de evaluación ya estén implementadas. No cargues intentos, sanciones, resultados ni certificados ficticios para saltarte el flujo.
