import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import Landing from "./pages/Landing";
import { Login, Register } from "./pages/AuthPages";
import Dashboard from "./pages/Dashboard";
import Assess from "./pages/Assess";
import ResultPage from "./pages/ResultPage";
import History from "./pages/History";
import Tools from "./pages/Tools";
import ModelInfo from "./pages/ModelInfo";
import Settings from "./pages/Settings";

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <p className="loading" role="status">Loading your account…</p>;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/tools" element={<Tools />} />
        <Route path="/models" element={<ModelInfo />} />
        <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
        <Route path="/assess/:task" element={<Protected><Assess /></Protected>} />
        <Route path="/history" element={<Protected><History /></Protected>} />
        <Route path="/history/:id" element={<Protected><ResultPage /></Protected>} />
        <Route path="/settings" element={<Protected><Settings /></Protected>} />
        <Route path="*" element={<div className="page"><h1>Page not found</h1><p>Check the address, or go back to the <a href="/">home page</a>.</p></div>} />
      </Routes>
    </Layout>
  );
}
