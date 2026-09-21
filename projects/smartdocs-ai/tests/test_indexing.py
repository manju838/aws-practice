import numpy as np

from indexing import new_index, normalize, remove_source


def make(dim=8):
    rng = np.random.default_rng(0)
    vecs = np.vstack([normalize(rng.normal(size=dim)) for _ in range(6)])
    index = new_index(dim)
    index.add(vecs)
    meta = {"chunks": [f"c{i}" for i in range(6)],
            "sources": ["docs/a.pdf"] * 3 + ["docs/b.pdf"] * 3}
    return index, meta, vecs


def test_normalize_gives_unit_length():
    assert abs(np.linalg.norm(normalize([3.0, 4.0])) - 1.0) < 1e-6


def test_remove_source_drops_only_that_document():
    index, meta, vecs = make()
    index2, meta2 = remove_source(index, meta, "docs/a.pdf")
    assert index2.ntotal == 3 and meta2["chunks"] == ["c3", "c4", "c5"]
    assert set(meta2["sources"]) == {"docs/b.pdf"}
    # the surviving vectors are the right ones, in the right order
    assert np.allclose(index2.reconstruct_n(0, 3), vecs[3:], atol=1e-6)


def test_remove_source_is_a_noop_for_unknown_source():
    index, meta, _ = make()
    index2, meta2 = remove_source(index, meta, "docs/nope.pdf")
    assert index2 is index and meta2 is meta


def test_remove_last_source_leaves_an_empty_index():
    index, meta, _ = make()
    index, meta = remove_source(index, meta, "docs/a.pdf")
    index, meta = remove_source(index, meta, "docs/b.pdf")
    assert index.ntotal == 0 and meta == {"chunks": [], "sources": []}


def test_reupload_does_not_duplicate():
    index, meta, vecs = make()
    index, meta = remove_source(index, meta, "docs/a.pdf")     # what the indexer does before adding
    index.add(vecs[:3])
    meta["chunks"] += ["c0", "c1", "c2"]
    meta["sources"] += ["docs/a.pdf"] * 3
    assert index.ntotal == 6 and len(meta["chunks"]) == 6
