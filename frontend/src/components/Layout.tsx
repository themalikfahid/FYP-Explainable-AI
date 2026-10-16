import { useState, type ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  async function doLogout() {
    await logout();
    close();
    nav("/login", { state: { message: "You have been logged out." } });
  }

  return (
    <div className="shell">
      <a className="skip" href="#main">Skip to content</a>
      <header className="topbar">
        <Link to={user ? "/dashboard" : "/"} className="brand" onClick={close}>
          <svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="7" /><path d="M6 17h6l2-6 4 12 2-6h6" /></svg>
          <span>Clarity Screen</span>
        </Link>
        <button className="menu-btn" aria-expanded={open} aria-controls="mainnav" onClick={() => setOpen(!open)}>
          {open ? "Close" : "Menu"}
        </button>
        <nav id="mainnav" className={open ? "nav open" : "nav"} aria-label="Main">
          {user ? (
            <>
              <NavLink to="/dashboard" onClick={close}>Dashboard</NavLink>
              <NavLink to="/assess/diabetes" onClick={close}>Diabetes screen</NavLink>
              <NavLink to="/assess/heart" onClick={close}>Heart screen</NavLink>
              <NavLink to="/history" onClick={close} end={false}>History</NavLink>
              <NavLink to="/tools" onClick={close}>BMI &amp; lifestyle</NavLink>
              <NavLink to="/models" onClick={close}>How the models work</NavLink>
              <NavLink to="/settings" onClick={close}>Account</NavLink>
              <button className="link-btn" onClick={doLogout}>Log out</button>
            </>
          ) : (
            <>
              <NavLink to="/tools" onClick={close}>BMI &amp; lifestyle</NavLink>
              <NavLink to="/models" onClick={close}>How the models work</NavLink>
              <NavLink to="/login" onClick={close}>Log in</NavLink>
              <NavLink to="/register" className="nav-cta" onClick={close}>Create account</NavLink>
            </>
          )}
        </nav>
      </header>
      <main id="main" tabIndex={-1}>{children}</main>
      <footer className="footer">
        <p>
          Final Year Project prototype: <em>Explainable AI-based hybrid model for diabetes screening and multiclass heart
          disease classification</em>. For education and decision support only. It does not diagnose and does not
          replace a health professional.
        </p>
      </footer>
    </div>
  );
}
