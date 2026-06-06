export default function DayTabs({
  days,
  active,
  onSelect,
}: {
  days: number[];
  active: number;
  onSelect: (index: number) => void;
}) {
  return (
    <div className="day-tabs" role="tablist" aria-label="Itinerary days">
      {days.map((dayNumber, index) => (
        <button
          key={dayNumber}
          type="button"
          role="tab"
          aria-selected={index === active}
          className={index === active ? "is-active" : ""}
          onClick={() => onSelect(index)}
        >
          Day {dayNumber}
        </button>
      ))}
    </div>
  );
}
