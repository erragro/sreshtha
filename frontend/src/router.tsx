import { createBrowserRouter, Navigate } from "react-router-dom"

import { AppShell } from "@/components/AppShell"
import { AuthGuard } from "@/components/AuthGuard"
import { ModuleGuard } from "@/components/ModuleGuard"
import { AdminPage } from "@/pages/AdminPage"
import { ChatPage } from "@/pages/ChatPage"
import { ContractDetailPage } from "@/pages/ContractDetailPage"
import { ContractReaderPage } from "@/pages/ContractReaderPage"
import { ConversationStudioPage } from "@/pages/ConversationStudioPage"
import { HomePage } from "@/pages/HomePage"
import { IdiomsAdminPage } from "@/pages/IdiomsAdminPage"
import { LoginPage } from "@/pages/LoginPage"
import { RightsGuideDetailPage } from "@/pages/RightsGuideDetailPage"
import { RightsGuidePage } from "@/pages/RightsGuidePage"
import { SchemeDetailPage } from "@/pages/SchemeDetailPage"
import { SchemesFinderPage } from "@/pages/SchemesFinderPage"
import { SignupPage } from "@/pages/SignupPage"

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/signup", element: <SignupPage /> },

  {
    element: <AuthGuard />,
    children: [
      {
        element: <AppShell />,
        children: [
          // Home — no module check, every authenticated user gets here.
          { index: true, element: <HomePage /> },

          // Chatbot — inside the /chat namespace, requires 'chatbot'
          // module access (any level).
          {
            path: "chat",
            element: <ModuleGuard moduleKey="chatbot" />,
            children: [
              { index: true, element: <ChatPage /> },
              { path: ":sessionId", element: <ChatPage /> },
            ],
          },

          // Contract Reader — upload list + clause-by-clause viewer.
          //   /contracts             — upload zone + list
          //   /contracts/:contractId — full analysis (three-stage output)
          {
            path: "contracts",
            element: <ModuleGuard moduleKey="contract_reader" />,
            children: [
              { index: true, element: <ContractReaderPage /> },
              { path: ":contractId", element: <ContractDetailPage /> },
            ],
          },

          // Rights Guide — statute-cited fact cards.
          //   /rights            — card list, language switcher
          //   /rights/:topicKey  — full card with citation + actions
          {
            path: "rights",
            element: <ModuleGuard moduleKey="rights_guide" />,
            children: [
              { index: true, element: <RightsGuidePage /> },
              { path: ":topicKey", element: <RightsGuideDetailPage /> },
            ],
          },

          // Schemes Finder — 3-question wizard, matched welfare schemes.
          //   /schemes           — wizard + inline results
          //   /schemes/:key      — scheme detail with docs + apply link
          {
            path: "schemes",
            element: <ModuleGuard moduleKey="schemes_finder" />,
            children: [
              { index: true, element: <SchemesFinderPage /> },
              { path: ":key", element: <SchemeDetailPage /> },
            ],
          },

          // Admin — orthogonal to modules; gated by is_super_admin.
          // /admin is the users panel; /admin/conversation is the
          // Conversation Studio (chip-tap taxonomy + templates).
          {
            path: "admin",
            element: <ModuleGuard superAdminOnly />,
            children: [
              { index: true, element: <AdminPage /> },
              { path: "conversation", element: <ConversationStudioPage /> },
              { path: "idioms", element: <IdiomsAdminPage /> },
            ],
          },
        ],
      },
    ],
  },

  { path: "*", element: <Navigate to="/" replace /> },
])
