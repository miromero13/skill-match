import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { BrowserRouter } from "react-router-dom"
import { ReportBlockDialog } from "@/components/moderation/report-block-dialog"
import { BlockedProfileBanner } from "@/components/moderation/blocked-profile-banner"
import { PrivacySettingsPage } from "@/pages/settings/privacy-settings-page"
import { useUserModerationStore } from "@/stores/user-moderation-store"
import { userModerationService } from "@/services/user-moderation-service"

vi.mock("@/services/user-moderation-service", () => ({
    userModerationService: {
        getBlockedUsers: vi.fn(),
        blockUser: vi.fn(),
        unblockUser: vi.fn(),
        reportUser: vi.fn(),
        getSafetyStatus: vi.fn(),
    },
}))

describe("User Moderation & Blocking UI (HU-26 / RF-MAT-14, RF-NOT-06)", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        useUserModerationStore.setState({
            blockedUsers: [],
            count: 0,
            loading: false,
            error: null,
            safetyCache: {},
        })
    })

    describe("ReportBlockDialog (Vistas 26 y 28)", () => {
        it("renders modal header with user name and default infraction reason", () => {
            render(
                <ReportBlockDialog
                    targetUserId="user-123"
                    targetUserName="Martín Gómez"
                    open={true}
                    onOpenChange={vi.fn()}
                />
            )

            expect(screen.getByTestId("report-block-dialog")).toBeDefined()
            expect(screen.getByText(/Bloquear y Reportar a Martín Gómez/i)).toBeDefined()
            expect(screen.getByText(/Conducta, lenguaje ofensivo o acoso/i)).toBeDefined()
            expect(screen.getByText(/Protección Automática:/i)).toBeDefined()
        })

        it("disables confirmation button until minimum 10 characters are entered in description", () => {
            render(
                <ReportBlockDialog
                    targetUserId="user-123"
                    targetUserName="Martín Gómez"
                    open={true}
                    onOpenChange={vi.fn()}
                />
            )

            const submitBtn = screen.getByTestId("confirm-report-block-btn") as HTMLButtonElement
            expect(submitBtn.disabled).toBe(true)

            const textarea = screen.getByTestId("report-description-input")
            fireEvent.change(textarea, { target: { value: "Muy corto" } })
            expect(submitBtn.disabled).toBe(true)

            fireEvent.change(textarea, {
                target: { value: "El usuario utilizó lenguaje ofensivo en el chat." },
            })
            expect(submitBtn.disabled).toBe(false)
        })

        it("submits report with selected infraction reason and automatic blocking", async () => {
            const mockReport = vi.mocked(userModerationService.reportUser).mockResolvedValueOnce({
                statuscode: 201,
                message: "Reporte enviado exitosamente.",
                data: {
                    report_id: "rep-1",
                    reported_id: "user-123",
                    reported_name: "Martín Gómez",
                    reason: "PAYMENT_OUTSIDE",
                    status: "PENDING",
                    created_at: new Date().toISOString(),
                    user_blocked: true,
                },
            })

            const onOpenChange = vi.fn()
            render(
                <ReportBlockDialog
                    targetUserId="user-123"
                    targetUserName="Martín Gómez"
                    open={true}
                    onOpenChange={onOpenChange}
                />
            )

            // Seleccionar infracción de pago externo
            const paymentOption = screen.getByTestId("reason-option-PAYMENT_OUTSIDE")
            fireEvent.click(paymentOption)

            // Ingresar descripción válida
            const textarea = screen.getByTestId("report-description-input")
            fireEvent.change(textarea, {
                target: { value: "Me pidió dinero por fuera de SkillMatch en lugar de trueque." },
            })

            const submitBtn = screen.getByTestId("confirm-report-block-btn")
            fireEvent.click(submitBtn)

            await waitFor(() => {
                expect(mockReport).toHaveBeenCalledWith("user-123", {
                    reason: "PAYMENT_OUTSIDE",
                    description: "Me pidió dinero por fuera de SkillMatch en lugar de trueque.",
                    block_user: true,
                })
            })
        })
    })

    describe("BlockedProfileBanner (Vistas 27 y 29)", () => {
        it("renders the blocked user banner with date and unblock button", () => {
            render(
                <BlockedProfileBanner
                    userId="user-456"
                    userName="Martín Gómez"
                    blockedAt="2026-05-22T10:00:00Z"
                />
            )

            expect(screen.getByTestId("blocked-profile-banner")).toBeDefined()
            expect(screen.getByText(/USUARIO BLOQUEADO/i)).toBeDefined()
            expect(screen.getByText(/Bloqueaste a este usuario el/i)).toBeDefined()
            expect(screen.getByTestId("unblock-user-btn")).toBeDefined()
        })

        it("triggers unblock action when clicking unblock button", async () => {
            const mockUnblock = vi.mocked(userModerationService.unblockUser).mockResolvedValueOnce({
                statuscode: 200,
                message: "Usuario desbloqueado.",
                data: null,
            })

            const onUnblocked = vi.fn()
            render(
                <BlockedProfileBanner
                    userId="user-456"
                    userName="Martín Gómez"
                    onUnblocked={onUnblocked}
                />
            )

            const unblockBtn = screen.getByTestId("unblock-user-btn")
            fireEvent.click(unblockBtn)

            await waitFor(() => {
                expect(mockUnblock).toHaveBeenCalledWith("user-456")
                expect(onUnblocked).toHaveBeenCalled()
            })
        })
    })

    describe("PrivacySettingsPage (/settings/privacy)", () => {
        it("displays empty state when there are no blocked users", async () => {
            vi.mocked(userModerationService.getBlockedUsers).mockResolvedValueOnce({
                statuscode: 200,
                message: "Sin bloqueos",
                data: [],
                count: 0,
            })

            render(
                <BrowserRouter>
                    <PrivacySettingsPage />
                </BrowserRouter>
            )

            await waitFor(() => {
                expect(screen.getByTestId("empty-blocked-users")).toBeDefined()
                expect(screen.getByText(/No tienes usuarios bloqueados actualmente/i)).toBeDefined()
            })
        })

        it("displays list of blocked users and allows unblocking from the page", async () => {
            vi.mocked(userModerationService.getBlockedUsers).mockResolvedValueOnce({
                statuscode: 200,
                message: "Bloqueados",
                data: [
                    {
                        block_id: "blk-1",
                        user_id: "usr-david",
                        full_name: "David Infractor",
                        avatar_url: null,
                        reason: "HARASSMENT",
                        blocked_at: "2026-11-10T12:00:00Z",
                    },
                ],
                count: 1,
            })

            vi.mocked(userModerationService.unblockUser).mockResolvedValueOnce({
                statuscode: 200,
                message: "Desbloqueado",
                data: null,
            })

            render(
                <BrowserRouter>
                    <PrivacySettingsPage />
                </BrowserRouter>
            )

            await waitFor(() => {
                expect(screen.getByText("David Infractor")).toBeDefined()
                expect(screen.getByText(/Conducta, lenguaje ofensivo o acoso/i)).toBeDefined()
            })

            const unblockBtn = screen.getByTestId("unblock-btn-usr-david")
            fireEvent.click(unblockBtn)

            await waitFor(() => {
                expect(userModerationService.unblockUser).toHaveBeenCalledWith("usr-david")
            })
        })
    })
})
