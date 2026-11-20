import type { CapacitorConfig } from "@capacitor/cli"

const config: CapacitorConfig = {
  appId: "com.skillmatch.app",
  appName: "SkillMatch",
  webDir: "dist",
  loggingBehavior: "debug",
  plugins: {
    SocialLogin: {
      providers: { google: true, facebook: false, apple: false, twitter: false, telegram: false, oauth2: false },
      logLevel: 1,
    },
    PushNotifications: {
      presentationOptions: ["badge", "sound", "alert", "banner", "list"],
    },
  },
  server: {
    androidScheme: "http",
    cleartext: true,
  },
}

export default config
