"""Offline Ragas runner STUB: faithfulness / answer-relevancy / context-precision over the
golden set (llm-evals-standards). Ragas is intentionally NOT installed in the running image
(see pyproject.toml `evals-offline` extra) because it pulls a heavy datasets/LLM stack that
bloats the API/worker container and flakes in CI. This is a standalone offline tool, run in
the eval/CI environment only.

Install the extra first:
    pip install -e '.[evals-offline]'

Then run (needs an LLM + embedding key in the environment for the judge, and a retrieval
layer + ingested tenant to produce contexts/answers):
    python scripts/eval_ragas.py --business-id <uuid>

This file is a documented scaffold, not a finished evaluator: it wires the golden set into a
Ragas EvaluationDataset shape and shows where the retrieval/generation calls plug in, so the
real runner is a fill-in-the-blanks rather than a from-scratch build. It fails LOUDLY with
install instructions if `ragas` is missing — it never silently no-ops.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_GOLDEN_PATH = Path(__file__).resolve().parent.parent / "evals" / "golden_dataset.json"


def _require_ragas() -> None:
    try:
        import ragas  # noqa: F401
    except ImportError:
        print(
            "ragas is not installed. It is deliberately excluded from the running image.\n"
            "Install the offline eval extra in your eval/CI environment:\n"
            "    pip install -e '.[evals-offline]'\n",
            file=sys.stderr,
        )
        raise SystemExit(2) from None


def main() -> int:
    _require_ragas()

    data = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    print(f"Loaded {len(cases)} golden cases for Ragas evaluation.")

    # --- Where the real runner plugs in (left as a documented scaffold) ---
    # For each case:
    #   1. contexts = await retrieve(session, business_id, question)  # Stage 5
    #   2. answer   = await generate(question, contexts)              # Stage 6 agent
    #   3. record {question, answer, contexts, ground_truth=expected_answer}
    # Then build a ragas EvaluationDataset and run:
    #   from ragas import evaluate
    #   from ragas.metrics import faithfulness, answer_relevancy, context_precision
    #   result = evaluate(dataset, metrics=[faithfulness, answer_relevancy, context_precision])
    # and gate on result scores (faithfulness is the hallucination metric — a drop there is
    # a regression even if relevancy rises).
    print(
        "Ragas runner stub: assemble contexts/answers via the retrieval + agent layers, "
        "then call ragas.evaluate with faithfulness/answer_relevancy/context_precision and "
        "gate on the scores. See the inline scaffold in this file."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
