# Trekku

AI-powered travel planner for Malaysia. A conversational agent gathers trip details over chat, then generates a day-by-day itinerary of hotels, attractions, and flights. Recommendations are grounded in a continuously refreshed knowledge base of real prices, ratings, and review trends scraped via SerpAPI and stored in Firebase.

- **Backend** — FastAPI agent (Google ADK + Groq LLM) with RAG over HuggingFace embeddings, served on Render.
- **Frontend** — React + Vite (TypeScript) single-page app, deployed on Vercel.
- **Data** — Firebase Firestore as the store; a daily GitHub Actions cron refreshes price/rating snapshots.

## Prerequisites

- Python 3.10+
- Node 18+ (developed on Node 22)
- [Firebase project](https://console.firebase.google.com/) with Firestore enabled, plus a service account key
- Groq API key
- HuggingFace API key
- One or more SerpAPI keys (used by the knowledge-capture scraper; rotated to spread quota)

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/Xiang115/Trekku.git
cd Trekku
```

### 2. Backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

Copy the env template and fill in your keys:

```bash
cp .env.example .env
```

| Variable | Purpose |
|----------|---------|
| `SERPAPI_KEY_1` … `SERPAPI_KEY_5` | SerpAPI keys for the knowledge-capture scraper (any subset) |
| `FIREBASE_PROJECT_ID` / `FIREBASE_PRIVATE_KEY` / `FIREBASE_CLIENT_EMAIL` | Firebase Admin credentials |
| `GROQ_API_KEY` | Groq LLM (itinerary + chat agent) |
| `HUGGINGFACE_API_KEY` | HuggingFace embeddings for RAG |
| `ENVIRONMENT` | `development` or `production` |

Place your Firebase service account JSON at `firebase/serviceAccountKey.json`, or set
`FIREBASE_SERVICE_ACCOUNT_PATH` to point elsewhere.

Run the API:

```bash
uvicorn main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env   # optional; leave VITE_API_BASE_URL empty to use the dev proxy
npm run dev            # http://localhost:5173
```

`VITE_API_BASE_URL` is empty by default, so API calls go same-origin and the Vite dev
proxy (`vite.config.ts`) forwards `/agent`, `/ratings`, and `/health` to `localhost:8000`.
Set it to an absolute URL for production builds.

## Seeding & refreshing data

From `backend/` (with the venv active and `.env` configured):

```bash
python run_seed.py      # one-time: seed Firestore + initialise SerpAPI quota records
python run_refresh.py   # refresh price/rating snapshots (run daily via GitHub Actions cron)
```

## Running tests

```bash
cd backend
pytest tests/
```

## API overview

| Method & path | Description |
|---------------|-------------|
| `POST /agent/chat` | Start or continue a trip-planning conversation |
| `POST /agent/chat/stream` | Same as `/chat`, streaming agent progress over SSE |
| `GET /agent/session/{id}` | Retrieve full session state + conversation history |
| `GET /agent/itinerary/{id}` | Retrieve a previously generated itinerary |
| `POST /agent/feedback` | Record a star rating / comment on an itinerary or entity |
| `POST /agent/modify` | Record an entity swap (negative signal for old, positive for new) |
| `GET /ratings/cities` | List supported cities |
| `GET /ratings/entities` | Distinct hotels / attractions / flights for a city |
| `GET /ratings/trend/{type}/{id}` | Price / rating / review history for an entity |
| `GET /health` | Health check |

## Project structure

```
Trekku/
│
├── backend/                            # FastAPI app — deploys to Render
│   ├── main.py                         # App entry point, CORS, exception handlers, routers
│   ├── config.py                       # Loads .env, Firebase init
│   ├── models.py                       # Pydantic request/response schemas
│   ├── database.py                     # Firestore read/write/query helpers
│   │
│   ├── agent.py                        # Conversational planning agent (Google ADK + Groq)
│   ├── ai_engine.py                    # Itinerary generation + HuggingFace RAG, param extraction
│   ├── knowledge_capture.py            # SerpAPI scraping, seeding, daily refresh, quota tracking
│   │
│   ├── routers/
│   │   ├── agent.py                    # /agent/* — chat, streaming, feedback, modify, itinerary
│   │   └── ratings.py                  # /ratings/* — cities, entities, trends
│   │
│   ├── run_seed.py                     # One-time Firestore seed + quota init
│   ├── run_refresh.py                  # Daily snapshot refresh (GitHub Actions cron)
│   ├── clear_database.py               # Utility to wipe collections
│   ├── requirements.txt                # Python dependencies
│   ├── .env.example                    # Env template
│   │
│   └── tests/                          # pytest suite
│
├── frontend/                           # React + Vite (TypeScript) — deploys to Vercel
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts                  # Dev proxy to backend
│   ├── public/
│   └── src/
│       ├── main.tsx · App.tsx
│       ├── api/                        # typed client (client.ts) + backend types (types.ts)
│       ├── components/                 # planner/ · itinerary/ · insights/ · checkout/ + Topbar, AuthModal
│       ├── state/                      # AuthContext (demo auth) · ChatContext (session/itinerary)
│       ├── hooks/                      # useRatings
│       ├── icons/ · lib/ · config/ · styles/
│       └── ...
│
├── firebase/
│   └── serviceAccountKey.json          # Firebase Admin SDK key (never commit)
│
└── README.md
```
