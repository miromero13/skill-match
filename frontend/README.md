# SkillMatch — Frontend & Mobile App

Plataforma descentralizada de intercambio recíproco y triangular de habilidades con validación objetiva por Inteligencia Artificial y pasaporte de confianza.

---

## 🛠️ Stack Tecnológico

- **Framework Web:** [React 19](https://react.dev/) + [TypeScript 6](https://www.typescriptlang.org/) + [Vite 8](https://vite.dev/)
- **Estilos & Componentes UI:** [Tailwind CSS v4](https://tailwindcss.com/) + [Shadcn UI](https://ui.shadcn.com/) (Preset **Mist**, tipografía **Inter Variable** y Radix UI)
- **Tema Visual:** Modo Claro / Modo Oscuro con detección automática del sistema operativo (`system default`) y alternador dinámico
- **Enrutamiento:** [React Router v7](https://reactrouter.com/) con 3 layouts arquitectónicos (`PublicLayout`, `PlatformLayout`, `ExamLayout`) y pantalla 404 dedicada
- **Estado Global:** [Zustand](https://github.com/pmndrs/zustand) con persistencia en `localStorage` (`useAuthStore`, `useUiStore`, `useSwapStore`)
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
