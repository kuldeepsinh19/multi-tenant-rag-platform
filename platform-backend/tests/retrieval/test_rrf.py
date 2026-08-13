"""Unit tests for `reciprocal_rank_fusion` — a pure function, no DB or network. RRF is
the deterministic merge step of hybrid retrieval; if fusion or dedup is wrong, a relevant
chunk found by only one ranker can be dropped or mis-ordered."""

from uuid import uuid4

from src.retrieval.service import reciprocal_rank_fusion


def test_rrf_dedups_and_ranks_agreed_item_first() -> None:
    a, b, c = uuid4(), uuid4(), uuid4()
    # `a` is top of the dense list and second in the sparse list -> highest fused score.
    dense = [a, b, c]
    sparse = [b, a, c]

    fused = reciprocal_rank_fusion([dense, sparse])

    assert sorted(fused) == sorted({a, b, c})  # dedup: each id appears exactly once
    assert len(fused) == 3
    assert fused[0] == a  # agreed-high item wins


def test_rrf_single_list_preserves_order() -> None:
    ids = [uuid4() for _ in range(4)]
    assert reciprocal_rank_fusion([ids]) == ids


def test_rrf_union_of_disjoint_lists() -> None:
    a, b, c, d = uuid4(), uuid4(), uuid4(), uuid4()
    fused = reciprocal_rank_fusion([[a, b], [c, d]])
    assert set(fused) == {a, b, c, d}
    # Both lists' rank-0 items tie on score; determinism breaks the tie by first appearance.
    assert fused[0] == a
    assert fused.index(a) < fused.index(b)
    assert fused.index(c) < fused.index(d)


def test_rrf_higher_k_still_orders_by_agreement() -> None:
    a, b = uuid4(), uuid4()
    # `a` ranks well in both lists; `b` only in one. `a` must lead regardless of k.
    fused = reciprocal_rank_fusion([[a, b], [a]], k=1)
    assert fused[0] == a


def test_rrf_empty_input() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []
