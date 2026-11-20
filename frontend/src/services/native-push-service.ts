import { Capacitor } from '@capacitor/core'
import {
  PushNotifications,
  type Token,
  type ActionPerformed,
  type PushNotificationSchema,
} from '@capacitor/push-notifications'
import { toast } from 'sonner'
import { apiClient } from '@/services/api-client'
import { useAuthStore } from '@/stores/auth-store'

let isInitialized = false

/**
 * Registers the device FCM token with the SkillMatch backend.
 */
export async function syncDeviceTokenToBackend(token: string): Promise<void> {
  const user = useAuthStore.getState().user
  if (!user || user.role !== 'MEMBER') return

  try {
    await apiClient.post('/notifications/devices', {
      fcm_token: token,
      platform: Capacitor.getPlatform() || 'android',
      device_label: 'Infinix Android',
    })
    console.info('Token FCM registrado exitosamente en el backend.')
  } catch (error) {
    console.warn('No se pudo registrar el token FCM en el backend:', error)
  }
}

/**
 * Initializes Firebase Cloud Messaging native push notifications on Android & iOS.
 * Safely no-ops in web/browser environments.
 */
export async function initializeNativePushNotifications(
  onNotificationTap?: (action: ActionPerformed) => void
): Promise<void> {
  if (!Capacitor.isNativePlatform()) return
  if (isInitialized) return

  try {
    let permStatus = await PushNotifications.checkPermissions()
    if (permStatus.receive === 'prompt') {
      permStatus = await PushNotifications.requestPermissions()
    }

    if (permStatus.receive !== 'granted') {
      console.warn('Permisos de notificaciones push denegados en dispositivo móvil.')
      return
    }

    // Configurar canal de alta importancia en Android para banner flotante (heads-up) y sonido en primer plano
    if (Capacitor.getPlatform() === 'android') {
      try {
        await PushNotifications.createChannel({
          id: 'skillmatch_notifications',
          name: 'SkillMatch Notificaciones',
          description: 'Notificaciones prioritarias de intercambios, recargas y avisos',
          importance: 5,
          visibility: 1,
          vibration: true,
          sound: 'default',
        })
      } catch (channelError) {
        console.warn('No se pudo crear el canal de notificaciones en Android:', channelError)
      }
    }

    // Escuchar registro exitoso del token FCM
    await PushNotifications.addListener('registration', (token: Token) => {
      console.info('Token FCM obtenido exitosamente:', token.value)
      try {
        localStorage.setItem('skillmatch:fcm_token', token.value)
      } catch {
        // Ignorar fallo de almacenamiento
      }
      void syncDeviceTokenToBackend(token.value)
    })

    // Sincronizar token existente si ya fue generado
    try {
      const existingToken = localStorage.getItem('skillmatch:fcm_token')
      if (existingToken) {
        void syncDeviceTokenToBackend(existingToken)
      }
    } catch {
      // Ignorar fallo de lectura local
    }

    // Escuchar posibles errores de registro con Firebase
    await PushNotifications.addListener('registrationError', (error) => {
      console.error('Error al registrar notificaciones push con Firebase:', error)
    })

    // Escuchar notificaciones recibidas mientras la app está abierta en primer plano
    await PushNotifications.addListener(
      'pushNotificationReceived',
      (notification: PushNotificationSchema) => {
        toast.info(notification.title || 'Notificación de SkillMatch', {
          description: notification.body || '',
        })
      }
    )

    // Escuchar interacción al pulsar sobre una notificación
    await PushNotifications.addListener(
      'pushNotificationActionPerformed',
      (action: ActionPerformed) => {
        if (onNotificationTap) {
          onNotificationTap(action)
        }
      }
    )

    // Registrar el dispositivo en los servicios de Firebase Messaging
    await PushNotifications.register()
    isInitialized = true
  } catch (error) {
    console.error('Error al inicializar PushNotifications de Firebase:', error)
  }
}
