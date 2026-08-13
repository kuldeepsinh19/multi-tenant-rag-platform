"""EmbeddingProvider adapter for Google Gemini's free-tier embedding API. This is the only
file in the codebase that imports langchain_google_genai's embeddings class."""

from langchain_google_genai import GoogleGenerativeAIEmbeddings


class GeminiEmbeddings:
    def __init__(self, api_key: str, model: str, dim: int) -> None:
        # `output_dimensionality` pins the vector length to our pgvector column size.
        # gemini-embedding-001 defaults to 3072 dims but supports Matryoshka truncation,
        # so we request exactly `dim` (768) to match the `chunks.embedding` column.
        self._client = GoogleGenerativeAIEmbeddings(
            model=model, google_api_key=api_key, output_dimensionality=dim
        )
        self._dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await self._client.aembed_documents(texts)

    @property
    def dim(self) -> int:
        return self._dim
