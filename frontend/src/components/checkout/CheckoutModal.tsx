import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../../state/AuthContext";
import { useChat } from "../../state/ChatContext";
import { formatCurrency } from "../../lib/format";
import { costBreakdown } from "../../lib/cost";

type Step = "review" | "payment" | "processing" | "success";

const onlyDigits = (s: string) => s.replace(/\D/g, "");

/** Format a 16-digit card number into "#### #### #### ####" groups. */
const formatCard = (s: string) => onlyDigits(s).slice(0, 16).replace(/(.{4})/g, "$1 ").trim();
const formatExpiry = (s: string) => {
  const d = onlyDigits(s).slice(0, 4);
  return d.length <= 2 ? d : `${d.slice(0, 2)}/${d.slice(2)}`;
};

export default function CheckoutModal({
  open,
  onClose,
  onOpenLogin,
}: {
  open: boolean;
  onClose: () => void;
  onOpenLogin: () => void;
}) {
  const { user } = useAuth();
  const { currentItinerary, paramsCollected } = useChat();
  const [step, setStep] = useState<Step>("review");
  const [card, setCard] = useState("");
  const [expiry, setExpiry] = useState("");
  const [cvc, setCvc] = useState("");
  const [cardName, setCardName] = useState("");
  const [bookingRef, setBookingRef] = useState("");

  const travelers = Math.max(1, paramsCollected?.travelers ?? 1);
  const breakdown = useMemo(
    () => (currentItinerary ? costBreakdown(currentItinerary, travelers) : null),
    [currentItinerary, travelers],
  );

  // Reset to the first step whenever the modal is (re)opened.
  useEffect(() => {
    if (open) setStep("review");
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !currentItinerary || !breakdown) return null;

  const paymentValid =
    cardName.trim().length > 1 &&
    onlyDigits(card).length === 16 &&
    onlyDigits(expiry).length === 4 &&
    onlyDigits(cvc).length >= 3;

  const pay = () => {
    setStep("processing");
    setBookingRef(`TRK-${Math.random().toString(36).slice(2, 8).toUpperCase()}`);
    // Mock payment latency — nothing is actually charged.
    window.setTimeout(() => setStep("success"), 1200);
  };

  // Bookable entities are charged at checkout; meals/transport are estimates shown separately.
  const bookedRows: Array<[string, string]> = [
    ["Hotels", breakdown.hotels > 0 ? formatCurrency(breakdown.hotels) : "Included"],
    ["Flight", breakdown.flight > 0 ? formatCurrency(breakdown.flight) : "Included"],
    ["Attractions", "Free entry"],
  ];
  const estimateRows: Array<[string, number]> = [
    ["Meals", breakdown.meals],
    ["Local transport", breakdown.transport],
  ];

  return (
    <div className="modal" role="dialog" aria-modal="true" aria-label="Checkout">
      <div className="modal-backdrop" onClick={onClose} />
      <div className="modal-dialog checkout-modal">
        {step === "review" && (
          <>
            <h3>Review your trip</h3>
            <p>
              {currentItinerary.days.length}-day trip
              {paramsCollected?.city ? ` to ${paramsCollected.city}` : ""} · {travelers}{" "}
              {travelers === 1 ? "traveller" : "travellers"}
            </p>

            <div className="checkout-lines">
              {bookedRows.map(([label, amount]) => (
                <div className="checkout-line" key={label}>
                  <span>{label}</span>
                  <span>{amount}</span>
                </div>
              ))}
              <div className="checkout-line total">
                <span>Booking total</span>
                <strong>{formatCurrency(breakdown.bookedTotal)}</strong>
              </div>
            </div>

            <p className="checkout-section-label">Estimated on-trip extras (not booked)</p>
            <div className="checkout-lines">
              {estimateRows.map(([label, amount]) => (
                <div className="checkout-line" key={label}>
                  <span>
                    {label}
                    <em className="est-tag">est.</em>
                  </span>
                  <span>{formatCurrency(amount)}</span>
                </div>
              ))}
              <div className="checkout-line">
                <span>Est. trip cost incl. extras</span>
                <span>{formatCurrency(breakdown.total)}</span>
              </div>
            </div>
            <p className="checkout-note">
              Meals and local transport are estimates you pay during your trip — they aren't booked or
              charged through Trekku.
            </p>

            {!user && (
              <div className="error-note">Please log in to complete your booking.</div>
            )}

            <div className="modal-actions">
              <button className="ghost" type="button" onClick={onClose}>
                Keep editing
              </button>
              {user ? (
                <button className="primary" type="button" onClick={() => setStep("payment")}>
                  Continue to payment
                </button>
              ) : (
                <button className="primary" type="button" onClick={onOpenLogin}>
                  Log in to checkout
                </button>
              )}
            </div>
          </>
        )}

        {step === "payment" && (
          <>
            <h3>Payment</h3>
            <p>
              Paying <strong>{formatCurrency(breakdown.bookedTotal)}</strong>. This is a demo — no card
              is charged.
            </p>

            <div className="pay-form">
              <label>
                <span>Name on card</span>
                <input
                  type="text"
                  value={cardName}
                  autoComplete="cc-name"
                  onChange={(e) => setCardName(e.target.value)}
                  placeholder="Jordan Tan"
                />
              </label>
              <label>
                <span>Card number</span>
                <input
                  type="text"
                  inputMode="numeric"
                  value={card}
                  onChange={(e) => setCard(formatCard(e.target.value))}
                  placeholder="4242 4242 4242 4242"
                />
              </label>
              <div className="pay-row">
                <label>
                  <span>Expiry</span>
                  <input
                    type="text"
                    inputMode="numeric"
                    value={expiry}
                    onChange={(e) => setExpiry(formatExpiry(e.target.value))}
                    placeholder="MM/YY"
                  />
                </label>
                <label>
                  <span>CVC</span>
                  <input
                    type="text"
                    inputMode="numeric"
                    value={cvc}
                    onChange={(e) => setCvc(onlyDigits(e.target.value).slice(0, 4))}
                    placeholder="123"
                  />
                </label>
              </div>
            </div>

            <div className="modal-actions">
              <button className="ghost" type="button" onClick={() => setStep("review")}>
                Back
              </button>
              <button className="primary" type="button" onClick={pay} disabled={!paymentValid}>
                Pay {formatCurrency(breakdown.bookedTotal)}
              </button>
            </div>
          </>
        )}

        {step === "processing" && (
          <div className="checkout-processing">
            <span className="inline-spinner" />
            <p>Confirming your booking…</p>
          </div>
        )}

        {step === "success" && (
          <div className="checkout-success">
            <div className="success-check">✓</div>
            <h3>Booking confirmed</h3>
            <p>
              Your Trekku trip{paramsCollected?.city ? ` to ${paramsCollected.city}` : ""} is locked
              in. A confirmation was sent to {user?.email ?? "your email"}.
            </p>
            <div className="checkout-line total">
              <span>Booking reference</span>
              <strong>{bookingRef}</strong>
            </div>
            <div className="checkout-line total">
              <span>Total paid</span>
              <strong>{formatCurrency(breakdown.bookedTotal)}</strong>
            </div>
            <div className="modal-actions">
              <button className="primary" type="button" onClick={onClose}>
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
