import "@fontsource/red-hat-display/500.css";
import "@fontsource/red-hat-display/700.css";
import "@fontsource/red-hat-display/800.css";
import "@fontsource/red-hat-text/400.css";
import "@fontsource/red-hat-text/500.css";
import "@fontsource/red-hat-text/600.css";
import "@fontsource/red-hat-mono/400.css";
import "@fontsource/red-hat-mono/500.css";
import "./styles.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useParams } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Loading } from "./components/ui";
import { AuthProvider, useAuth } from "./lib/auth";
import { ToastProvider } from "./lib/toast";
import { Account } from "./pages/Account";
import { Analyst } from "./pages/Analyst";
import { Assessment } from "./pages/Assessment";
import { Dashboards } from "./pages/Dashboards";
import { Engagements } from "./pages/Engagements";
import { EvidencePage } from "./pages/Evidence";
import { Framework } from "./pages/Framework";
import { Heatmap } from "./pages/Heatmap";
import { Interviews } from "./pages/Interviews";
import { Login } from "./pages/Login";
import { Overview } from "./pages/Overview";
import { Scope } from "./pages/Scope";
import { Users } from "./pages/Users";

const qc = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: true, staleTime: 10_000, retry: 1 } },
});

function EngagementRedirect() {
  const { eid } = useParams();
  return <Navigate to={`/e/${eid}/overview`} replace />;
}

function Root() {
  const { user, loading } = useAuth();
  if (loading) return <Loading what="Starting QE Compass…" />;
  if (!user) return <Login />;
  return (
    <Routes>
      <Route element={<Layout />}>
        {user.must_change_password ? (
          <Route path="*" element={<Account forced />} />
        ) : (
          <>
            <Route index element={<Engagements />} />
            <Route path="account" element={<Account />} />
            <Route path="admin/users" element={<Users />} />
            <Route path="e/:eid" element={<EngagementRedirect />} />
            <Route path="e/:eid/overview" element={<Overview />} />
            <Route path="e/:eid/interviews" element={<Interviews />} />
            <Route path="e/:eid/evidence" element={<EvidencePage />} />
            <Route path="e/:eid/assessment" element={<Assessment />} />
            <Route path="e/:eid/analyst" element={<Analyst />} />
            <Route path="e/:eid/heatmap" element={<Heatmap />} />
            <Route path="e/:eid/dashboards" element={<Dashboards />} />
            <Route path="e/:eid/scope" element={<Scope />} />
            <Route path="e/:eid/framework" element={<Framework />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </>
        )}
      </Route>
    </Routes>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <AuthProvider>
          <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            <Root />
          </BrowserRouter>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  </StrictMode>,
);
