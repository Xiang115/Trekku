import type { EntitySummary } from "../../api/types";

export default function EntitySelect({
  entities,
  value,
  onChange,
  loading,
  label = "Entity",
}: {
  entities: EntitySummary[];
  value: string;
  onChange: (entityId: string) => void;
  loading: boolean;
  label?: string;
}) {
  return (
    <label className="select-field">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={loading || entities.length === 0}
      >
        {loading && <option>Loading…</option>}
        {!loading && entities.length === 0 && <option>No entities</option>}
        {!loading &&
          entities.map((e) => (
            <option key={e.entity_id} value={e.entity_id}>
              {e.name}
            </option>
          ))}
      </select>
    </label>
  );
}
