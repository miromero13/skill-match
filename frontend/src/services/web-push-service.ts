import { apiClient } from "@/services/api-client"
import { useAuthStore } from "@/stores/auth-store"

export type WebPushStatus =
  | "UNSUPPORTED"
  | "AVAILABLE"
  | "DENIED"
  | "SUBSCRIBED"
  | "UNSUBSCRIBED"

export interface WebPushCapability {
  status: WebPushStatus
  permission: NotificationPermission | "unsupported"
  subscriptionId: string | null
  message?: string
}

interface WebPushPublicKey {
  public_key: string
}

interface WebPushSubscriptionResponse {
  id: string
  endpoint?: string
  device_label: string
  is_active: boolean
  created_at?: string
}

interface SerializedPushSubscription {
  endpoint?: string
  keys?: { p256dh?: string; auth?: string }
}

const WORKER_URL = "/service-worker.js"
const STORAGE_PREFIX = "skillmatch:web-push-subscription"

function storageKey(): string {
  return `${STORAGE_PREFIX}:${useAuthStore.getState().user?.id ?? "anonymous"}`
}

function storedSubscriptionId(): string | null {
  try {
    return localStorage.getItem(storageKey())
  } catch {
    return null
  }
}

function rememberSubscription(id: string | null): void {
  try {
    if (id) localStorage.setItem(storageKey(), id)
    else localStorage.removeItem(storageKey())
  } catch {
    // Private browsing/storage denial must not invalidate a valid push setup.
  }
}

function supported(): boolean {
  return (
    typeof Notification !== "undefined" &&
    typeof navigator !== "undefined" &&
    Boolean(navigator.serviceWorker)
  )
}

function base64UrlToBytes(value: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (value.length % 4)) % 4)
  const base64 = (value + padding).replace(/-/g, "+").replace(/_/g, "/")
  const decoded = atob(base64)
  const bytes = new Uint8Array(new ArrayBuffer(decoded.length))
  for (let index = 0; index < decoded.length; index += 1) {
    bytes[index] = decoded.charCodeAt(index)
  }
  return bytes
}

export async function getWebPushCapability(): Promise<WebPushCapability> {
  if (!supported()) {
    return {
      status: "UNSUPPORTED",
      permission: "unsupported",
      subscriptionId: null,
    }
  }
  const subscriptionId = storedSubscriptionId()
  if (Notification.permission === "denied") {
    return { status: "DENIED", permission: "denied", subscriptionId }
  }
  return {
    status:
      Notification.permission === "granted" && subscriptionId
        ? "SUBSCRIBED"
        : "AVAILABLE",
    permission: Notification.permission,
    subscriptionId,
  }
}

export async function requestWebPushSubscription(
  deviceLabel: string
): Promise<WebPushCapability> {
  if (!supported()) {
    return {
      status: "UNSUPPORTED",
      permission: "unsupported",
      subscriptionId: null,
    }
  }
  if (Notification.permission === "denied") {
    return { status: "DENIED", permission: "denied", subscriptionId: null }
  }

  const permission =
    Notification.permission === "granted"
      ? "granted"
      : await Notification.requestPermission()
  if (permission !== "granted") {
    return {
      status: permission === "denied" ? "DENIED" : "AVAILABLE",
      permission,
      subscriptionId: null,
    }
  }

  const registration = await navigator.serviceWorker.register(WORKER_URL, {
    scope: "/",
  })
  const publicKey = await apiClient.get<WebPushPublicKey>(
    "/notifications/push/public-key",
    { showToastOnError: true }
  )
  const previousSubscription = await registration.pushManager.getSubscription()
  if (previousSubscription && !storedSubscriptionId()) {
    await previousSubscription.unsubscribe()
  }
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: base64UrlToBytes(publicKey.data.public_key),
  })
  const serialized = subscription.toJSON() as SerializedPushSubscription
  if (
    !serialized.endpoint ||
    !serialized.keys?.p256dh ||
    !serialized.keys.auth
  ) {
    throw new Error("El navegador no devolvió una suscripción Web Push válida.")
  }
  const response = await apiClient.post<WebPushSubscriptionResponse>(
    "/notifications/push/subscriptions",
    {
      endpoint: serialized.endpoint,
      keys: {
        p256dh: serialized.keys.p256dh,
        auth: serialized.keys.auth,
      },
      device_label: (deviceLabel.trim() || "Navegador web").slice(0, 100),
    },
    { showToastOnError: true }
  )
  rememberSubscription(response.data.id)
  return {
    status: "SUBSCRIBED",
    permission: "granted",
    subscriptionId: response.data.id,
    message: response.message,
  }
}

export async function revokeWebPushSubscription(
  subscriptionId: string
): Promise<WebPushCapability> {
  const response = await apiClient.delete<null>(
    `/notifications/push/subscriptions/${subscriptionId}`,
    { showToastOnError: true }
  )
  if (supported()) {
    const registration = await navigator.serviceWorker.register(WORKER_URL, {
      scope: "/",
    })
    const subscription = await registration.pushManager.getSubscription()
    if (subscription) await subscription.unsubscribe()
  }
  rememberSubscription(null)
  return {
    status: "UNSUBSCRIBED",
    permission: supported() ? Notification.permission : "unsupported",
    subscriptionId: null,
    message: response.message,
  }
}
