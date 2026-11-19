/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_ENV?: string
  readonly VITE_BROWSER_SUPERVISION_TRIAL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
