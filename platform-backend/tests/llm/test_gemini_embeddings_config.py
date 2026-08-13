"""Regression test for Gemini embedding dimensionality (src/llm/adapters/gemini_embeddings.py).

The old model `text-embedding-004` 404'd on the live API; we switched to
`gemini-embedding-001`, which defaults to 3072 dims. We MUST pin `output_dimensionality`
to 768 to match the pgvector `chunks.embedding` column. Pure construction test — no
network calls (the suite never hits the live Gemini API).
"""

from src.llm.adapters.gemini_embeddings import GeminiEmbeddings


def test_gemini_embeddings_pins_output_dimensionality() -> None:
    adapter = GeminiEmbeddings(api_key="test", model="gemini-embedding-001", dim=768)

    assert adapter.dim == 768
    # The underlying GoogleGenerativeAIEmbeddings client must carry the pinned dimension,
    # otherwise it would default to 3072 and mismatch the pgvector column.
    assert adapter._client.output_dimensionality == 768
