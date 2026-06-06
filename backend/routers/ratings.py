from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from models import TrendResponse, TrendPoint, EntitySummary
from database import query_records, get_all_records
from knowledge_capture import TREKKU_SEED, generate_id

# Every flight in the knowledge base routes into Selangor (KUL); origins are
# the other states. Snapshots only ever record a fare, never a rating/review.
FLIGHT_DESTINATION = "Selangor"

router = APIRouter(prefix="/ratings", tags=["ratings"])

# Source collection key holding each entity's stable id. Flights are handled
# separately because they are bucketed by origin state rather than keyed by row.
_ID_FIELD = {"hotels": "hotel_id", "attractions": "attraction_id"}


@router.get("/cities", response_model=List[str])
def get_cities() -> List[str]:
    return TREKKU_SEED["cities"]


@router.get("/entities", response_model=List[EntitySummary])
def get_entities(
    entity_type: str = Query(..., description="One of: hotels, attractions, flights"),
    city: str = Query(..., description="City name from /ratings/cities"),
) -> List[EntitySummary]:
    if entity_type not in ("hotels", "attractions", "flights"):
        raise HTTPException(status_code=400, detail="entity_type must be hotels, attractions, or flights")

    # Read distinct entities straight from the source collections, filtered
    # server-side by city, instead of streaming the entire rating_snapshots
    # history (one doc per entity per day). entity_id / name / city are derived
    # exactly as capture_rating_snapshot() derives them, so the ids returned
    # here match the snapshots that /ratings/trend reads back.
    seen: dict = {}

    if entity_type == "flights":
        # Flights always route into Selangor (KUL), so the destination `city`
        # filter does not apply — a flight "entity" is a route, keyed by its
        # origin state. Many source rows (airlines) collapse into one route via
        # generate_id(..., origin_state, "selangor"); its price is the cheapest
        # fare across those airlines. The `city` query param is accepted for a
        # uniform signature but intentionally ignored here.
        records = [r for r in get_all_records("flights") if r.get("origin_state")]
        for r in records:
            origin = r["origin_state"]
            eid = generate_id("flight", origin, "selangor")
            price = r.get("price")
            existing = seen.get(eid)
            if existing is None:
                seen[eid] = EntitySummary(
                    entity_id=eid,
                    name=f"{origin} → {FLIGHT_DESTINATION}",
                    city=FLIGHT_DESTINATION,
                    price=price,
                )
            elif price is not None and (existing.price is None or price < existing.price):
                existing.price = price
    else:
        id_field = _ID_FIELD[entity_type]
        records = query_records(entity_type, "location.city", "==", city)
        for r in records:
            eid = r.get(id_field)
            if not eid:
                continue
            if eid not in seen:
                seen[eid] = EntitySummary(
                    entity_id=eid,
                    name=r.get("name", ""),
                    city=(r.get("location") or {}).get("city", ""),
                    # Hotels expose a {min, max} nightly range; use its midpoint to match
                    # the representative rate the itinerary shows. Attractions have no price.
                    price=_hotel_midpoint(r) if entity_type == "hotels" else None,
                )

    return list(seen.values())


def _hotel_midpoint(record: dict) -> Optional[float]:
    """Representative nightly rate: midpoint of the stored {min, max} range."""
    ppn = record.get("price_per_night")
    if not ppn:
        return None
    if isinstance(ppn, dict):
        pmin = ppn.get("min", 0) or 0
        pmax = ppn.get("max", pmin) or pmin
        return round((pmin + pmax) / 2)
    return float(ppn)


@router.get("/trend/{entity_type}/{entity_id}", response_model=TrendResponse)
def get_trend(
    entity_type: str,
    entity_id: str,
    from_date: Optional[str] = Query(None, alias="from", description="YYYY-MM-DD start date (inclusive)"),
    to_date: Optional[str] = Query(None, alias="to", description="YYYY-MM-DD end date (inclusive)"),
) -> TrendResponse:
    if entity_type not in ("hotels", "attractions", "flights"):
        raise HTTPException(status_code=400, detail="entity_type must be hotels, attractions, or flights")

    records = query_records("rating_snapshots", "entity_id", "==", entity_id)
    records = [r for r in records if r.get("entity_type") == entity_type]

    if from_date:
        records = [r for r in records if r.get("date", "") >= from_date]
    if to_date:
        records = [r for r in records if r.get("date", "") <= to_date]

    records_sorted = sorted(records, key=lambda r: r.get("date", ""))

    if not records_sorted:
        raise HTTPException(status_code=404, detail=f"No snapshots found for {entity_id}")

    meta = records_sorted[0]
    data_points = [
        TrendPoint(
            date=r["date"],
            rating=r.get("rating"),
            review_count=r.get("review_count"),
            price_min=r.get("price_min"),
        )
        for r in records_sorted
    ]

    return TrendResponse(
        entity_id=entity_id,
        entity_type=entity_type,
        name=meta.get("name", ""),
        city=meta.get("city", ""),
        from_date=from_date,
        to_date=to_date,
        data=data_points,
    )
