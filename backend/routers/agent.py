import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

import agent as agent_module
from database import get_record, set_record
from models import ChatRequest, ChatResponse, FeedbackRequest, ModifyRequest

router = APIRouter(prefix="/agent", tags=["agent"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Start or continue a trip planning conversation."""
    return await agent_module.chat_async(request.session_id, request.message)


@router.get("/session/{session_id}")
def get_session(session_id: str):
    """Retrieve full session state including conversation history."""
    session = agent_module.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/feedback")
def submit_feedback(request: FeedbackRequest):
    """
    Record explicit user feedback on an itinerary or specific entity.
    If rating (1-5) is provided, maps to signal: (rating - 3) / 2.
    """
    signal = request.signal
    if request.rating is not None:
        signal = (request.rating - 3) / 2.0

    # Derive session_id from the itinerary document
    itinerary_doc = get_record("generated_itineraries", request.itinerary_id)
    if itinerary_doc is None:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    feedback_id = str(uuid.uuid4())
    feedback_type = "explicit_rating" if request.rating is not None else "explicit_text"

    record = {
        "feedback_id": feedback_id,
        "itinerary_id": request.itinerary_id,
        "session_id": itinerary_doc.get("session_id", ""),
        "created_at": _now_iso(),
        "feedback_type": feedback_type,
        "entity_type": request.entity_type,
        "entity_id": request.entity_id,
        "signal": round(signal, 4),
        "details": {
            "rating": request.rating,
            "comment": request.comment,
        },
    }

    set_record("tacit_feedback", feedback_id, record)
    return {"feedback_id": feedback_id}


@router.post("/modify")
def modify_entity(request: ModifyRequest):
    """
    Record an implicit modification: user replaced one entity with another.
    Writes negative signal for original and positive signal for replacement.
    """
    itinerary_doc = get_record("generated_itineraries", request.itinerary_id)
    if itinerary_doc is None:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    session_id = itinerary_doc.get("session_id", "")
    now = _now_iso()

    original_id = str(uuid.uuid4())
    replacement_id = str(uuid.uuid4())

    set_record("tacit_feedback", original_id, {
        "feedback_id": original_id,
        "itinerary_id": request.itinerary_id,
        "session_id": session_id,
        "created_at": now,
        "feedback_type": "implicit_modification",
        "entity_type": request.entity_type,
        "entity_id": request.original_entity_id,
        "signal": -0.8,
        "details": {
            "original_entity_id": request.original_entity_id,
            "replacement_entity_id": request.replacement_entity_id,
        },
    })

    set_record("tacit_feedback", replacement_id, {
        "feedback_id": replacement_id,
        "itinerary_id": request.itinerary_id,
        "session_id": session_id,
        "created_at": now,
        "feedback_type": "implicit_modification",
        "entity_type": request.entity_type,
        "entity_id": request.replacement_entity_id,
        "signal": 0.8,
        "details": {
            "original_entity_id": request.original_entity_id,
            "replacement_entity_id": request.replacement_entity_id,
        },
    })

    return {"feedback_ids": [original_id, replacement_id]}


@router.get("/itinerary/{itinerary_id}")
def get_itinerary(itinerary_id: str):
    """Retrieve a previously generated itinerary by ID."""
    doc = get_record("generated_itineraries", itinerary_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    return doc
