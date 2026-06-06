import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

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


def _sse(event: str, data: dict) -> str:
    """Format one Server-Sent Events frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# Marks the end of the queue so the draining generator knows to stop.
_STREAM_DONE = object()


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Same as /chat, but streams the agent's real processing state via SSE.

    Emits `event: status` frames as the agent moves through its stages, then a
    terminal `event: result` carrying the full ChatResponse payload (or
    `event: error` on failure). The agent core is shared with /chat — only the
    transport differs.
    """
    queue: asyncio.Queue = asyncio.Queue()

    async def run_agent() -> None:
        # Set the ContextVar INSIDE the task so nested emit_progress calls find the queue.
        agent_module._progress_queue.set(queue)
        try:
            result = await agent_module.chat_async(request.session_id, request.message)
            await queue.put({"event": "result", "data": result})
        except Exception as exc:  # surface failure to the client, then end cleanly
            await queue.put({"event": "error", "data": {"message": str(exc)}})
        finally:
            await queue.put(_STREAM_DONE)

    async def event_stream():
        task = asyncio.create_task(run_agent())
        try:
            while True:
                item = await queue.get()
                if item is _STREAM_DONE:
                    break
                if "event" in item:
                    yield _sse(item["event"], item["data"])
                else:
                    yield _sse("status", item)
        finally:
            # Client disconnected (or we're done) — make sure the agent task is cleaned up.
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
