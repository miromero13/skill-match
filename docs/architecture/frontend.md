# SkillMatch — Arquitectura Detallada del Frontend y Mobile

*Especificación técnica para la aplicación cliente Web y Móvil (React 19 + TypeScript + Zustand + Shadcn Mist + Capacitor).*

---

## 1. Visión y Principios del Cliente

SkillMatch unifica la experiencia Web Desktop y Móvil en una única base de código React enriquecida con TypeScript, empaquetada nativamente en dispositivos móviles mediante **Capacitor**:

1. **Rendimiento React 19:** Componentes funcionales modernos, renderizado eficiente y carga diferida (*lazy loading*) de rutas pesadas (ej. editor de código Monaco, grabador de video/audio).
2. **Estado Desacoplado y Atómico con Zustand:** Se eliminan los contextos monolíticos pesados. Cada módulo cuenta con su store específico (`useAuthStore`, `useEvaluationStore`, `useWalletStore`, `useMatchingStore`).
3. **Consumo Estricto de APIResponse:** El cliente lee siempre la estructura `{ statuscode, message, data, count }`. Los toasts y mensajes de error muestran textualmente el valor de `message` retornado por el backend.
4. **Política 404 para Rutas Administrativas:** Si un usuario con rol `MEMBER` o no autenticado intenta navegar a `/admin/...`, la guardia de rutas no muestra un acceso denegado ni un 403, sino que renderiza directamente la pantalla **404 Not Found**.

---

## 2. Sistema de Diseño (Design System) y Estilos

- **Librería de Componentes:** Shadcn/ui con el preset **Mist**.
- **Tipografía:** `Inter` como fuente principal legible y moderna.
- **Paleta de Colores Canónica:**
  - Color Primario (Esmeralda Institucional): `oklch(0.511 0.096 186.391)` $\to$ `#00786F`.
  - Fondo y Superficies: Tonos fríos de gris y pizarra (*Slate / Zinc*) para paneles de código y dashboards.
- **Iconografía:** `lucide-react` para toda la simbología de interfaz (prohibido el uso de emojis en componentes formales o cards).

---

## 3. Disposición y Navegación Adaptativa (Responsive Layout)

### 3.1 Web Desktop
- **Layout Shell Maestro (tipo red social profesional):**
  - **Topbar / Header:** Barra superior fija y limpia con logotipo institucional, buscador global dinámico y accesos directos (Notificaciones, Billetera, Perfil).
  - **Sidebar Izquierdo (260px):** Navegación contextual. Los enlaces administrativos solo se renderizan si el rol autenticado es `ADMIN`.
  - **Área Central (Feed / Canvas):** Espacio de trabajo dinámico para tarjetas de coincidencia, paneles de sesión o catálogo.
  - **Sidebar Derecho:** Resumen de habilidades del usuario (distinguiendo habilidades verificadas con badge de escudo verde de las auto-declaradas).

### 3.2 Mobile Responsive & Capacitor
- **Bottom Navigation Bar:** Barra inferior persistente para navegación rápida con un pulgar (Inicio, Búsqueda, Mis Sesiones, Billetera, Perfil).
- **Header Móvil Compacto:** Logo y botón de menú desplegable para accesos secundarios.
- **APIs Nativas vía Capacitor:**
  - `@capacitor/camera`: Captura de video para evaluación de fútbol y supervisión visual.
  - Micrófono y Audio: Acceso a grabación de audio de baja latencia para instrumentos musicales.
  - Almacenamiento seguro de tokens JWT en el almacenamiento nativo del dispositivo.

---

## 4. Estructura de Carpetas Prevista (`frontend/`)

```text
frontend/
├── src/
│   ├── assets/               # Recursos gráficos estáticos y logotipos
│   ├── components/           # Componentes UI reutilizables (Shadcn Mist)
│   │   ├── common/           # Botones, modales, tablas, alertas
│   │   ├── layout/           # Header, Sidebar, BottomNav, Footer
│   │   └── modules/          # Componentes específicos por dominio
│   ├── hooks/                # Hooks personalizados (useMediaQuery, useWebSocket, etc.)
│   ├── pages/                # Vistas de página enrutadas por React Router
│   │   ├── admin/            # Vistas protegidas por rol ADMIN (protección 404 para MEMBER)
│   │   ├── auth/             # Registro social, login OTP y login admin
│   │   ├── evaluation/       # Layout de examen: Monaco Editor, cámara, metrónomo
│   │   ├── public/           # Landing page institucional y Pasaporte público QR
│   │   └── user/             # Perfil, disponibilidad, billetera, sesiones
│   ├── services/             # Clientes de API con Axios o Fetch envueltos en APIResponse
│   ├── stores/               # Tiendas atómicas de Zustand
│   │   ├── authStore.ts
│   │   ├── evaluationStore.ts
│   │   ├── matchingStore.ts
│   │   └── walletStore.ts
│   ├── types/                # Definiciones de TypeScript e interfaces de APIResponse
│   ├── App.tsx               # Enrutador principal y configuración de temas
│   └── main.tsx              # Punto de entrada de la aplicación
├── capacitor.config.ts       # Configuración de empaquetado nativo
├── tailwind.config.js        # Configuración de Tailwind y preset Mist
└── vite.config.ts            # Configuración de Vite y plugins
```
