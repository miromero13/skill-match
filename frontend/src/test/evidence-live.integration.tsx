import { readFileSync } from "node:fs"
import process from "node:process"
import { expect, it } from "vitest"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { EvidenceManager } from "@/components/skill-evidences/evidence-manager"
import { useAuthStore, type UserProfile } from "@/stores/auth-store"
import { getEvidences } from "@/services/skill-evidence-service"

const path = process.env.HU16_TEST_FIXTURE
if (!path)
  throw new Error(
    "Ejecuta doc-dev-ramiro/HU-16/scripts/verify_hu16_private.py para preparar las fixtures aisladas."
  )
const fixture = JSON.parse(readFileSync(path, "utf8")) as {
  skillId: string
  tokenA: string
  tokenB: string
  userA: UserProfile
  userB: UserProfile
}

it("performs private CRUD from React through the real API and PostgreSQL", async () => {
  const user = userEvent.setup()
  useAuthStore.getState().login(fixture.userA, fixture.tokenA)
  render(
    <EvidenceManager
      skill={{ id: fixture.skillId, skill_name: "Python integración" }}
    />
  )
  await user.click(screen.getByRole("button", { name: "Evidencias" }))
  await screen.findByText(/Todavía no hay evidencias/)
  await user.click(screen.getByRole("button", { name: "Agregar evidencia" }))
  await user.type(screen.getByLabelText("Título"), "Proyecto integrado")
  await user.type(
    screen.getByLabelText("URL del recurso"),
    "https://EXAMPLE.COM/integration"
  )
  await user.click(screen.getByRole("button", { name: "Guardar evidencia" }))
  expect(await screen.findByText("Proyecto integrado")).toBeInTheDocument()
  const created = await getEvidences(fixture.skillId)
  expect(created.count).toBe(1)
  expect(created.data[0].url).toBe("https://example.com/integration")
  await user.click(screen.getByRole("button", { name: "Agregar evidencia" }))
  await user.type(screen.getByLabelText("Título"), "Duplicado")
  await user.type(
    screen.getByLabelText("URL del recurso"),
    "https://example.com/integration"
  )
  await user.click(screen.getByRole("button", { name: "Guardar evidencia" }))
  expect(
    await screen.findByText("Ya registraste esta evidencia.")
  ).toBeInTheDocument()
  expect(screen.getByLabelText("Título")).toHaveValue("Duplicado")
  expect((await getEvidences(fixture.skillId)).count).toBe(1)
  await user.click(screen.getByRole("button", { name: "Volver a evidencias" }))
  await user.keyboard("{Escape}")
  await user.click(screen.getByRole("button", { name: "Evidencias" }))
  await user.click(
    await screen.findByRole("button", { name: "Editar Proyecto integrado" })
  )
  await user.clear(screen.getByLabelText("Título"))
  await user.type(screen.getByLabelText("Título"), "Proyecto actualizado")
  await user.click(screen.getByRole("button", { name: "Guardar evidencia" }))
  expect(await screen.findByText("Proyecto actualizado")).toBeInTheDocument()
  await user.keyboard("{Escape}")
  useAuthStore.getState().login(fixture.userB, fixture.tokenB)
  await expect(getEvidences(fixture.skillId)).rejects.toMatchObject({
    statuscode: 404,
    message: "Recurso no encontrado",
  })
  useAuthStore.getState().login(fixture.userA, fixture.tokenA)
  await user.click(screen.getByRole("button", { name: "Evidencias" }))
  await user.click(
    await screen.findByRole("button", { name: "Eliminar Proyecto actualizado" })
  )
  await user.click(
    within(screen.getByRole("alertdialog")).getByRole("button", {
      name: "Confirmar eliminación",
    })
  )
  await waitFor(async () =>
    expect((await getEvidences(fixture.skillId)).count).toBe(0)
  )
  expect(
    await screen.findByText(/Todavía no hay evidencias/)
  ).toBeInTheDocument()
  useAuthStore.getState().logout()
})
