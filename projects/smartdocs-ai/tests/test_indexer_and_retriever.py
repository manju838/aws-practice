"""Round trip: real PDF -> indexer -> fake S3 -> retriever. Covers dedup and cache refresh."""
import json

import pymupdf
import pytest

from support import load_handler
from fakes import FakeBedrockEmbeddings, FakeS3, fake_embedding

indexer = load_handler("indexer_handler", "indexer")
import retriever  # noqa: E402  (src/chat is on sys.path via conftest)


def make_pdf(text):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 550, 780), text, fontsize=11)
    return doc.tobytes()


def event(key):
    return {"Records": [{"s3": {"object": {"key": key}}}]}


@pytest.fixture
def world(monkeypatch):
    s3 = FakeS3()
    monkeypatch.setattr(indexer, "s3", s3)
    monkeypatch.setattr(indexer, "embed", fake_embedding)
    monkeypatch.setattr(retriever, "s3", s3)
    monkeypatch.setattr(retriever, "bedrock", FakeBedrockEmbeddings())
    monkeypatch.setitem(retriever._cache, "index", None)
    monkeypatch.setitem(retriever._cache, "etag", None)
    return s3


RESNET = "Residual networks use skip connections so very deep networks can be trained without degradation."
POTATO = "Roasting potatoes needs high heat and plenty of oil for a crispy golden crust."


def test_index_then_retrieve_finds_the_right_document(world):
    world.put_object("b", "docs/resnet.pdf", make_pdf(RESNET))
    world.put_object("b", "docs/potato.pdf", make_pdf(POTATO))
    indexer.lambda_handler(event("docs/resnet.pdf"), None)
    indexer.lambda_handler(event("docs/potato.pdf"), None)

    hits = retriever.retrieve("skip connections deep networks trained", top_k=3)
    assert hits and hits[0]["source"] == "docs/resnet.pdf"
    assert all(h["score"] >= retriever.MIN_SCORE for h in hits)


def test_reupload_replaces_instead_of_duplicating(world):
    world.put_object("b", "docs/resnet.pdf", make_pdf(RESNET))
    for _ in range(3):
        indexer.lambda_handler(event("docs/resnet.pdf"), None)
    meta = json.loads(world.objects["index/metadata.json"])
    assert meta["sources"].count("docs/resnet.pdf") == len(meta["chunks"]) == 1


def test_url_encoded_keys_are_decoded(world):
    world.put_object("b", "docs/my file.pdf", make_pdf(RESNET))
    out = indexer.lambda_handler(event("docs/my+file.pdf"), None)      # how S3 sends it
    assert json.loads(out["body"])[0]["source"] == "docs/my file.pdf"


def test_non_docs_keys_are_ignored(world):
    out = indexer.lambda_handler(event("index/faiss.index"), None)
    assert json.loads(out["body"]) == [] and "index/faiss.index" not in world.objects


def test_pdf_without_text_indexes_nothing(world):
    doc = pymupdf.open(); doc.new_page()
    world.put_object("b", "docs/blank.pdf", doc.tobytes())
    out = indexer.lambda_handler(event("docs/blank.pdf"), None)
    assert json.loads(out["body"])[0]["indexed_chunks"] == 0
    assert "index/faiss.index" not in world.objects


def test_retriever_picks_up_a_newer_index_in_a_warm_container(world):
    assert retriever.retrieve("skip connections") == []                # nothing indexed yet
    world.put_object("b", "docs/resnet.pdf", make_pdf(RESNET))
    indexer.lambda_handler(event("docs/resnet.pdf"), None)
    assert retriever.retrieve("skip connections")                      # first load
    world.put_object("b", "docs/potato.pdf", make_pdf(POTATO))
    indexer.lambda_handler(event("docs/potato.pdf"), None)
    hits = retriever.retrieve("crispy potatoes oil heat")      # same warm cache, must reload
    assert hits and hits[0]["source"] == "docs/potato.pdf"
