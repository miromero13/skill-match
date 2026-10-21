# Guía de Creación de Pull Requests (PR) — SkillMatch

Para mantener una base de código limpia y un proceso de integración continuo confiable, todo Pull Request debe seguir las buenas prácticas detalladas a continuación.

---

## 1. Regla Fundamental de Destino
- **Rama Base (`base`):** `dev` (Siempre).
- **Rama Origen (`compare`):** Tu rama personal (ej. `dev-luis`) o tu rama de tarea (`feat/<id-historia>-<nombre>`).
- **Prohibido:** Abrir Pull Requests con destino directo a `main`.

---

## 2. Antes de Abrir el Pull Request
1. **Sincronización:** Asegúrate de integrar los últimos cambios de `dev` para evitar conflictos:
   ```bash
   git fetch origin dev
   git merge origin/dev
   ```
2. **Pruebas Automatizadas:** Verifica que toda la suite de tests pase localmente:
   ```bash
   cd backend && uv run pytest -v
   ```
3. **Linter y Formato:** Asegúrate de que no existan errores de sintaxis o formato.
4. **Cero Secretos:** Verifica que no estés agregando ningún archivo `.env` ni credenciales privadas.

---

## 3. Estructura y Título del Pull Request

El título debe seguir el mismo estándar de **Conventional Commits**:
```
<tipo>[ámbito opcional]: <descripción en imperativo> (ID-Historia)
```
Ejemplos:
- `feat(backend): initialize backend base architecture and contracts (HU-03)`
- `feat(auth): implement google oauth and whatsapp otp verification (HU-07)`
- `fix(cors): allow local vite preview origins in allowed list (HU-03)`

---

## 4. Plantilla de Descripción del Pull Request

Copia y completa este formato en la descripción de tu PR en GitHub:

```markdown
## 📌 Descripción del Cambio
Breve explicación de qué problema resuelve este Pull Request o qué funcionalidad introduce.

## 🎯 Historia de Usuario / Issue Asociado
- Relacionado con: **HU-XX** (o issue #XX de Jira/GitHub)

## 🛠️ Tipo de Cambio
- [ ] `feat`: Nueva funcionalidad
- [ ] `fix`: Corrección de bug
- [ ] `chore`: Mantenimiento / dependencias
- [ ] `docs`: Documentación
- [ ] `refactor`: Refactorización de código
- [ ] `perf`: Mejora de rendimiento
- [ ] `test`: Incorporación o mejora de tests

## 🧪 Pruebas Realizadas y Evidencia
- [ ] Pruebas unitarias ejecutadas localmente con resultado exitoso:
  ```text
  [Pegar salida de pytest aquí]
  ```
- [ ] Endpoints probados en Swagger UI (`/docs`).
- [ ] Formato de respuesta verificado bajo `APIResponse`.

## 🔒 Checklist de Seguridad y Calidad
- [ ] El PR apunta a la rama **`dev`**.
- [ ] No incluye archivos `.env`, claves API ni credenciales privadas.
- [ ] No utiliza APIs comerciales de IA de terceros (apego estricto a IA propia).
- [ ] Se actualizaron `backend/env.template` y `backend/README.md` si se añadieron nuevas variables.
```
