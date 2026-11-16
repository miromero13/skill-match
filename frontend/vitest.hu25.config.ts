import { mergeConfig } from "vitest/config"
import config from "./vitest.config.ts"

export default mergeConfig(config, {
  test: {
    include: ["src/test/notification-live.integration.tsx"],
    testTimeout: 30000,
  },
})
