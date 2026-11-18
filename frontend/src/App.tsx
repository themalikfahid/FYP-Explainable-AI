import { Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./lib/auth";
import AppShell from "./components/layout/AppShell";
import { Spinner } from "./components/ui";
import Landing from "./pages/Landing";
import { Login, Register } from "./pages/AuthPages";
import Dashboard from "./pages/Dashboard";
import Assess from "./pages/Assess";
import AssessForm from "./pages/AssessForm";
import T1DAssess from "./pages/T1DAssess";
import ECGAssess from "./pages/ECGAssess";
import ResultPage from "./pages/ResultPage";
import History from "./pages/History";
import Models from "./pages/Models";
import Tools from "./pages/Tools";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";

function Protected({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <div style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}><Spinner /></div>;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  return children;
}

export default function App() {
  return (
    <>
      <a className="skip-link" href="#main">Skip to content</a>
      <div className="bg-grid" aria-hidden />
      <Suspense fallback={<div style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}><Spinner /></div>}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/app" element={<Protected><AppShell /></Protected>}>
            <Route index element={<Dashboard />} />
            <Route path="assess" element={<Assess />} />
            <Route path="assess/t1d" element={<T1DAssess />} />
            <Route path="assess/ecg" element={<ECGAssess />} />
            <Route path="assess/:task" element={<AssessForm />} />
            <Route path="result/:id" element={<ResultPage />} />
            <Route path="history" element={<History />} />
            <Route path="models" element={<Models />} />
            <Route path="tools" element={<Tools />} />
            <Route path="settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </>
  );
}
