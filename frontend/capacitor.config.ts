import type { CapacitorConfig } from "@capacitor/cli"

// CAP_ENV=production npx cap sync android -> release build: HTTPS WebView origin
// (https://localhost), no cleartext HTTP and no native logs. Default keeps the dev setup.
const isProduction = process.env.CAP_ENV === "production"

const config: CapacitorConfig = {
  appId: "com.skillmatch.app",
  appName: "SkillMatch",
  webDir: "dist",
  loggingBehavior: isProduction ? "none" : "debug",
  plugins: {
    SocialLogin: {
      providers: { google: true, facebook: false, apple: false, twitter: false, telegram: false, oauth2: false },
      logLevel: 1,
    },
    PushNotifications: {
      presentationOptions: ["badge", "sound", "alert", "banner", "list"],
    },
  },
  server: isProduction
    ? { androidScheme: "https" }
    : { androidScheme: "http", cleartext: true },
}

export default config
