import { useState } from "react";
import Icon from "../../icons/Icon";

export default function StarRating({
  value,
  onRate,
  disabled,
}: {
  value: number;
  onRate: (n: number) => void;
  disabled?: boolean;
}) {
  const [hover, setHover] = useState(0);
  const active = hover || value;

  return (
    <div className={`star-rating${value ? " is-saved" : ""}`} role="radiogroup" aria-label="Rate">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          disabled={disabled}
          className={n <= active ? "is-filled" : ""}
          onMouseEnter={() => setHover(n)}
          onMouseLeave={() => setHover(0)}
          onClick={() => onRate(n)}
          aria-label={`Rate ${n} star${n > 1 ? "s" : ""}`}
          aria-checked={value === n}
          role="radio"
        >
          <Icon name="star" />
        </button>
      ))}
    </div>
  );
}
