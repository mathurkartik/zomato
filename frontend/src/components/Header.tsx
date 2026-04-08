import type { HealthResponse } from '@/lib/api';

interface HeaderProps {
  health: HealthResponse | null;
}

export default function Header({ health }: HeaderProps) {
  const isOk = health?.status === 'ok';
  const label = health == null
    ? 'Connecting…'
    : isOk
      ? `${(health.catalog_rows || 0).toLocaleString()} restaurants`
      : 'Server degraded';

  return (
    <header className="site-header">
      <div className="header-inner">
        {/* Logo */}
        <div className="logo-group">
          <span className="logo-brand">
            <span className="logo-red">zomato</span>
            <span className="logo-black"> AI</span>
          </span>
        </div>

        {/* Nav */}
        <nav className="header-nav" aria-label="Main navigation">
          <a href="#" className="nav-link active" id="nav-home">Home</a>
          <a href="#" className="nav-link" id="nav-dining">Dining Out</a>
          <a href="#" className="nav-link" id="nav-delivery">Delivery</a>
          <a href="#" className="nav-link" id="nav-profile">Profile</a>
        </nav>

        {/* Health badge */}
        <div
          id="health-badge"
          className={`health-badge ${health == null ? '' : isOk ? 'ok' : 'bad'}`}
          aria-label={`Backend status: ${label}`}
        >
          <span className="health-dot" />
          <span className="health-label">{label}</span>
        </div>
      </div>
    </header>
  );
}
