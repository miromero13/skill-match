import "@testing-library/jest-dom/vitest"
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { Capacitor } from "@capacitor/core"
import { getNativeGoogleCredential } from "@/services/native-google-service"
import { MemberLoginPage } from "./member-login-page"
import { loginWithGoogle } from "@/services/auth-service"

vi.mock("@capacitor/core", () => ({ Capacitor: { isNativePlatform: vi.fn(() => false) } }))
vi.mock("@/services/native-google-service", () => ({ nativeGoogleConfigured: () => true, getNativeGoogleCredential: vi.fn(async () => "native-token") }))
beforeEach(() => { vi.clearAllMocks(); vi.mocked(Capacitor.isNativePlatform).mockReturnValue(false) })
vi.mock("@/services/auth-service", () => ({ loginWithGoogle: vi.fn() }))
afterEach(() => { cleanup(); vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

it("offers Google only without fictional providers or an unsigned development login", () => {
  vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "")
  render(<MemoryRouter><MemberLoginPage /></MemoryRouter>)
  expect(screen.queryAllByText(/GitHub|WhatsApp|OTP|Carlos Méndez|modo desarrollo/i)).toHaveLength(0)
  expect(screen.getByRole("alert")).toHaveTextContent("El acceso con Google no está configurado.")
  expect(screen.queryByRole("button")).not.toBeInTheDocument()
  expect(loginWithGoogle).not.toHaveBeenCalled()
})


it("renders the real Google control within a narrow mobile card", async () => {
  vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "client.apps.googleusercontent.com")
  vi.spyOn(Element.prototype, "clientWidth", "get").mockReturnValue(240)
  const renderButton = vi.fn()
  vi.stubGlobal("google", { accounts: { id: { initialize: vi.fn(), renderButton } } })
  render(<MemoryRouter><MemberLoginPage /></MemoryRouter>)
  await vi.waitFor(() => expect(renderButton).toHaveBeenCalled())
  const [container, options] = renderButton.mock.calls[0]
  expect(container).toHaveClass("w-full", "max-w-[360px]", "justify-center")
  expect(container.parentElement).toHaveClass("justify-center")
  expect(options.width).toBeLessThanOrEqual(240)
  expect(container.closest(".hidden")).toBeNull()
  expect(screen.getByText(/tu cuenta se crea automáticamente/i)).toBeInTheDocument()
})


it("uses the native Google SDK, then still verifies the credential with the backend", async () => {
  vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "client.apps.googleusercontent.com")
  vi.mocked(Capacitor.isNativePlatform).mockReturnValue(true)
  render(<MemoryRouter><MemberLoginPage /></MemoryRouter>)
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "Continuar con Google" })))
  expect(getNativeGoogleCredential).toHaveBeenCalledOnce()
  expect(loginWithGoogle).toHaveBeenCalledWith("native-token")
})
