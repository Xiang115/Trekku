from config import GROQ_API_KEY, HUGGINGFACE_API_KEY


def generate_itinerary(destination: str, budget: float, days: int) -> list:
    """Call Groq LLM to generate a day-by-day itinerary."""
    pass


def rag_query(query: str, context_docs: list) -> str:
    """Run a RAG pipeline using HuggingFace embeddings + Groq generation."""
    pass
