"""Slug generation for new businesses.

The slug lands in a unique-indexed column, so `_slugify` must never return something that
would break the insert — most importantly never an empty string, which is why the fallback
exists. `create_business` handles collisions by retrying with a random suffix
(tests/businesses/test_businesses.py covers that path); this file pins the pure transform."""

import pytest

from src.businesses.service import _slugify


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Acme", "acme"),
        ("Acme Inc", "acme-inc"),
        ("ACME INC", "acme-inc"),
        ("Acme  Inc", "acme-inc"),
        ("Acme, Inc.", "acme-inc"),
        ("Acme & Co", "acme-co"),
        ("  Acme Inc  ", "acme-inc"),
        ("Acme-Inc", "acme-inc"),
        ("Acme_Inc", "acme-inc"),
        ("Acme 2000", "acme-2000"),
        ("acme.com", "acme-com"),
        ("Acme/Widgets", "acme-widgets"),
    ],
)
def test_slugify_produces_a_url_safe_slug(name: str, expected: str) -> None:
    assert _slugify(name) == expected


def test_slugify_collapses_runs_of_punctuation_into_one_separator() -> None:
    assert _slugify("Acme !!! Inc") == "acme-inc"


def test_slugify_strips_leading_and_trailing_separators() -> None:
    assert _slugify("---Acme---") == "acme"
    assert _slugify("!!!Acme???") == "acme"


@pytest.mark.parametrize("name", ["", "   ", "!!!", "---", "...", "@#$%"])
def test_slugify_falls_back_rather_than_returning_an_empty_slug(name: str) -> None:
    # An empty slug would violate the unique index in a way that the
    # retry-on-conflict loop could never resolve.
    assert _slugify(name) == "business"


def test_slugify_falls_back_for_a_purely_non_ascii_name() -> None:
    # The character class is [a-z0-9] only, so a fully non-Latin name reduces to
    # nothing and must take the fallback.
    assert _slugify("日本語") == "business"


def test_slugify_keeps_the_ascii_portion_of_a_mixed_name() -> None:
    assert _slugify("Acme 日本語 Inc") == "acme-inc"


def test_slugify_output_contains_only_slug_safe_characters() -> None:
    for name in ["Acme, Inc.", "  A & B  ", "Ünïcödé Ltd", "100% Pure"]:
        slug = _slugify(name)
        assert slug
        assert all(ch in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in slug), slug
        assert not slug.startswith("-")
        assert not slug.endswith("-")


def test_slugify_is_idempotent() -> None:
    once = _slugify("Acme, Inc.")

    assert _slugify(once) == once
