import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import { AuthProvider, useAuth } from "./auth";
import { AppShell } from "./components/AppShell";
import { ToastProvider } from "./components/Toast";
import { setTimeZone } from "./format";
import { AuditPage } from "./pages/AuditPage";
import { DocumentPage } from "./pages/DocumentPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { LoginPage } from "./pages/LoginPage";
import { PeoplePage } from "./pages/PeoplePage";
import { PersonPage } from "./pages/PersonPage";
import { PublicScanPage } from "./pages/PublicScanPage";
import { SettingsPage } from "./pages/SettingsPage";
import { UploadPage } from "./pages/UploadPage";
import "./styles.css";
import { applyTheme } from "./theme";

applyTheme();

function App() {
  const { user, loading } = useAuth();
  const [settingsReady, setSettingsReady] = useState(false);

  useEffect(() => {
    if (!user) return;
    api
      .settings()
      .then((settings) => setTimeZone(settings.timezone))
      .catch(() => undefined)
      .finally(() => setSettingsReady(true));
  }, [user]);

  if (loading || (user && !settingsReady)) return <div className="spinner spinner-page" />;
  if (!user) return <LoginPage />;
  return (
    <AppShell>
      <Routes>
        <Route path="/pessoas" element={<PeoplePage />} />
        <Route path="/pessoas/:id" element={<PersonPage />} />
        <Route path="/documentos" element={<DocumentsPage />} />
        <Route path="/documentos/:id" element={<DocumentPage />} />
        <Route path="/novo" element={<UploadPage />} />
        <Route path="/auditoria" element={<AuditPage />} />
        <Route path="/configuracoes" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/pessoas" replace />} />
      </Routes>
    </AppShell>
  );
}

function Root() {
  const location = useLocation();
  if (location.pathname.startsWith("/enviar/")) {
    return (
      <Routes>
        <Route path="/enviar/:token" element={<PublicScanPage />} />
      </Routes>
    );
  }
  return (
    <AuthProvider>
      <App />
    </AuthProvider>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <Root />
      </ToastProvider>
    </BrowserRouter>
  </StrictMode>,
);
