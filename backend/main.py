from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

from routers.ratings import router as ratings_router
from routers.agent import router as agent_router

app = FastAPI(title="Trekku API")


@app.exception_handler(ResourceExhausted)
async def handle_quota_exhausted(request: Request, exc: ResourceExhausted):
    # Firestore daily quota exhausted (free tier). Degrade cleanly instead of
    # surfacing an unhandled 500 with a gRPC stack trace.
    return JSONResponse(
        status_code=503,
        content={"detail": "Data store quota exceeded; please try again later."},
    )


@app.exception_handler(ServiceUnavailable)
async def handle_backend_unavailable(request: Request, exc: ServiceUnavailable):
    return JSONResponse(
        status_code=503,
        content={"detail": "Data store temporarily unavailable; please try again later."},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ratings_router)
app.include_router(agent_router)


@app.get("/health")
def health():
    return {"status": "ok"}
