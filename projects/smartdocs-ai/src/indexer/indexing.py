"""Pure FAISS/numpy helpers for the indexer (no AWS calls, so they are unit-testable)."""
import faiss
import numpy as np


def normalize(vector):
    """Scale to unit length. With unit vectors, inner product == cosine similarity."""
    arr = np.asarray(vector, dtype=np.float32)
    return arr / (np.linalg.norm(arr) + 1e-9)     # +1e-9 avoids division by zero


def new_index(dim):
    """Exact (brute-force) inner-product index: simple and fast enough below ~10k chunks."""
    return faiss.IndexFlatIP(dim)


def remove_source(index, meta, source):
    """Drop every chunk that came from `source`, returning (index, meta).

    Makes re-uploading the same PDF idempotent. Without this, every re-upload
    appends duplicate chunks and retrieval returns the same passage three times.
    """
    keep = [i for i, s in enumerate(meta["sources"]) if s != source]
    if len(keep) == len(meta["sources"]):
        return index, meta                                   # nothing to remove
    rebuilt = new_index(index.d)
    if keep:
        vectors = index.reconstruct_n(0, index.ntotal)[keep]
        rebuilt.add(np.ascontiguousarray(vectors, dtype=np.float32))
    new_meta = {
        "chunks": [meta["chunks"][i] for i in keep],
        "sources": [meta["sources"][i] for i in keep],
    }
    return rebuilt, new_meta
