import Icon from "../icons/Icon";
import { useAuth } from "../state/AuthContext";

export default function Topbar({ onOpenLogin }: { onOpenLogin: () => void }) {
  const { user, logout } = useAuth();

  const handleChip = () => {
    if (window.confirm("Sign out from this Trekku account?")) logout();
  };

  return (
    <header className="topbar">
      <a className="brand" href="#planner" aria-label="Trekku planner">
        <span className="brand-mark">T</span>
        <span>Trekku</span>
      </a>
      <nav className="main-nav" aria-label="Main navigation">
        <a href="#planner">Planner</a>
        <a href="#itinerary">Itinerary</a>
        <a href="#insights">Insights</a>
        <a href="#account">Account</a>
      </nav>
      <div className="auth-controls">
        {user ? (
          <button className="account-chip" type="button" onClick={handleChip}>
            <span>{user.name.slice(0, 1).toUpperCase()}</span>
            <strong>{user.name.split(" ")[0]}</strong>
          </button>
        ) : (
          <button className="login-button" type="button" onClick={onOpenLogin}>
            <Icon name="lock" />
            Login
          </button>
        )}
      </div>
    </header>
  );
}
