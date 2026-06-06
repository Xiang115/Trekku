export default function CitySelect({
  cities,
  value,
  onChange,
  loading,
}: {
  cities: string[];
  value: string;
  onChange: (city: string) => void;
  loading: boolean;
}) {
  return (
    <label className="select-field">
      City
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={loading || cities.length === 0}
      >
        {loading && <option>Loading…</option>}
        {!loading && cities.length === 0 && <option>No cities</option>}
        {!loading &&
          cities.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
      </select>
    </label>
  );
}
