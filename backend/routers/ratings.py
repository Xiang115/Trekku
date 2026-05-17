from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from models import TrendResponse, TrendPoint, EntitySummary
from database import query_records
from knowledge_capture import TREKKU_SEED

router = APIRouter(prefix="/ratings", tags=["ratings"])


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

    records = query_records("rating_snapshots", "entity_type", "==", entity_type)
    city_lower = city.strip().lower()
    filtered = [r for r in records if r.get("city", "").strip().lower() == city_lower]

    seen: dict = {}
    for r in filtered:
        eid = r["entity_id"]
        if eid not in seen:
            seen[eid] = EntitySummary(
                entity_id=eid,
                name=r.get("name", ""),
                city=r.get("city", ""),
            )

    return list(seen.values())


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
