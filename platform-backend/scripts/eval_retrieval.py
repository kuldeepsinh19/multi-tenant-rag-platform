"""Offline retrieval-metrics runner: context precision / context recall against the golden
set, with NO LLM in the loop (llm-evals-standards: measure retrieval quality first, before
touching generation). Precision/recall of the RETRIEVED document ids vs. the golden
`expected_doc_ids` tell you whether the right chunk was fetched at all — the ceiling on
everything the generator can do.

This is a STANDALONE offline tool. It is never imported by the running app. The import of
the retrieval layer (Stage 5) is guarded so this script doesn't hard-fail if that module
isn't merged yet — run it once retrieval + an ingested tenant exist.

Usage (from platform-backend/, inside the api container or an env with the app installed):
    python scripts/eval_retrieval.py --business-id <uuid> [--top-k 5] [--min-precision 0.6]

Exit code is non-zero when a metric falls below its threshold, so this can gate CI once a
real ingested tenant + golden set exist. Without --business-id it prints the format check
and exits 0 (nothing to retrieve against).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

_GOLDEN_PATH = Path(__file__).resolve().parent.parent / "evals" / "golden_dataset.json"


def _load_golden() -> list[dict[str, object]]:
    data = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    if not isinstance(cases, list) or not cases:
        raise SystemExit(f"Golden set at {_GOLDEN_PATH} has no cases.")
    return cases


def context_precision(retrieved_ids: list[str], expected_ids: set[str]) -> float:
    """Fraction of retrieved docs that are relevant (in the golden expected set). 1.0 when
    nothing was retrieved AND nothing was expected; 0.0 when we retrieved but expected
    nothing relevant."""
    if not retrieved_ids:
        return 1.0 if not expected_ids else 0.0
    hits = sum(1 for doc_id in retrieved_ids if doc_id in expected_ids)
    return hits / len(retrieved_ids)


def context_recall(retrieved_ids: list[str], expected_ids: set[str]) -> float:
    """Fraction of expected (golden) docs that were actually retrieved. 1.0 when nothing
    was expected. This is the metric that tells you if the right chunk was retrieved at
    all."""
    if not expected_ids:
        return 1.0
    retrieved_set = set(retrieved_ids)
    hits = sum(1 for doc_id in expected_ids if doc_id in retrieved_set)
    return hits / len(expected_ids)


async def _run(business_id: UUID, top_k: int) -> tuple[float, float]:
    # Guarded import: Stage 5 may not be merged when someone first reads this script.
    try:
        from src.core.db import async_session_factory
        from src.retrieval.service import retrieve
    except ImportError as exc:  # pragma: no cover - depends on merge state
        raise SystemExit(
            "Retrieval layer (src/retrieval/service.retrieve) not importable yet: "
            f"{exc}. This is expected until Stage 5 is merged."
        ) from exc

    cases = _load_golden()
    precisions: list[float] = []
    recalls: list[float] = []

    async with async_session_factory() as session:
        for case in cases:
            question = str(case["question"])
            expected = {str(d) for d in case.get("expected_doc_ids", [])}  # type: ignore[union-attr]
            chunks = await retrieve(session, business_id, question, top_k=top_k)
            retrieved_ids = [c.citation_id() for c in chunks]
            precisions.append(context_precision(retrieved_ids, expected))
            recalls.append(context_recall(retrieved_ids, expected))
            print(
                f"  q={question!r:60.60} "
                f"precision={precisions[-1]:.2f} recall={recalls[-1]:.2f} "
                f"retrieved={retrieved_ids}"
            )

    mean_precision = sum(precisions) / len(precisions)
    mean_recall = sum(recalls) / len(recalls)
    return mean_precision, mean_recall


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-id", type=str, default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-precision", type=float, default=0.6)
    parser.add_argument("--min-recall", type=float, default=0.6)
    args = parser.parse_args()

    cases = _load_golden()
    print(f"Loaded {len(cases)} golden cases from {_GOLDEN_PATH}")

    if args.business_id is None:
        print(
            "No --business-id supplied: format check only (nothing to retrieve against). "
            "Pass an ingested tenant's id to compute real precision/recall."
        )
        return 0

    mean_precision, mean_recall = asyncio.run(
        _run(UUID(args.business_id), args.top_k)
    )
    print(f"\nmean context precision: {mean_precision:.3f} (min {args.min_precision})")
    print(f"mean context recall:    {mean_recall:.3f} (min {args.min_recall})")

    ok = mean_precision >= args.min_precision and mean_recall >= args.min_recall
    if not ok:
        print("FAIL: a retrieval metric is below threshold — this gates the build.")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
