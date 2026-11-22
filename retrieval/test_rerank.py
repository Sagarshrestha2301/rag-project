"""Prove the reranker: it reorders the list, keeps k, and changes nothing when off.

Cases: the flag off keeps today's passages untouched, a higher score moves a passage up,
the list is cut to `k`, a passage keeps its BM25 score and gains `rerank`/`bm25_rank`,
ties keep their BM25 order, an empty list stays empty, and the cache key suffix is empty
unless the flag is on.

Usage:
    .venv\\Scripts\\python.exe retrieval\\test_rerank.py
"""

from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from retrieval import rerank  # noqa: E402

FAILURES: list[str] = []
TOTAL = 0


def check(name: str, fn) -> None:
    global TOTAL
    TOTAL += 1
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as exc:
        FAILURES.append(name)
        print(f"  FAIL  {name}: {exc}")


def passage(doc: str, number: int, score: float, text: str) -> dict:
    return {"doc": doc, "page": number, "label": doc.split("_")[0], "ocr": False,
            "score": score, "context": text, "snippet": text[:20]}


PASSAGES = [
    passage("1970_Das_Beliefs.pdf", 6, 11.5, "Terai households and their taboos"),
    passage("1975_Cost_cutting.pdf", 2, 10.1, "cost cutting in the hills"),
    passage("1970_Adhikari_Tehri_Dam.pdf", 1, 9.4, "the Tehri dam project"),
    passage("1993_Marahatta_Floods.pdf", 4, 8.8, "540 mm of rain at Tistung"),
]

# A stand-in for the cross-encoder: the last passage is the only relevant one.
def scorer(question: str, texts: list[str]) -> list[float]:
    assert question.startswith("How much"), question
    return [0.1, 0.2, 0.3, 7.5]


def flag_on() -> None:
    """Turn the reranker on for one case; a no-op list needs it off."""
    os.environ[rerank.FLAG] = "1"


def test_flag_off_is_a_no_op() -> None:
    previous = os.environ.pop(rerank.FLAG, None)
    try:
        assert rerank.enabled() is False
        assert rerank.cache_suffix() == ""
        # No scorer passed: off must not even load the model.
        assert rerank.apply(PASSAGES, "How much", k=4) == PASSAGES
    finally:
        if previous is not None:
            os.environ[rerank.FLAG] = previous


def test_flag_states() -> None:
    for value, expected in (("1", True), ("true", True), ("on", True), ("0", False),
                            ("", False)):
        os.environ[rerank.FLAG] = value
        assert rerank.enabled() is expected, value
    os.environ[rerank.FLAG] = "1"
    assert rerank.cache_suffix().startswith("+rerank"), rerank.cache_suffix()
    os.environ.pop(rerank.FLAG, None)


def test_reorders_by_score() -> None:
    flag_on()
    out = rerank.apply(PASSAGES, "How much", k=4, scorer=scorer)
    assert [p["page"] for p in out] == [4, 1, 2, 6], [p["page"] for p in out]


def test_keeps_k_and_drops_the_rest() -> None:
    flag_on()
    out = rerank.apply(PASSAGES, "How much", k=2, scorer=scorer)
    assert len(out) == 2 and out[0]["page"] == 4, out


def test_passage_fields_survive() -> None:
    flag_on()
    out = rerank.apply(PASSAGES, "How much", k=4, scorer=scorer)
    best = out[0]
    assert best["score"] == 8.8, best["score"]          # BM25 stays the gate's number
    assert best["rerank"] == 7.5 and best["bm25_rank"] == 3, best
    assert best["doc"] == "1993_Marahatta_Floods.pdf" and best["snippet"]
    assert PASSAGES[0].get("rerank") is None, "the input list must not be modified"


def test_ties_keep_bm25_order() -> None:
    flag_on()
    flat = lambda question, texts: [1.0] * len(texts)  # noqa: E731
    out = rerank.apply(PASSAGES, "How much", k=4, scorer=flat)
    assert [p["page"] for p in out] == [6, 2, 1, 4], [p["page"] for p in out]


def test_empty_list() -> None:
    flag_on()
    assert rerank.apply([], "How much", k=4, scorer=scorer) == []


def test_anchor_keeps_bm25_order_in_front() -> None:
    """With CHAT_RERANK_ANCHOR=1 the top BM25 page stays first and only the tail moves."""
    flag_on()
    os.environ["CHAT_RERANK_ANCHOR"] = "1"
    try:
        out = rerank.apply(PASSAGES, "How much", k=4, scorer=scorer)
        assert out[0]["page"] == 6, out[0]               # BM25's own first page
        assert [p["page"] for p in out[1:]] == [4, 1, 2], [p["page"] for p in out]
        assert out[0].get("rerank") is None, "an anchored passage was rescored"
        assert rerank.cache_suffix().endswith("a1"), rerank.cache_suffix()
    finally:
        os.environ.pop("CHAT_RERANK_ANCHOR", None)


def test_anchor_zero_orders_everything() -> None:
    flag_on()
    os.environ["CHAT_RERANK_ANCHOR"] = "0"
    try:
        out = rerank.apply(PASSAGES, "How much", k=4, scorer=scorer)
        assert [p["page"] for p in out] == [4, 1, 2, 6], [p["page"] for p in out]
    finally:
        os.environ.pop("CHAT_RERANK_ANCHOR", None)


def test_depth_never_below_two() -> None:
    os.environ["CHAT_RERANK_DEPTH"] = "1"
    try:
        assert rerank.depth() >= 2, rerank.depth()
        os.environ["CHAT_RERANK_DEPTH"] = "not a number"
        assert rerank.depth() == rerank.DEPTH, rerank.depth()
    finally:
        os.environ.pop("CHAT_RERANK_DEPTH", None)


def main() -> int:
    print("retrieval/test_rerank.py")
    check("flag off: passages untouched, no cache suffix", test_flag_off_is_a_no_op)
    check("flag on: reorders and suffixes the cache key", test_flag_states)
    check("the best passage moves to the front", test_reorders_by_score)
    check("the list is cut to k", test_keeps_k_and_drops_the_rest)
    check("BM25 score, rerank score and rank all survive", test_passage_fields_survive)
    check("ties keep the BM25 order", test_ties_keep_bm25_order)
    check("an empty list stays empty", test_empty_list)
    check("anchor=1 keeps the top BM25 page first", test_anchor_keeps_bm25_order_in_front)
    check("anchor=0 reranks the whole list", test_anchor_zero_orders_everything)
    check("depth has a floor and survives junk", test_depth_never_below_two)
    os.environ.pop(rerank.FLAG, None)
    print(f"\n{TOTAL - len(FAILURES)}/{TOTAL} passed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
