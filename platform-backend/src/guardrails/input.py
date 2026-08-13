"""Input guardrails — everything that screens what reaches the model.

Pure, unit-testable functions with no I/O. Layers (in order applied by the agent/chat
layer): size/shape limits (Pydantic + `enforce_size`), PII redaction, prompt-injection /
jailbreak screening, and a scope/topic check. Per llm-guardrails-standards these run
*before* a generation call is spent, and they fail closed: on a detected attack we raise
`GuardrailBlocked` rather than pass through.

Retrieved chunks are untrusted data too — `redact_pii` / `screen_injection` are reused to
sanitise retrieved content before it is delimited into the prompt (never as instructions).
No presidio (not installed); PII detection is regex/heuristic.
"""

import re

from src.core.exceptions import GuardrailBlocked

# Enforced here in addition to the Pydantic `max_length` so service-layer / retrieved-text
# callers that don't go through the request schema still get a bound.
MAX_INPUT_CHARS = 4_000

# --- PII patterns (regex/heuristic — deliberately conservative, no presidio) ----------
_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    # E.164-ish and common separated forms; require >= 10 digits to avoid nuking prices.
    ("PHONE", re.compile(r"(?<!\d)(?:\+?\d[\s.-]?){10,15}(?!\d)")),
    ("SSN", re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")),
    # 13-16 digit card-like runs (allowing spaces/dashes between groups).
    ("CREDIT_CARD", re.compile(r"(?<!\d)(?:\d[ -]?){13,16}(?!\d)")),
]

# --- Prompt-injection / jailbreak heuristics ------------------------------------------
# These match the classic override attempts. Case-insensitive substring/regex screen.
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(?:all\s+)?(?:your\s+)?(?:previous|prior|above)\s+instructions", re.I),
    re.compile(r"disregard\s+(?:all\s+)?(?:your\s+)?(?:previous|prior|above)", re.I),
    re.compile(r"forget\s+(?:all\s+)?(?:your\s+)?(?:previous|prior|above|earlier)", re.I),
    re.compile(r"you\s+are\s+now\s+(?:a|an|in)\b", re.I),
    re.compile(r"\bdeveloper\s+mode\b", re.I),
    re.compile(r"\bjailbreak\b", re.I),
    re.compile(r"\bDAN\b"),
    re.compile(r"pretend\s+(?:to\s+be|you\s+are)", re.I),
    re.compile(r"reveal\s+(?:your\s+)?(?:system\s+)?prompt", re.I),
    re.compile(r"(?:system|assistant)\s*[:>]\s", re.I),
    re.compile(r"</?(?:system|instructions?)>", re.I),
    re.compile(
        r"act\s+as\s+(?:if\s+you\s+are\s+)?(?:a|an|the)\s+(?:unrestricted|unfiltered)", re.I
    ),
]


def enforce_size(text: str, *, max_chars: int = MAX_INPUT_CHARS) -> str:
    """Reject oversized/empty input before it reaches the model. Fail closed."""
    stripped = text.strip()
    if not stripped:
        raise GuardrailBlocked("Message must not be empty.")
    if len(text) > max_chars:
        raise GuardrailBlocked("Message is too long.")
    return stripped


def redact_pii(text: str) -> str:
    """Mask PII with typed placeholders (e.g. ``[REDACTED_EMAIL]``) so it never reaches
    the model or the logs. Pure/idempotent-ish; order matters (email before phone so an
    email's digits aren't misread as a phone number)."""
    redacted = text
    for label, pattern in _PII_PATTERNS:
        redacted = pattern.sub(f"[REDACTED_{label}]", redacted)
    return redacted


def contains_pii(text: str) -> bool:
    return any(pattern.search(text) for _, pattern in _PII_PATTERNS)


def detect_injection(text: str) -> bool:
    """True if the text matches a known prompt-injection / jailbreak pattern."""
    return any(pattern.search(text) for pattern in _INJECTION_PATTERNS)


def screen_injection(text: str) -> None:
    """Fail-closed screen for user input: raise `GuardrailBlocked` on a detected attack."""
    if detect_injection(text):
        raise GuardrailBlocked("Message contains a disallowed instruction pattern.")


def sanitize_retrieved(text: str) -> str:
    """Neutralise a retrieved chunk before it is delimited into the prompt as *data*.

    Retrieved documents are untrusted (they may carry planted 'ignore your instructions'
    payloads). We don't block the whole turn on a poisoned chunk — that would let an
    attacker DoS a tenant by uploading a document — instead we defang injection markers so
    the model treats the content as inert data. PII in retrieved content is also masked.
    """
    cleaned = redact_pii(text)
    for pattern in _INJECTION_PATTERNS:
        cleaned = pattern.sub("[filtered]", cleaned)
    return cleaned


def check_scope(text: str, *, min_meaningful_chars: int = 2) -> None:
    """Cheap out-of-domain / degenerate-input screen run before a generation call.

    We deliberately keep this narrow: it rejects clearly non-answerable input (empty after
    stripping punctuation). Genuine topic classification is the retrieval layer's job — if
    nothing relevant is retrieved, the agent's groundedness gate produces the honest
    "I don't have enough information" fallback, so we don't pre-emptively refuse on-topic
    questions we can't cheaply classify here.
    """
    meaningful = re.sub(r"[^\w]", "", text)
    if len(meaningful) < min_meaningful_chars:
        raise GuardrailBlocked("Message does not contain an answerable question.")


def screen_input(text: str, *, max_chars: int = MAX_INPUT_CHARS) -> str:
    """Run the full input guardrail chain and return the sanitised (size-checked,
    PII-redacted) query. Any failure raises `GuardrailBlocked` (fail closed)."""
    sized = enforce_size(text, max_chars=max_chars)
    screen_injection(sized)
    check_scope(sized)
    return redact_pii(sized)
