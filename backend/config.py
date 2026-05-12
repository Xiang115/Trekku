import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")

_default_key_path = os.path.join(os.path.dirname(__file__), "..", "firebase", "serviceAccountKey.json")
_cred = credentials.Certificate(
    os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", _default_key_path)
)
firebase_admin.initialize_app(_cred)
db = firestore.client()
