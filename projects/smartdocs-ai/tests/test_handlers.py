import base64
import json

import pytest
from botocore.exceptions import ClientError

import auth
from support import ROOT, load_handler
from fakes import FakeBedrockChat, FakeTable

chat = load_handler("chat_handler", "chat")
upload = load_handler("upload_handler", "upload")

CHUNK = {"text": "ResNet adds skip connections.", "source": "docs/resnet.pdf", "score": 0.81}


def post(body, headers=None, b64=False):
    raw = json.dumps(body) if not isinstance(body, str) else body
    if b64:
        raw = base64.b64encode(raw.encode()).decode()
    return {"body": raw, "isBase64Encoded": b64, "headers": headers or {}}


@pytest.fixture
def wired(monkeypatch):
    model, table = FakeBedrockChat("It adds skip connections."), FakeTable()
    monkeypatch.setattr(chat, "bedrock", model)
    monkeypatch.setattr(chat, "table", table)
    monkeypatch.setattr(chat.retriever, "retrieve", lambda q, top_k=3: [CHUNK])
    return model, table


def test_happy_path_returns_answer_sources_and_saves_both_turns(wired):
    model, table = wired
    res = chat.lambda_handler(post({"question": "What is ResNet?", "session_id": "s1"}), None)
    body = json.loads(res["body"])
    assert res["statusCode"] == 200
    assert body["answer"] == "It adds skip connections." and body["sources"] == ["docs/resnet.pdf"]
    assert [i["role"] for i in table.items] == ["user", "assistant"]
    assert table.items[1]["timestamp"] > table.items[0]["timestamp"] and "ttl" in table.items[0]
    sent = model.calls[0]
    assert sent["modelId"] == "test-model" and "skip connections" in sent["system"][0]["text"]
    assert sent["messages"] == [{"role": "user", "content": [{"text": "What is ResNet?"}]}]
    assert "temperature" not in sent["inferenceConfig"]


def test_followup_sends_history_in_order(wired):
    model, table = wired
    chat.lambda_handler(post({"question": "What is ResNet?", "session_id": "s1"}), None)
    chat.lambda_handler(post({"question": "What problem does it solve?", "session_id": "s1"}), None)
    roles = [m["role"] for m in model.calls[1]["messages"]]
    assert roles == ["user", "assistant", "user"]


def test_base64_body_is_supported(wired):
    assert chat.lambda_handler(post({"question": "hi"}, b64=True), None)["statusCode"] == 200


@pytest.mark.parametrize("body", [{"question": ""}, {"question": "x" * 2001}, {}, "not json", "[1,2]"])
def test_bad_requests_get_400(wired, body):
    assert chat.lambda_handler(post(body), None)["statusCode"] == 400


def test_model_failure_returns_502_and_saves_nothing(wired):
    model, table = wired
    model.error = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "INVALID_PAYMENT_INSTRUMENT"}}, "Converse")
    res = chat.lambda_handler(post({"question": "hi"}), None)
    assert res["statusCode"] == 502 and json.loads(res["body"])["code"] == "AccessDeniedException"
    assert table.items == []


def test_api_key_is_enforced_when_a_secret_is_configured(wired, monkeypatch):
    monkeypatch.setenv("API_KEY_SECRET_ARN", "arn:secret")
    monkeypatch.setattr(auth, "_expected", "s3cret")
    ok = chat.lambda_handler(post({"question": "hi"}, headers={"x-api-key": "s3cret"}), None)
    assert ok["statusCode"] == 200
    for headers in ({}, {"x-api-key": "wrong"}):
        assert chat.lambda_handler(post({"question": "hi"}, headers=headers), None)["statusCode"] == 401


def test_auth_copies_are_identical():
    assert (ROOT / "src/chat/auth.py").read_text() == (ROOT / "src/upload/auth.py").read_text()


# ── upload ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("given,expected", [
    ("report.pdf", "report.pdf"), ("My Report (final).PDF", "My_Report__final_.PDF"),
    ("../../etc/passwd", "passwd.pdf"), ("notes.txt", "notes.txt.pdf"),
])
def test_safe_filename(given, expected):
    assert upload.safe_filename(given) == expected


def test_safe_filename_falls_back_for_empty_or_hidden_names():
    for bad in (None, "", ".pdf", "  "):
        name = upload.safe_filename(bad)
        assert name.endswith(".pdf") and not name.startswith(".") and len(name) > 4


def test_upload_returns_presigned_url_under_docs():
    body = json.loads(upload.lambda_handler(post({"filename": "a b.pdf"}), None)["body"])
    assert body["key"] == "docs/a_b.pdf"
    assert "test-bucket" in body["upload_url"] and "X-Amz-Signature" in body["upload_url"]
    assert upload.lambda_handler(post("nope"), None)["statusCode"] == 400
