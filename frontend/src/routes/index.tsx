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
import { AdminLayout } from "@/layouts/admin-layout"
import { AdminRouteGuard } from "@/components/admin-route-guard"
import { MemberRouteGuard } from "@/components/member-route-guard"
import { TeachingSkillsPage } from "@/pages/teaching-skills-page"

export const router = createBrowserRouter([
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
        element: <FeedPage />, // Placeholder para Vista 02
      },
      {
        path: "swaps",
        element: <FeedPage />, // Placeholder para Vista 20
      },
      {
        path: "notifications",
        element: <FeedPage />, // Placeholder para Vista 25
      },
      {
        path: "profile",
        element: <FeedPage />, // Placeholder para Vista 09 / 10
      },
      {
        path: "teaching-skills",
        element: <TeachingSkillsPage />,
      },
      {
        path: "wallet",
        element: <FeedPage />, // Placeholder para Vista 13A
      },
      {
        path: "availability",
        element: <FeedPage />, // Placeholder para Vista 21
      },
      {
        path: "certificates",
        element: <FeedPage />, // Placeholder para Vista 22
      },
      {
        path: "reputation",
        element: <FeedPage />, // Placeholder para Vista 23
      },
      {
        path: "complaints",
        element: <FeedPage />, // Placeholder para Vista 24A
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
        <AdminDashboardPage />
      </AdminRouteGuard>
    ),
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
