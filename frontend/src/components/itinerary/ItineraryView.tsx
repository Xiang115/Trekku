import { useState } from "react";
import { useChat } from "../../state/ChatContext";
import { formatCurrency } from "../../lib/format";
import { costBreakdown, hotelNightly } from "../../lib/cost";
import type { PricePerNight } from "../../api/types";
import CheckoutModal from "../checkout/CheckoutModal";
import DayTabs from "./DayTabs";
import EntityCard from "./EntityCard";

function hotelPriceLabel(price: PricePerNight): string {
  return `${formatCurrency(hotelNightly(price))}/night`;
}

export default function ItineraryView({ onOpenLogin }: { onOpenLogin: () => void }) {
  const { currentItinerary, itineraryId, status, paramsCollected } = useChat();
  const [activeDay, setActiveDay] = useState(0);
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const breakdown = currentItinerary
    ? costBreakdown(currentItinerary, paramsCollected?.travelers ?? 1)
    : null;

  return (
    <section className="section-block" id="itinerary">
      <div className="section-heading">
        <div>
          <p className="panel-kicker">AI Itinerary</p>
          <h2>Your generated trip</h2>
        </div>
        {currentItinerary && (
          <span className="badge green">
            Est. {formatCurrency(currentItinerary.total_estimated_cost)}
          </span>
        )}
      </div>

      {!currentItinerary ? (
        <div className="empty-state">
          <h3>No itinerary yet</h3>
          <p>
            {status === "hydrating"
              ? "Restoring your saved trip…"
              : "Plan a trip in the chat above. Once Trekku has your destination, budget and dates, your day-by-day itinerary will appear here."}
          </p>
        </div>
      ) : (
        <div className="dashboard-grid">
          <div className="timeline-panel">
            <DayTabs
              days={currentItinerary.days.map((d) => d.day)}
              active={activeDay}
              onSelect={setActiveDay}
            />

            {(() => {
              const day = currentItinerary.days[activeDay];
              if (!day) return <div className="empty-state">No details for this day.</div>;
              return (
                <div className="entity-list">
                  {day.hotel && (
                    <EntityCard
                      itineraryId={itineraryId}
                      entityType="hotels"
                      entityId={day.hotel.hotel_id}
                      name={day.hotel.name}
                      price={hotelPriceLabel(day.hotel.price_per_night)}
                    />
                  )}
                  {day.attractions.map((a) => (
                    <EntityCard
                      key={a.attraction_id}
                      itineraryId={itineraryId}
                      entityType="attractions"
                      entityId={a.attraction_id}
                      name={a.name}
                      meta={a.estimated_duration ?? undefined}
                    />
                  ))}
                  {day.notes && <p className="day-notes">{day.notes}</p>}
                </div>
              );
            })()}
          </div>

          <aside className="map-panel">
            {currentItinerary.flight && (
              <EntityCard
                itineraryId={itineraryId}
                entityType="flights"
                entityId={currentItinerary.flight.flight_id}
                name={`${currentItinerary.flight.airline} ${currentItinerary.flight.flight_number}`}
                price={formatCurrency(currentItinerary.flight.price)}
              />
            )}

            {breakdown && (
              <div className="cost-breakdown">
                <div className="cost-row">
                  <span>Hotels</span>
                  <span>{breakdown.hotels > 0 ? formatCurrency(breakdown.hotels) : "Included"}</span>
                </div>
                <div className="cost-row">
                  <span>Flight</span>
                  <span>{breakdown.flight > 0 ? formatCurrency(breakdown.flight) : "Included"}</span>
                </div>
                <div className="cost-row">
                  <span>Attractions</span>
                  <span>Free entry</span>
                </div>
                <div className="cost-row total">
                  <span>Booking total</span>
                  <strong>{formatCurrency(breakdown.bookedTotal)}</strong>
                </div>

                <p className="cost-section-label">Estimated extras (not booked)</p>
                <div className="cost-row">
                  <span>Meals <em className="est-tag">est.</em></span>
                  <span>{formatCurrency(breakdown.meals)}</span>
                </div>
                <div className="cost-row">
                  <span>Transport <em className="est-tag">est.</em></span>
                  <span>{formatCurrency(breakdown.transport)}</span>
                </div>
                <div className="cost-row">
                  <span>Est. trip cost incl. extras</span>
                  <span>{formatCurrency(breakdown.total)}</span>
                </div>
              </div>
            )}

            <button
              className="primary checkout-cta"
              type="button"
              onClick={() => setCheckoutOpen(true)}
            >
              Looks good — checkout
            </button>
          </aside>
        </div>
      )}

      <CheckoutModal
        open={checkoutOpen}
        onClose={() => setCheckoutOpen(false)}
        onOpenLogin={onOpenLogin}
      />
    </section>
  );
}
