---
name: rag-retrieval-standards
description: Standards for the retrieval / RAG layer of this AI project (LlamaIndex + hybrid search + reranking). Use this whenever building, reviewing, or tuning ingestion, chunking, indexing, retrieval, reranking, or citation handling — so Claude builds a grounded, traceable retrieval pipeline instead of a vector-search demo that hallucinates. Triggers on any mention of RAG, retrieval, LlamaIndex, chunking, embeddings, vector store, reranking, or citations, even for a small change.
---

# RAG retrieval standards

Assumes the root `project-conventions` skill. Retrieval quality is the ceiling on answer
quality — the model can only be as grounded as what you feed it. This layer's job is to
return the *right* context with *traceable sources*, so the generation and guardrail
layers can produce answers that are provably grounded.

## The core principle: retrieval is the real problem, generation is the easy part

Most "the AI hallucinated" failures are actually retrieval failures — the right chunk was
never retrieved, so the model filled the gap. **Prove retrieval quality on its own, before
wiring in the LLM.** If retrieval is bad, no prompt will save you.

## Ingestion and chunking

- **Chunk on semantic boundaries, not arbitrary character counts.** Split on headings,
  paragraphs, or sentences so a chunk is a coherent unit of meaning. A chunk cut mid-
  sentence retrieves badly.
- **Attach metadata to every chunk**: source document id, title, section, page/URL,
  and last-updated date. This metadata is what makes citations and filtering possible —
  a chunk with no provenance can't be cited or trusted.
- **Tune chunk size to the content.** Dense reference docs want smaller chunks; narrative
  docs want larger. There's no universal number — measure it (see evals below).
- **Handle updates and deletes.** Documents change; stale chunks produce confidently wrong
  answers. Re-index on change and remove deleted sources.

## Retrieval — hybrid is the baseline, not an upgrade

- **Use hybrid search: dense (vector) + sparse (BM25/keyword), then combine.** Pure vector
  search misses exact terms, IDs, and rare keywords; pure keyword misses paraphrase.
  Hybrid is the current production baseline — treat vector-only as incomplete.
- **Rerank the merged candidates** with a cross-encoder reranker before passing to the
  model. Retrieve broad (e.g. top 20), rerank, keep the best few. This step reliably lifts
  answer quality more than prompt tweaking does.
- **Filter by metadata** when the query implies it (recency, document type, access scope).
  Never retrieve across documents the current user isn't authorized to see — retrieval is
  a trust boundary too.

## Grounding and citations

- **Carry source metadata all the way to the answer.** Every retrieved chunk keeps its
  `doc_id`/section so the generation layer can cite it and the guardrail layer can verify
  the answer against it. If provenance is dropped in retrieval, groundedness can't be
  enforced downstream.
- **Return enough for the model to cite, not so much it drowns.** Passing 30 chunks
  dilutes attention and inflates cost; passing the reranked top few, each with its id,
  is what enables `[doc_id]` citations.
- **If nothing relevant is retrieved, say so — don't pad.** An empty or low-score
  retrieval should surface as "no supporting context found," which the agent turns into
  "I don't have enough information," not a guess. This is the honest-failure path.

## Context assembly

- Assemble the prompt context deterministically: deduplicate chunks, order by relevance,
  and clearly delimit each source with its id so citations map cleanly.
- Respect the context window budget — count tokens, and prefer fewer high-relevance chunks
  over stuffing the window. Overstuffing degrades both quality and cost.
- Keep retrieved context clearly separated from instructions in the prompt, so retrieved
  text (which may itself contain injection attempts) can't be mistaken for system
  instructions. See `llm-guardrails-standards`.

## Measuring retrieval quality (do this before generation)

- **Build a small labeled set** of queries with their known-correct source chunks, and
  measure **context recall** (did we retrieve the chunk that contains the answer?) and
  **context precision** (how much of what we retrieved was relevant?). These are
  retrieval-only metrics — you can compute them with no LLM in the loop.
- Use these numbers to tune chunk size, hybrid weighting, and reranking — iterate on the
  metric, not on vibes. This ties directly into the full eval suite in
  `llm-evals-standards` (Ragas: context precision / recall / faithfulness).

## Performance and cost

- **Cache** embeddings and frequent-query results (Redis). Re-embedding the same query or
  re-retrieving identical requests is wasted latency and money.
- Batch embedding calls during ingestion rather than one-per-chunk.
- Measure p95 retrieval latency separately from generation latency, so you know which half
  of a slow response to fix.
