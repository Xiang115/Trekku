import Icon from "../icons/Icon";
import { useAuth } from "../state/AuthContext";

export default function AccountSection({ onOpenLogin }: { onOpenLogin: () => void }) {
  const { user } = useAuth();

  const scrollToItinerary = () =>
    document.querySelector("#itinerary")?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <section className="section-block account-block" id="account">
      <div className="section-heading">
        <div>
          <p className="panel-kicker">Authentication</p>
          <h2>Account access for saved trips</h2>
        </div>
        <button
          className="outline-button"
          type="button"
          onClick={user ? scrollToItinerary : onOpenLogin}
        >
          {user ? "View saved trips" : "Login to continue"}
        </button>
      </div>

      <div className="account-grid">
        <article className={`account-status-card${user ? " is-authenticated" : ""}`}>
          <span className="status-icon">
            <Icon name={user ? "user" : "lock"} />
          </span>
          <div>
            <h3>{user ? `Signed in as ${user.name}` : "Guest browsing mode"}</h3>
            <p>
              {user
                ? "My Trips, saved itineraries, and checkout are unlocked for this account."
                : "Explore and plan a trip first, then log in before saving itineraries or checking out."}
            </p>
          </div>
        </article>

        <article className="auth-step-card">
          <span>01</span>
          <h3>Create account</h3>
          <p>Email, password, and name are stored locally for this demo session.</p>
        </article>

        <article className="auth-step-card">
          <span>02</span>
          <h3>Login</h3>
          <p>Returning users pick up saved trips and previous AI itineraries.</p>
        </article>

        <article className="auth-step-card">
          <span>03</span>
          <h3>Secure dashboard</h3>
          <p>Authenticated sessions unlock My Trips, checkout, and profile settings.</p>
        </article>
      </div>
    </section>
  );
}
