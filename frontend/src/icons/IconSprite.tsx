/**
 * Inline SVG sprite ported verbatim from the original prototype's index.html.
 * Rendered once near the root so every <Icon> / <use href="#icon-…"> resolves.
 */
export default function IconSprite() {
  return (
    <svg className="icon-sprite" aria-hidden="true">
      <symbol id="icon-search" viewBox="0 0 24 24">
        <circle cx="11" cy="11" r="7"></circle>
        <path d="m20 20-3.2-3.2"></path>
      </symbol>
      <symbol id="icon-plane" viewBox="0 0 24 24">
        <path d="M3 12h18"></path>
        <path d="m15 6 6 6-6 6"></path>
        <path d="M5 7l7 5-7 5"></path>
      </symbol>
      <symbol id="icon-bed" viewBox="0 0 24 24">
        <path d="M4 11V5"></path>
        <path d="M4 15h16"></path>
        <path d="M20 15v4"></path>
        <path d="M4 19v-8h10a6 6 0 0 1 6 6v2"></path>
        <path d="M8 11V9h4v2"></path>
      </symbol>
      <symbol id="icon-map" viewBox="0 0 24 24">
        <path d="m9 18-6 3V6l6-3 6 3 6-3v15l-6 3-6-3Z"></path>
        <path d="M9 3v15"></path>
        <path d="M15 6v15"></path>
      </symbol>
      <symbol id="icon-users" viewBox="0 0 24 24">
        <circle cx="9" cy="8" r="4"></circle>
        <path d="M3 21a6 6 0 0 1 12 0"></path>
        <path d="M16 5a4 4 0 0 1 0 6"></path>
        <path d="M21 21a6 6 0 0 0-4-5.7"></path>
      </symbol>
      <symbol id="icon-wallet" viewBox="0 0 24 24">
        <path d="M4 7h16v12H4a2 2 0 0 1-2-2V5a2 2 0 0 0 2 2Z"></path>
        <path d="M18 12h2v4h-2a2 2 0 0 1 0-4Z"></path>
      </symbol>
      <symbol id="icon-check" viewBox="0 0 24 24">
        <path d="m4 12 5 5L20 6"></path>
      </symbol>
      <symbol id="icon-lock" viewBox="0 0 24 24">
        <rect x="5" y="10" width="14" height="10" rx="2"></rect>
        <path d="M8 10V7a4 4 0 0 1 8 0v3"></path>
        <path d="M12 14v2"></path>
      </symbol>
      <symbol id="icon-user" viewBox="0 0 24 24">
        <circle cx="12" cy="8" r="4"></circle>
        <path d="M4 21a8 8 0 0 1 16 0"></path>
      </symbol>
      <symbol id="icon-star" viewBox="0 0 24 24">
        <path d="M12 3.5l2.6 5.3 5.9.85-4.25 4.14 1 5.86L12 17.9l-5.25 2.75 1-5.86L3.5 9.65l5.9-.85L12 3.5Z"></path>
      </symbol>
      <symbol id="icon-swap" viewBox="0 0 24 24">
        <path d="M4 8h13"></path>
        <path d="m14 5 3 3-3 3"></path>
        <path d="M20 16H7"></path>
        <path d="m10 13-3 3 3 3"></path>
      </symbol>
    </svg>
  );
}
