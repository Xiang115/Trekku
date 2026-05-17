from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.ratings import router as ratings_router

app = FastAPI(title="Trekku API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ratings_router)


@app.get("/health")
def health():
    return {"status": "ok"}
