import { createBrowserRouter, Navigate } from "react-router-dom"
import { PublicLayout } from "@/layouts/public-layout"
import { PlatformLayout } from "@/layouts/platform-layout"
import { ExamLayout } from "@/layouts/exam-layout"
import { LandingPage } from "@/pages/landing-page"
import { FeedPage } from "@/pages/feed-page"
import { ExamPage } from "@/pages/exam-page"
import { NotFoundPage } from "@/pages/not-found-page"
import { MemberLoginPage } from "@/pages/member-login-page"
import { AdminLoginPage } from "@/pages/admin-login-page"
import { AdminDashboardPage } from "@/pages/admin-dashboard-page"
import { AdminUsersPage } from "@/pages/admin-users-page"
import { AdminCatalogPage } from "@/pages/admin-catalog-page"
import { TheoryBankPage } from "@/pages/theory-bank-page"
import { LearningSkillsPage } from "@/pages/learning-skills-page"
import { AdminLayout } from "@/layouts/admin-layout"
import { AdminRouteGuard } from "@/components/admin-route-guard"
import { MemberRouteGuard } from "@/components/member-route-guard"
import { TeachingSkillsPage } from "@/pages/teaching-skills-page"
import { EvaluationSetupPage } from "@/pages/evaluation-setup-page"
import { BrowserSupervisionPage } from "@/pages/browser-supervision-page"
import { ProfilePage } from "@/pages/profile-page"
import { AdminDatasetCapturePage } from "@/pages/admin-dataset-capture-page"
import { FootballValidationWizard } from "@/features/football-validation"
import { AvailabilityPage } from "@/pages/availability-page"
import { MatchesPage } from "@/pages/matches-page"
import { SearchPage } from "@/pages/search-page"
import { ComingSoonPage } from "@/pages/coming-soon-page"

import { NotificationLayout } from "@/components/notifications/notification-layout"
import { NotificationInboxPage } from "@/pages/notifications/notification-inbox-page"
import { NotificationSettingsPage } from "@/pages/notifications/notification-settings-page"
import { PrivacySettingsPage } from "@/pages/settings/privacy-settings-page"

