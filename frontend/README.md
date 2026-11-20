# SkillMatch — Frontend & Mobile App

Plataforma descentralizada de intercambio recíproco y triangular de habilidades con validación objetiva por Inteligencia Artificial y pasaporte de confianza.

---

## 🛠️ Stack Tecnológico

- **Framework Web:** [React 19](https://react.dev/) + [TypeScript 6](https://www.typescriptlang.org/) + [Vite 8](https://vite.dev/)
- **Estilos & Componentes UI:** [Tailwind CSS v4](https://tailwindcss.com/) + [Shadcn UI](https://ui.shadcn.com/) (Preset **Mist**, tipografía **Inter Variable** y Radix UI)
- **Tema Visual:** Modo Claro / Modo Oscuro con detección automática del sistema operativo (`system default`) y alternador dinámico
- **Enrutamiento:** [React Router v7](https://reactrouter.com/) con 3 layouts arquitectónicos (`PublicLayout`, `PlatformLayout`, `ExamLayout`) y pantalla 404 dedicada
- **Estado Global:** [Zustand](https://github.com/pmndrs/zustand) con persistencia web en `localStorage`; las credenciales nativas usan almacenamiento seguro del dispositivo
- **Cliente HTTP:** Cliente nativo tipado basado en **Fetch API** con interceptores automáticos de JWT y extracción de mensajes para notificaciones con **Sonner**
- **Soporte Móvil:** [Capacitor 8](https://capacitorjs.com/) (`@capacitor/android`, `@capacitor/ios`) configurado con `appId: com.skillmatch.app` y permisos de hardware para cámara y micrófono

---

## 📁 Arquitectura del Proyecto

```
frontend/
├── android/                    # Proyecto nativo Android (Gradle, AndroidManifest.xml)
├── ios/                        # Proyecto nativo iOS (Xcode, Info.plist, Swift)
├── src/
│   ├── components/
│   │   ├── navigation/         # PublicNavbar, PublicFooter, PlatformHeader, PlatformSidebar, MobileBottomBar
│   │   ├── ui/                 # 45 componentes oficiales de Shadcn UI (Button, Card, Dialog, Sidebar, etc.)
│   │   ├── mode-toggle.tsx     # Selector de tema Claro / Oscuro / Sistema
│   │   └── theme-provider.tsx  # Proveedor React Context de Dark Mode reactivo
│   ├── layouts/
│   │   ├── public-layout.tsx   # Layout institucional con Navbar fija y Footer
│   │   ├── platform-layout.tsx # Layout autenticado con Header Facebook, Sidebar y Bottom Bar de 54px
│   │   └── exam-layout.tsx     # Layout minimalista full-screen para evaluaciones y sandbox Docker
│   ├── pages/
│   │   ├── landing-page.tsx    # Portada pública (Hero, 3 pasos, Demos IA)
│   │   ├── feed-page.tsx       # Feed principal con Match Cards y compatibilidad
│   │   ├── exam-page.tsx       # Sandbox con editor de código, Pytest y telemetría de cámara
│   │   └── not-found-page.tsx  # Pantalla 404 dedicada
│   ├── routes/
│   │   └── index.tsx           # Configuración declarativa de rutas con createBrowserRouter
│   ├── services/
│   │   ├── api-client.ts       # Cliente HTTP Fetch tipado con interceptores
│   │   └── index.ts            # Exportaciones de servicios
│   ├── stores/
│   │   ├── auth-store.ts       # Sesión JWT, perfil de usuario y saldo de SkillPoints
│   │   ├── ui-store.ts         # Modales y drawers móviles
│   │   └── swap-store.ts       # Propuestas e intercambios activos
│   ├── types/
│   │   └── api.ts              # Sobre canónico APIResponse<T> y ApiError
│   ├── App.tsx                 # Entrada con TooltipProvider, Toaster y RouterProvider
│   └── index.css               # Variables CSS de diseño Mist (oklch) y reglas de tema
├── capacitor.config.ts         # Configuración central de Capacitor
└── package.json
```

---

## 🚀 Guía de Ejecución

### 1. Desarrollo Web
```bash
cd frontend
npm install
npm run dev
```
La aplicación estará disponible en `http://localhost:5173`.

### 2. Compilación de Producción Web
```bash
npm run build
```

### 3. Assets de visión autoalojados (seguimiento de mirada en el navegador)
La prueba de supervisión corre MediaPipe FaceLandmarker en el navegador (~15 fps, `@mediapipe/tasks-vision` 1.2.3) para la
mirada y las señales en vivo; el servidor vuelve a medir los frames muestreados y es quien decide. No se usa ningún CDN en
tiempo de ejecución: los assets se sirven desde `public/mediapipe/` (ignorado por git) y los provee
`scripts/install-vision-assets.mjs`:

| Comando | Qué hace |
|---|---|
| `npm install` (`postinstall`) | Copia los `.wasm` de `node_modules/@mediapipe/tasks-vision/wasm` a `public/mediapipe/wasm/` (sin red). |
| `npm run prepare-vision` | Lo anterior + instala `public/mediapipe/face_landmarker.task`: lo copia de `backend/app/models/weights/` si existe con el hash correcto; si no, lo descarga por HTTPS y verifica el SHA-256 fijado (`64184e22…c9ff`, el mismo que usa el backend). Nunca sobrescribe un archivo existente con otro hash. |
| `npm run dev` / `npm run build` (`predev`/`prebuild`) | Ejecutan el script con `--soft`: un modelo que no se puede instalar es solo un aviso y el seguimiento del navegador queda deshabilitado (el servidor igual controla la mirada). |
| `node scripts/install-vision-assets.mjs --verify-only` | Verifica los assets instalados sin copiar ni descargar. |

---

## ⚙️ Variables de Entorno (.env)

Copia el archivo de plantilla `env.template` a tu archivo local `.env`:
```bash
cp env.template .env
```

| Variable | Descripción | Valor por Defecto |
|---|---|---|
| `VITE_API_URL` | URL base de la API backend FastAPI. En desarrollo apunta directamente a `http://localhost:8000/api` (autorizado en `ALLOWED_ORIGINS` del backend). | `"http://localhost:8000/api"` |
| `VITE_APP_ENV` | Entorno de despliegue (`development`, `staging`, `production`). | `"development"` |
| `VITE_APP_NAME` | Nombre de la plataforma mostrado en la interfaz. | `"SkillMatch"` |
| `VITE_GOOGLE_CLIENT_ID` | Cliente OAuth Web de Google, idéntico a `GOOGLE_CLIENT_ID` del backend. También es la audiencia de los tokens nativos. Sin configurar, el login queda deshabilitado; no hay cuentas simuladas. | `""` |
| `VITE_GOOGLE_IOS_CLIENT_ID` | Cliente OAuth de tipo iOS para `com.skillmatch.app`. Requiere configurar su esquema invertido en `ios/App/App/Info.plist`. | `""` |
| `VITE_APP_VERSION` | Versión semántica del cliente frontend. | `"0.1.0"` |
| `VITE_BROWSER_SUPERVISION_TRIAL` | Fuerza encendida (`"true"`) o apagada (`"false"`) la prueba de supervisión del navegador (SM-43, `/app/browser-supervision-test`). Vacío/sin definir = activa solo en modo desarrollo de Vite (`DEV`). Nunca se habilita si `VITE_APP_ENV="production"`, sin importar este valor. | `""` (sin definir) |

Plantilla lista para copiar y pegar:
```bash
# ==============================================================================
# SkillMatch Frontend — Variables de Entorno (.env)
# ==============================================================================
VITE_API_URL="http://localhost:8000/api"
VITE_APP_ENV="development"
VITE_APP_NAME="SkillMatch"
VITE_APP_VERSION="0.1.0"
VITE_GOOGLE_CLIENT_ID="tu-google-client-id.apps.googleusercontent.com"
VITE_GOOGLE_IOS_CLIENT_ID=""
# VITE_BROWSER_SUPERVISION_TRIAL="true"
```

---

## 🐳 Docker

El stack completo se levanta con Docker Compose desde la raíz del repositorio; ver la guía
[`docs/deployment/docker.md`](../docs/deployment/docker.md). La imagen del frontend (`frontend/Dockerfile`, contexto
`./frontend`) tiene dos targets:

| Target | Uso | Puerto |
|---|---|---|
| `dev` | Servidor de Vite con recarga en caliente (`npm run dev -- --host 0.0.0.0 --port 5173`). | `5173` |
| `runtime` (por defecto, última etapa) | `nginxinc/nginx-unprivileged:1.29-alpine` sirve el `dist/` compilado. | `8080` |

Las variables `VITE_*` se **incrustan en el bundle al compilar**: se pasan como build args y cambiar cualquiera exige
reconstruir la imagen (no se leen en tiempo de ejecución ni se copia ningún `.env` a la imagen). No son secretos.

| Build arg | Obligatorio | Valor por defecto |
|---|---|---|
| `VITE_API_URL` | Sí. URL absoluta `http(s)://…/api` del mismo origen que sirve el frontend (p. ej. `https://skillmatch.example.com/api`). La compilación falla si está vacía o no termina en `/api`. | — |
| `VITE_APP_ENV` | No | `production` |
| `VITE_GOOGLE_CLIENT_ID` | No (sin él, el login con Google queda deshabilitado) | `""` |
| `VITE_GOOGLE_IOS_CLIENT_ID` | No | `""` |
| `VITE_BROWSER_SUPERVISION_TRIAL` | No (ignorado si `VITE_APP_ENV=production`) | `""` |

```bash
cd frontend
docker build --build-arg VITE_API_URL=http://localhost:8080/api -t skillmatch-frontend .   # runtime
docker build --target dev -t skillmatch-frontend:dev .
```

En el target `runtime`, nginx (`nginx/default.conf`) es el **único origen público**: sirve la SPA (fallback a
`index.html`) y hace de proxy inverso de `/api/` y `/ws/` hacia `http://backend:8000` (resolver DNS de Docker, cabeceras de
WebSocket, timeouts de 1 h, cuerpos de hasta 200 MB), por lo que el backend no publica puertos. `/docs`, `/redoc` y
`/openapi.json` nunca se reenvían (responden 404). `GET /healthz` responde `200 ok` para el healthcheck. `index.html` y
`/service-worker.js` se sirven con `Cache-Control: no-cache`; `/assets/` (con hash) como inmutables por un año.

---

## 📱 Flujo de Trabajo Móvil (Capacitor)

### Sincronizar Cambios Web con Android e iOS
Cada vez que hagas un cambio en el código frontend, sincronizalo con las plataformas nativas:
```bash
npm run build:mobile
# O directamente:
npm run cap:sync
```

### Abrir en Android Studio
```bash
npm run cap:android
```

### Abrir en Xcode (macOS)
```bash
npm run cap:ios
```

---

## 🔒 Permisos Nativos Configurados

- **Android (`android/app/src/main/AndroidManifest.xml`):**
  - `android.permission.CAMERA`
  - `android.permission.RECORD_AUDIO`
  - `android.permission.MODIFY_AUDIO_SETTINGS`
- **iOS (`ios/App/App/Info.plist`):**
  - `NSCameraUsageDescription`: *"SkillMatch requiere acceso a la cámara para la prueba de vida y validación de habilidades."*
  - `NSMicrophoneUsageDescription`: *"SkillMatch requiere acceso al micrófono para la evaluación oral y pruebas de audio."*


## 🔐 Autenticación y sesiones (HU-07 a HU-10)

- **Miembros:** solo Google. Web usa el botón oficial de Google Identity Services; Android/iOS usan `@capgo/capacitor-social-login` con únicamente Google habilitado. El perfil del SDK no crea una sesión: el ID token siempre se verifica en el backend.
- **Administradores:** únicamente correo y contraseña en `/admin/login`. Cualquier ADMIN activo puede gestionar otros administradores; no hay jerarquía por correo de seed ni rol SuperAdmin.
- **Saldo:** se muestra el saldo persistido de la billetera, inicialmente 0. No se implementan recargas, pagos, transferencias ni retiros.
- **Web:** los tokens se persisten en localStorage; esto no es almacenamiento cifrado y exige prevenir XSS.
- **Nativo:** `@aparajita/capacitor-secure-storage@8.0.1`, iOS Keychain sin sincronización/vinculado al dispositivo y almacenamiento protegido en Android. Preferences solo se consulta para migrar credenciales antiguas y eliminarlas después de la escritura cifrada. No hay fallback a texto plano.
- Las guardias esperan la hidratación. Las renovaciones concurrentes se coordinan y las respuestas tardías de refresh/logout no reemplazan una sesión posterior.
- Los logs del puente nativo están deshabilitados para no volcar respuestas con credenciales.

### Configurar Google nativo antes de probar con cuentas reales

1. Crear un cliente OAuth **Web** y usar el mismo ID en `VITE_GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_ID` del backend. Autorizar el origen web de desarrollo/producción en Google Cloud.
2. **Android:** registrar `com.skillmatch.app` y los SHA-1 de las claves de firma correspondientes (debug, release y Play App Signing). Obtener la firma local con `cd android && ./gradlew signingReport`. El ID de cliente Android no reemplaza al ID Web.
3. **iOS:** crear el cliente OAuth iOS para `com.skillmatch.app` y establecer `VITE_GOOGLE_IOS_CLIENT_ID`. En `ios/App/App/Info.plist`, reemplazar `com.googleusercontent.apps.replace-with-ios-client-id` por el ID iOS invertido, por ejemplo `com.googleusercontent.apps.PREFIX` para `PREFIX.apps.googleusercontent.com`. Mantener el reenvío de URLs de `SceneDelegateProxy`: el plugin registra su observador de callbacks de Google.
4. Ejecutar `npm run build:mobile`, compilar y probar el ingreso, cierre de sesión y reapertura en un dispositivo/simulador configurado. Una compilación nativa o un doble del SDK no acredita login real ni protección del almacenamiento en un dispositivo.

Referencias: [Google en Android](https://capgo.app/docs/plugins/social-login/google/android/) y [Google en iOS](https://capgo.app/docs/plugins/social-login/google/ios/).

## 🗂️ Catálogo jerárquico (HU-12)

El backoffice permanece en `/admin/catalog` (alias `/admin/skills`). Permite crear/editar categorías y subcategorías, moverlas sin ciclos y activar/desactivar ramas. Los nombres se comparan sin diferencias de mayúsculas, acentos ni espacios repetidos dentro del mismo padre/categoría. La búsqueda por categoría incluye descendientes.

Eliminar una habilidad es lógico; si tiene miembros vinculados, el backend responde 409 y se utiliza la desactivación por PATCH, que conserva asociaciones. Las categorías inactivas ocultan su rama del catálogo público, no del backoffice.
