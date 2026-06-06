import { useState } from "react";
import Icon, { type IconName } from "../../icons/Icon";
import * as api from "../../api/client";
import { ApiError } from "../../api/client";
import { useChat } from "../../state/ChatContext";
import type { EntitySummary, EntityType } from "../../api/types";
import StarRating from "./StarRating";
import SwapModal from "./SwapModal";

const KIND_ICON: Record<EntityType, IconName> = {
  hotels: "bed",
  attractions: "map",
  flights: "plane",
};

const KIND_LABEL: Record<EntityType, string> = {
  hotels: "Hotel",
  attractions: "Attraction",
  flights: "Flight",
};

export default function EntityCard({
  itineraryId,
  entityType,
  entityId,
  name,
  meta,
  price,
}: {
  itineraryId: string | null;
  entityType: EntityType;
  entityId: string;
  name: string;
  meta?: string;
  price?: string;
}) {
  const { paramsCollected, applyLocalSwap } = useChat();
  const [rating, setRating] = useState(0);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [swapOpen, setSwapOpen] = useState(false);

  const handleRate = async (n: number) => {
    if (!itineraryId || busy) return;
    setRating(n);
    setSaved(false);
    setBusy(true);
    setFeedbackError(null);
    try {
      await api.submitFeedback({
        itinerary_id: itineraryId,
        entity_id: entityId,
        entity_type: entityType,
        rating: n,
      });
      setSaved(true);
    } catch (err) {
      setFeedbackError(err instanceof ApiError ? err.message : "Could not save rating.");
    } finally {
      setBusy(false);
    }
  };

  const handleSwapped = (replacement: EntitySummary) => {
    applyLocalSwap(entityType, entityId, replacement);
  };

  return (
    <article className="entity-card">
      <div className="entity-card-head">
        <div>
          <span className="entity-kind">
            <Icon name={KIND_ICON[entityType]} /> {KIND_LABEL[entityType]}
          </span>
          <h4>{name}</h4>
          {meta && <div className="entity-meta">{meta}</div>}
        </div>
        {price && <span className="entity-price">{price}</span>}
      </div>

      <div className="entity-actions">
        <StarRating value={rating} onRate={handleRate} disabled={!itineraryId || busy} />
        <button
          className="swap-button"
          type="button"
          onClick={() => setSwapOpen(true)}
          disabled={!itineraryId}
        >
          <Icon name="swap" /> Swap
        </button>
      </div>

      {saved && <span className="rating-saved">Thanks — feedback saved.</span>}
      {feedbackError && <div className="error-note">{feedbackError}</div>}

      {itineraryId && (
        <SwapModal
          open={swapOpen}
          onClose={() => setSwapOpen(false)}
          itineraryId={itineraryId}
          entityType={entityType}
          originalId={entityId}
          city={paramsCollected?.city ?? null}
          onSwapped={handleSwapped}
        />
      )}
    </article>
  );
}