export const router = createBrowserRouter([
  {
    path: "/evaluation/:skillId/setup",
    element: <MemberRouteGuard><PlatformLayout /></MemberRouteGuard>,
    children: [{ index: true, element: <EvaluationSetupPage /> }],
  },
  {
    path: "/settings/privacy",
    element: (
      <MemberRouteGuard>
        <PlatformLayout />
      </MemberRouteGuard>
    ),
    children: [{ index: true, element: <PrivacySettingsPage /> }],
  },
  {
    path: "/matches",
    element: (
      <MemberRouteGuard>
        <PlatformLayout />
      </MemberRouteGuard>
    ),
    children: [{ index: true, element: <MatchesPage /> }],
  },
  // 1. Public Layout (Landing Page, Institucional)
  {
    path: "/",
    element: <PublicLayout />,
    children: [
      {
        index: true,
        element: <LandingPage />,
      },
    ],
  },

  { path: "/notifications",
    element: <NotificationLayout />,
    children: [
      { index: true, element: <NotificationInboxPage /> },
      { path: "settings", element: <NotificationSettingsPage /> },
    ],
  },
  { path: "/search", element: <Navigate to="/app/search" replace /> },
  { path: "/app/notifications", element: <Navigate to="/notifications" replace /> },
  { path: "/app/notifications/settings", element: <Navigate to="/notifications/settings" replace /> },

  // 2. Member Authentication (HU-07 / Vista 28 Web / Vista 30 Mobile)
  {
    path: "/login",
    element: <MemberLoginPage />,
  },

  // 3. Platform Layout (Consumer Platform de Miembros protegida por MemberRouteGuard)
  {
    path: "/app",
    element: (
      <MemberRouteGuard>
        <PlatformLayout />
      </MemberRouteGuard>
    ),
    children: [

      {
        index: true,
        element: <FeedPage />,
      },
      {
        path: "search",
        element: <SearchPage />,
      },
      {
        path: "swaps",
        element: (
          <ComingSoonPage
            featureKey="swaps"
            title="Mis Intercambios"
            subtitle="Gestión de trueques activos y finalizados"
            description="Aquí podrás visualizar el estado de tus propuestas de intercambio aceptadas, gestionar salas de clase y confirmar finalizaciones."
          />
        ),
      },
      {
        path: "profile",
        element: <ProfilePage />,
      },
      {
        path: "learning-skills",
        element: <LearningSkillsPage />, // HU-15 / Vista 09: Habilidades que deseo aprender
      },
      {
        path: "teaching-skills",
        element: <TeachingSkillsPage />,
      },
      {
        path: "browser-supervision-test",
        element: <BrowserSupervisionPage />,
      },
      {
        path: "football-validation",
        element: (
          <div className="p-4 sm:p-6 max-w-6xl mx-auto">
            <FootballValidationWizard />
          </div>
        ),
      },
      {
        path: "wallet",
        element: (
          <ComingSoonPage
            featureKey="wallet"
            title="Billetera de SkillPoints"
            subtitle="Historial de movimientos, canjes y transferencias"
            description="Tu saldo actual está sincronizado con el backend. La visualización de transacciones históricas y canje de puntos estará disponible próximamente."
          />
        ),
      },
      {
        path: "availability",
        element: <AvailabilityPage />,
      },
      {
        path: "certificates",
        element: (
          <ComingSoonPage
            featureKey="certificates"
            title="Certificados de IA"
            subtitle="Sellos criptográficos y acreditaciones verificadas"
            description="Próximamente podrás emitir, visualizar y exportar tus certificados de aprobación de habilidades avalados por los motores de evaluación de SkillMatch."
          />
        ),
      },
      {
        path: "reputation",
        element: (
          <ComingSoonPage
            featureKey="reputation"
            title="Reputación y Reseñas"
            subtitle="Calificaciones pedagógicas y comentarios"
            description="Próximamente se habilitará el muro de valoraciones comunitarias y propinas recibidas tras completar sesiones de trueque."
          />
        ),
      },
      {
        path: "complaints",
        element: (
          <ComingSoonPage
            featureKey="complaints"
            title="Centro de Quejas y Mediación"
            subtitle="Resolución de disputas e incumplimientos"
            description="Próximamente podrás abrir quejas formales de trueques incumplidos y solicitar mediación o compensación arbitral de SkillPoints."
          />
        ),
      },
      {
        path: "settings/privacy",
        element: <PrivacySettingsPage />,
      },
    ],
  },

  // 3. Exam Layout (Full-Screen Distraction-Free Sandbox & Oral Exam)
  {
    path: "/app/exam-demo",
    element: <ExamLayout />,
    children: [
      {
        index: true,
        element: <ExamPage />,
      },
    ],
  },

  // 4. Admin Dedicated Login (HU-08 - Vista 29 & 31)
  {
    path: "/admin/login",
    element: <AdminLoginPage />,
  },

  // 5. Admin Dashboard (Protegido por AdminRouteGuard con política de ofuscación 404)
  {
    path: "/admin/dashboard",
    element: (
      <AdminRouteGuard>
        <AdminLayout />
      </AdminRouteGuard>
    ),
    children: [
      {
        index: true,
        element: <AdminDashboardPage />,
      },
    ],
  },

  // 6. Admin Backoffice - Gestión de Usuarios y Administradores (HU-10 - Vistas 15A, 15B, 17A, 17B)
  {
    path: "/admin/administrators",
    element: (
      <AdminRouteGuard>
        <AdminLayout />
      </AdminRouteGuard>
    ),
    children: [
      {
        index: true,
        element: <AdminUsersPage />,
      },
    ],
  },

  {
    path: "/admin/theory/questions",
    element: <AdminRouteGuard><AdminLayout /></AdminRouteGuard>,
    children: [{ index: true, element: <TheoryBankPage /> }],
  },

  // 6.1 Admin Backoffice - Catálogo de Habilidades (HU-12)
  {
    path: "/admin/catalog",
    element: (
      <AdminRouteGuard>
        <AdminLayout />
      </AdminRouteGuard>
    ),
    children: [
      {
        index: true,
        element: <AdminCatalogPage />,
      },
    ],
  },

  // 6.2 Alias /admin/skills -> /admin/catalog
  {
    path: "/admin/skills",
    element: <Navigate to="/admin/catalog" replace />,
  },

  // 6.3 Admin Backoffice - Captura de Datasets de IA (HU-17 / RF-IA-18)
  {
    path: "/admin/capture",
    element: (
      <AdminRouteGuard>
        <AdminLayout />
      </AdminRouteGuard>
    ),
    children: [
      {
        index: true,
        element: <AdminDatasetCapturePage />,
      },
    ],
  },
  {
    path: "/admin/ai-datasets",
    element: <Navigate to="/admin/capture" replace />,
  },

  // 6.4 Admin Backoffice - Auditoría de Fraude (Próximamente)
  {
    path: "/admin/fraud-audit",
    element: (
      <AdminRouteGuard>
        <AdminLayout />
      </AdminRouteGuard>
    ),
    children: [
      {
        index: true,
        element: (
          <ComingSoonPage
            featureKey="complaints"
            title="Auditoría de Fraude y Telemetría"
            subtitle="Inspección de evaluaciones, liveness y análisis de similitud"
            description="Este módulo de supervisión para administradores permitirá auditar alertas de integridad biométrica en tiempo real y dictaminar incidentes de suplantación."
          />
        ),
      },
    ],
  },

  // 6.5 Admin Backoffice - Disputas & Quejas (Próximamente)
  {
    path: "/admin/disputes",
    element: (
      <AdminRouteGuard>
        <AdminLayout />
      </AdminRouteGuard>
    ),
    children: [
      {
        index: true,
        element: (
          <ComingSoonPage
            featureKey="complaints"
            title="Disputas & Mediación Comunitaria"
            subtitle="Arbitraje de trueques incumplidos y compensación de SkillPoints"
            description="Este módulo permitirá al equipo administrador mediar en quejas reportadas por miembros, evaluar grabaciones y ordenar restituciones de saldo de puntos."
          />
        ),
      },
    ],
  },

  // 6. Admin Direct Redirection (Protección preventiva)
  {
    path: "/admin",
    element: <Navigate to="/admin/login" replace />,
  },

  // 7. 404 Dedicated Not Found
  {
    path: "*",
    element: <NotFoundPage />,
  },
])
