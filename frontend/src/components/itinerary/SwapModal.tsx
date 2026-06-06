import { useEffect, useState } from "react";
import * as api from "../../api/client";
import { ApiError } from "../../api/client";
import { formatCurrency } from "../../lib/format";
import type { EntitySummary, EntityType } from "../../api/types";

const KIND_LABEL: Record<EntityType, string> = {
  hotels: "hotel",
  attractions: "attraction",
  flights: "flight",
};

export default function SwapModal({
  open,
  onClose,
  itineraryId,
  entityType,
  originalId,
  city,
  onSwapped,
}: {
  open: boolean;
  onClose: () => void;
  itineraryId: string;
  entityType: EntityType;
  originalId: string;
  city: string | null;
  onSwapped: (replacement: EntitySummary) => void;
}) {
  const [candidates, setCandidates] = useState<EntitySummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (!city) {
      setError("No city is set for this trip yet, so alternatives can't be loaded.");
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setSelected(null);
    api
      .getEntities(entityType, city)
      .then((list) => {
        if (cancelled) return;
        setCandidates(list.filter((e) => e.entity_id !== originalId));
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Could not load alternatives.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, city, entityType, originalId]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const confirm = async () => {
    const replacement = candidates.find((c) => c.entity_id === selected);
    if (!replacement) return;
    setSaving(true);
    setError(null);
    try {
      await api.modifyEntity({
        itinerary_id: itineraryId,
        original_entity_id: originalId,
        replacement_entity_id: replacement.entity_id,
        entity_type: entityType,
      });
      onSwapped(replacement);
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not record the swap.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal" role="dialog" aria-modal="true" aria-label="Swap entity">
      <div className="modal-backdrop" onClick={onClose} />
      <div className="modal-dialog">
        <h3>Swap {KIND_LABEL[entityType]}</h3>
        <p>
          Pick an alternative in {city}. This records a learning signal to improve future
          recommendations — it doesn't regenerate the itinerary.
        </p>

        {loading && (
          <div className="loading-note">
            <span className="inline-spinner" /> Loading alternatives…
          </div>
        )}
        {error && <div className="error-note">{error}</div>}
        {!loading && !error && candidates.length === 0 && (
          <div className="empty-state">No alternatives available for this city.</div>
        )}

        {!loading && candidates.length > 0 && (
          <ul className="candidate-list">
            {candidates.map((c) => (
              <li key={c.entity_id}>
                <button
                  type="button"
                  className={`candidate-option${selected === c.entity_id ? " is-selected" : ""}`}
                  onClick={() => setSelected(c.entity_id)}
                >
                  <span>{c.name}</span>
                  <span>
                    {c.price != null
                      ? `${formatCurrency(c.price)}${entityType === "hotels" ? "/night" : ""}`
                      : c.city}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="modal-actions">
          <button className="ghost" type="button" onClick={onClose}>
            Cancel
          </button>
          <button className="primary" type="button" onClick={confirm} disabled={!selected || saving}>
            {saving ? "Saving…" : "Confirm swap"}
          </button>
        </div>
      </div>
    </div>
  );
}
