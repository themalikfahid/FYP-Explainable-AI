import { useState } from "react";
import { NavLink, useLocation, useNavigate, useOutlet } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Activity, BarChart3, Calculator, ClipboardPlus, Cpu, History, LayoutDashboard, LogOut, Menu, Settings, ShieldCheck, X } from "lucide-react";
import { useAuth } from "../../lib/auth";
import { Brand } from "./Brand";
import { Button } from "../ui";

const NAV = [
  { section: "Workspace", items: [
    { to: "/app", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/app/assess", label: "New assessment", icon: ClipboardPlus },
    { to: "/app/history", label: "History", icon: History },
  ] },
  { section: "Insights", items: [
    { to: "/app/models", label: "Model transparency", icon: Cpu },
    { to: "/app/tools", label: "Health tools", icon: Calculator },
  ] },
  { section: "Account", items: [{ to: "/app/settings", label: "Settings", icon: Settings }] },
];

export default function AppShell() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const outlet = useOutlet(); // captured per render so exiting pages keep their own element (no remount/state loss)
  const [open, setOpen] = useState(false);
  const initials = (user?.full_name ?? "?").split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();

  return (
    <div className="shell">
      <aside className={`sidebar ${open ? "open" : ""}`} aria-label="Main navigation">
        <Brand to="/app" />
        {NAV.map((g) => (
          <div key={g.section}>
            <div className="nav-section">{g.section}</div>
            {g.items.map((i) => (
              <NavLink key={i.to} to={i.to} end={i.end} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`} onClick={() => setOpen(false)}>
                <i.icon size={18} aria-hidden />{i.label}
              </NavLink>
            ))}
          </div>
        ))}
        <div style={{ marginTop: "auto" }} className="card" >
          <div className="row" style={{ gap: 8, marginBottom: 6 }}><ShieldCheck size={16} color="#34d399" /><strong style={{ fontSize: 13 }}>Education only</strong></div>
          <p style={{ fontSize: 12.5, margin: 0 }}>Not a medical device and not a diagnosis. Always confirm with a clinician.</p>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="row">
            <Button variant="ghost" className="icon mobile-bar" aria-label={open ? "Close menu" : "Open menu"} onClick={() => setOpen((v) => !v)}>{open ? <X size={20} /> : <Menu size={20} />}</Button>
            <span className="row muted" style={{ gap: 8, fontSize: 13.5 }}><Activity size={15} color="#22d3ee" /> Models online</span>
          </div>
          <div className="row">
            <Button size="sm" variant="primary" to="/app/assess" icon={<BarChart3 size={15} />}>New assessment</Button>
            <div className="row" style={{ gap: 10 }}>
              <div aria-hidden style={{ width: 36, height: 36, borderRadius: 12, display: "grid", placeItems: "center", background: "var(--grad-soft)", border: "1px solid var(--line-strong)", fontWeight: 700, fontSize: 13 }}>{initials}</div>
              <div style={{ lineHeight: 1.2 }}><div style={{ fontWeight: 600, fontSize: 14 }}>{user?.full_name}</div><div className="faint" style={{ fontSize: 12 }}>{user?.email}</div></div>
              <Button variant="ghost" className="icon" aria-label="Sign out" onClick={async () => { await logout(); nav("/"); }}><LogOut size={18} /></Button>
            </div>
          </div>
        </header>
        <AnimatePresence mode="wait">
          <motion.main id="main" key={loc.pathname} className="page" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: .28 }}>
            {outlet}
          </motion.main>
        </AnimatePresence>
      </div>
    </div>
  );
}
