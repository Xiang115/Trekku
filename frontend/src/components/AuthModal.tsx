import { useEffect, useRef, useState } from "react";
import Icon from "../icons/Icon";
import { deriveDisplayName, useAuth } from "../state/AuthContext";

type Mode = "login" | "signup";

export default function AuthModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { login } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const emailRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    const t = window.setTimeout(() => emailRef.current?.focus(), 0);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      window.clearTimeout(t);
    };
  }, [open, onClose]);

  if (!open) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const displayName =
      mode === "signup" ? deriveDisplayName(name || "Trekku User") : deriveDisplayName(email.split("@")[0]);
    login({ name: displayName, email, provider: mode === "signup" ? "email_signup" : "email_login" });
    onClose();
  };

  const handleGoogle = () => {
    login({ name: "Daniel Student", email: "daniel@trekku.demo", provider: "google_demo" });
    onClose();
  };

  return (
    <div className="auth-modal" role="dialog" aria-modal="true" aria-labelledby="authTitle">
      <div className="auth-backdrop" onClick={onClose} />
      <section className="auth-dialog">
        <button className="auth-close" type="button" aria-label="Close login dialog" onClick={onClose}>
          &times;
        </button>
        <div className="auth-visual-panel">
          <span className="status-icon">
            <Icon name="user" />
          </span>
          <h2 id="authTitle">{mode === "signup" ? "Join Trekku" : "Welcome back to Trekku"}</h2>
          <p>Save your trips, continue AI itineraries, and move smoothly into checkout.</p>
          <div className="auth-benefits">
            <span>
              <Icon name="check" /> Saved trips
            </span>
            <span>
              <Icon name="check" /> Continue AI itineraries
            </span>
            <span>
              <Icon name="check" /> Secure checkout handoff
            </span>
          </div>
        </div>

        <div className="auth-form-panel">
          <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
            <button
              className={mode === "login" ? "is-active" : ""}
              type="button"
              onClick={() => setMode("login")}
            >
              Login
            </button>
            <button
              className={mode === "signup" ? "is-active" : ""}
              type="button"
              onClick={() => setMode("signup")}
            >
              Sign up
            </button>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            {mode === "signup" && (
              <label>
                Full name
                <input
                  autoComplete="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Daniel Student"
                />
              </label>
            )}
            <label>
              Email address
              <input
                ref={emailRef}
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="daniel@trekku.demo"
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete={mode === "signup" ? "new-password" : "current-password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            {mode === "signup" && (
              <label>
                Travel style
                <select>
                  <option>Solo Explorer</option>
                  <option>Family Planner</option>
                  <option>Organization Admin</option>
                </select>
              </label>
            )}
            <div className="auth-options">
              <label>
                <input type="checkbox" defaultChecked />
                Remember me
              </label>
              <button type="button">Forgot password?</button>
            </div>
            <button className="auth-submit" type="submit">
              {mode === "signup" ? "Create account" : "Login to account"}
            </button>
            <button className="google-button" type="button" onClick={handleGoogle}>
              <Icon name="user" />
              Continue with Google
            </button>
            <p className="auth-message">
              Demo mode uses local session state — no backend authentication is required.
            </p>
          </form>
        </div>
      </section>
    </div>
  );
}
