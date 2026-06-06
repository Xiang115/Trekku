import { formatCurrency } from "../../lib/format";
import type { TripParams } from "../../api/types";

export default function ParamsChips({ params }: { params: TripParams | null }) {
  const chips: { label: string; value: string | null }[] = [
    { label: "City", value: params?.city ?? null },
    { label: "From", value: params?.origin_state ?? null },
    { label: "Days", value: params?.days != null ? `${params.days}` : null },
    { label: "Travellers", value: params?.travelers != null ? `${params.travelers}` : null },
    { label: "Budget", value: params?.budget != null ? formatCurrency(params.budget) : null },
    { label: "Date", value: params?.travel_date ?? null },
  ];

  return (
    <div className="params-chips" aria-label="Trip details collected so far">
      {chips.map((chip) => (
        <span key={chip.label} className={`badge${chip.value ? " is-set" : ""}`}>
          {chip.label}: {chip.value ?? "—"}
        </span>
      ))}
    </div>
  );
}
