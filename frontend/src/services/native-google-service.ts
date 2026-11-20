import { Capacitor } from "@capacitor/core"
import { SocialLogin } from "@capgo/capacitor-social-login"

let initialization: Promise<void> | undefined
const validClientId = (value: string | undefined): value is string =>
  Boolean(value?.endsWith(".apps.googleusercontent.com") && !value.includes("tu-google"))

export function nativeGoogleConfigured(): boolean {
  return validClientId(import.meta.env.VITE_GOOGLE_CLIENT_ID) &&
    (Capacitor.getPlatform() !== "ios" || validClientId(import.meta.env.VITE_GOOGLE_IOS_CLIENT_ID))
}

/** Only obtains a Google credential. The backend alone verifies it and issues a session. */
export async function getNativeGoogleCredential(): Promise<string> {
  if (!Capacitor.isNativePlatform() || !nativeGoogleConfigured()) {
    throw new Error("El acceso con Google no está configurado.")
  }
  const webClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string
  if (!initialization) {
    initialization = SocialLogin.initialize({ google: {
      webClientId, mode: "online", skipAuthOnlyAuthorizationAfterSignIn: true,
      ...(Capacitor.getPlatform() === "ios" ? {
        iOSClientId: import.meta.env.VITE_GOOGLE_IOS_CLIENT_ID as string,
        iOSServerClientId: webClientId,
      } : {}),
    } }).catch((error: unknown) => { initialization = undefined; throw error })
  }
  await initialization
  const response = await SocialLogin.login({ provider: "google", options: {} })
  const result = response.result
  if (!("idToken" in result) || typeof result.idToken !== "string" || !result.idToken) {
    throw new Error("Google no devolvió una credencial válida.")
  }
  return result.idToken
}
