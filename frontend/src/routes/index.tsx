import { createBrowserRouter, Navigate } from "react-router-dom"
import { PublicLayout } from "@/layouts/public-layout"
import { PlatformLayout } from "@/layouts/platform-layout"
import { ExamLayout } from "@/layouts/exam-layout"
import { LandingPage } from "@/pages/landing-page"
import { FeedPage } from "@/pages/feed-page"
import { ExamPage } from "@/pages/exam-page"
import { NotFoundPage } from "@/pages/not-found-page"
import { AdminLoginPage } from "@/pages/admin-login-page"

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

  // 2. Platform Layout (Consumer Platform & Admin Backoffice)
  {
    path: "/app",
    element: <PlatformLayout />,
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

  // 5. Admin Direct Redirection (Protección preventiva)
  {
    path: "/admin",
    element: <Navigate to="/admin/login" replace />,
  },

  // 6. 404 Dedicated Not Found
  {
    path: "*",
    element: <NotFoundPage />,
  },
])
