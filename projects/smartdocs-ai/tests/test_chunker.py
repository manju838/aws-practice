import pytest

from chunker import chunk_text


def test_produces_multiple_chunks():
    assert len(chunk_text(" ".join(["word"] * 1000))) == 4


def test_overlap_is_working():
    words = [str(i) for i in range(700)]
    chunks = chunk_text(" ".join(words), chunk_size=300, overlap=50)
    assert chunks[0].split()[-1] in chunks[1].split()[:50]


def test_empty_text_gives_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_short_text_is_one_chunk_without_a_duplicate_tail():
    assert len(chunk_text(" ".join(["w"] * 300))) == 1
    assert len(chunk_text(" ".join(["w"] * 10))) == 1


def test_every_word_is_covered():
    words = [str(i) for i in range(1234)]
    joined = " ".join(chunk_text(" ".join(words)))
    assert all(w in joined.split() for w in words)


def test_bad_overlap_is_rejected():
    with pytest.raises(ValueError):
        chunk_text("a b c", chunk_size=10, overlap=10)
