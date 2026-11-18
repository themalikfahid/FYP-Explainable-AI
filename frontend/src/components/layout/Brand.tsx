import { Link } from "react-router-dom";

export function LogoMark({ size = 38 }: { size?: number }) {
  return (
    <span className="logo-mark" style={{ width: size, height: size }} aria-hidden>
      <svg width={size * 0.58} height={size * 0.58} viewBox="0 0 24 24" fill="none" stroke="#04101c" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 21C5 16.5 3 11.5 5.2 8.2 7 5.6 10.4 6 12 8.6c1.6-2.6 5-3 6.8-.4C21 11.5 19 16.5 12 21z" fill="#04101c" fillOpacity=".15" />
        <path d="M3 12.5h4.5l2-3.8 3 7 2-3.2H21" />
      </svg>
    </span>
  );
}
export function Brand({ to = "/" }: { to?: string }) {
  return (
    <Link to={to} className="brand" aria-label="Clarity Screen home">
      <LogoMark />
      <span>Clarity Screen<small>Explainable AI screening</small></span>
    </Link>
  );
}
