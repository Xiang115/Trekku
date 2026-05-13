# Trekku

AI-powered travel itinerary generator. Uses Groq LLM for itinerary generation and HuggingFace embeddings for RAG-based recommendations, with Firebase as the data store.

## Prerequisites

- Python 3.10+
- [Firebase project](https://console.firebase.google.com/) with Firestore enabled
- Groq API key
- HuggingFace API key

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/Xiang115/Trekku.git
cd Trekku
```

### 2. Create a virtual environment

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

## Running Tests

```bash
pytest tests/
```

## Project Structure
trekku-workspace/
│
│
├── backend/                            # Deploys to Render
│   ├── .env                            # All secret keys (never commit)
│   ├── .env.example                    # Template for teammates
│   ├── requirements.txt                # Python dependencies
│   │
│   ├── config.py                       # Loads .env, Firebase init
│   ├── models.py                       # Pydantic data models / schemas
│   ├── database.py                     # Firebase read/write functions
│   │
│   ├── knowledge_capture.py            # YOUR MODULE (knowledge capture)
│   │   ├── seed_database()
│   │   ├── ttl_checker()
│   │   ├── trend_tracker()
│   │   ├── quota_tracker()
│   │   ├── fetch_and_parse()
│   │   └── store_to_firebase()
│   │
│   ├── ai_engine.py                    # AI Engineer (Groq + HuggingFace RAG)
│   ├── main.py                         # FastAPI entry point, all routes
│   │
│   └── tests/
│       ├── test_knowledge_capture.py   # Unit tests for your module
│       ├── test_database.py
│       └── test_ai_engine.py
│
├── frontend/                           # Deploys to Vercel
│   ├── package.json
│   ├── .env.local                      # Frontend env vars (API base URL)
│   │
│   ├── public/
│   │   └── index.html
│   │
│   └── src/
│       ├── index.js
│       ├── App.jsx
│       ├── App.css
│       │
│       ├── components/
│       │   ├── SearchForm.jsx          # User input: destination, budget, dates
│       │   ├── ItineraryCard.jsx       # Displays generated itinerary
│       │   ├── HotelCard.jsx           # Hotel recommendation display
│       │   └── FlightCard.jsx          # Flight info display
│       │
│       ├── pages/
│       │   ├── Home.jsx
│       │   ├── PlanTrip.jsx
│       │   └── SavedItineraries.jsx
│       │
│       └── services/
│           └── api.js                  # Axios calls to FastAPI backend
│
├── firebase/
│   ├── firestore.rules                 # Firestore security rules
│   ├── firestore.indexes.json          # Composite indexes
│   └── serviceAccountKey.json         # Firebase Admin SDK key (never commit)
│
├── docs/
│   ├── prd.md                          # Knowledge capture PRD (this file)
│   ├── api-contracts.md                # Endpoint definitions for all teammates
│   └── architecture.md                # System architecture notes
│
├── .gitignore
└── README.md
```