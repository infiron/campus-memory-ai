"""Optional OpenAI-compatible embedding adapter. Empty/failed configuration cleanly falls back to keyword search."""
import math
import httpx
from ..config import settings

async def semantic_similarity_map(query: str, documents: list[tuple[int, str]]) -> dict[int, float]:
    if not (settings.ai_base_url and settings.ai_api_key and settings.ai_embedding_model) or not documents:
        return {}
    url = settings.ai_base_url.rstrip("/")
    if not url.endswith("/embeddings"):
        url += "/embeddings"
    inputs = [query] + [text[:6000] for _, text in documents]
    try:
        async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
            response = await client.post(url, headers={"Authorization": f"Bearer {settings.ai_api_key}", "Content-Type": "application/json"},
                                         json={"model": settings.ai_embedding_model, "input": inputs})
            response.raise_for_status()
            payload = response.json()
        vectors = [item["embedding"] for item in sorted(payload.get("data", []), key=lambda row: row.get("index", 0))]
        if len(vectors) != len(inputs):
            return {}
        q = vectors[0]
        def cosine(a, b):
            dot = sum(x*y for x,y in zip(a,b)); na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
            return dot/(na*nb) if na and nb else 0.0
        return {documents[i][0]: max(0.0, min(1.0, cosine(q, vectors[i+1]))) for i in range(len(documents))}
    except Exception:
        # The caller continues with lexical retrieval; model outage must not block knowledge lookup.
        return {}
