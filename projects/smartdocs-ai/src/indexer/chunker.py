"""Split text into overlapping word-level chunks."""

CHUNK_SIZE = 300     # words per chunk
CHUNK_OVERLAP = 50   # words shared between neighbouring chunks


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Return a list of overlapping chunks.

    Why overlap? A sentence that straddles a chunk boundary would otherwise be
    cut in half and lose its context. With overlap, every idea appears whole in
    at least one chunk.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")
    words = text.split()
    step = chunk_size - overlap
    chunks = []
    for start in range(0, len(words), step):
        chunk = " ".join(words[start:start + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        if start + chunk_size >= len(words):
            break          # the last chunk already reaches the end; don't emit a tail-only duplicate
    return chunks
