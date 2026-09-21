"""Chat Lambda: the full RAG loop.

  retrieve -> load history -> build prompt -> ask Claude -> save history -> return
"""
import base64
import json
import logging
import os
import time
import uuid

import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config
from botocore.exceptions import ClientError

import auth
import prompting
import retriever

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def log(msg, **fields):
    logger.info(json.dumps({"msg": msg, **fields}))


REGION = os.environ.get("AWS_REGION", "ap-south-2")
MODEL_ID = os.environ["CHAT_MODEL_ID"]
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "1000"))
TEMPERATURE = os.environ.get("TEMPERATURE", "")      # empty = model default (some newer models reject it)
TOP_K = int(os.environ.get("TOP_K", "3"))
HISTORY_LIMIT = 10                                   # last N stored messages sent back to the model
TTL_DAYS = 7                                         # DynamoDB deletes old conversations for free

bedrock = boto3.client(
    "bedrock-runtime", region_name=REGION,
    config=Config(retries={"max_attempts": 4, "mode": "adaptive"}, read_timeout=60),
)
table = boto3.resource("dynamodb", region_name=REGION).Table(os.environ["CONVERSATIONS_TABLE"])


def respond(status, payload):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(payload)}


def parse_body(event):
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError("Request body must be JSON") from e
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")
    return body


def load_history(session_id):
    resp = table.query(
        KeyConditionExpression=Key("session_id").eq(session_id),
        ScanIndexForward=False,          # newest first...
        Limit=HISTORY_LIMIT,
    )
    return list(reversed(resp.get("Items", [])))     # ...then back to chronological order


def save_turn(session_id, question, answer):
    now_ms = int(time.time() * 1000)
    ttl = int(time.time()) + TTL_DAYS * 86400
    for offset, role, content in ((0, "user", question), (1, "assistant", answer)):
        table.put_item(Item={
            "session_id": session_id, "timestamp": now_ms + offset,
            "role": role, "content": content, "ttl": ttl,
        })


def lambda_handler(event, context):
    started = time.time()
    request_id = getattr(context, "aws_request_id", str(uuid.uuid4()))

    if not auth.is_authorized(event):
        log("Unauthorized", request_id=request_id)
        return respond(401, {"error": "Missing or invalid x-api-key"})

    try:
        body = parse_body(event)
    except ValueError as e:
        return respond(400, {"error": str(e)})
    question = str(body.get("question") or "").strip()
    session_id = str(body.get("session_id") or "default")[:100]
    if not question or len(question) > 2000:
        return respond(400, {"error": "'question' is required and must be under 2000 characters"})

    history = load_history(session_id)
    chunks = retriever.retrieve(prompting.retrieval_query(history, question), top_k=TOP_K)

    request = {
        "modelId": MODEL_ID,
        "system": [{"text": prompting.build_system_prompt(chunks)}],
        "messages": prompting.build_messages(history, question),
        "inferenceConfig": {"maxTokens": MAX_TOKENS},
    }
    if TEMPERATURE:
        request["inferenceConfig"]["temperature"] = float(TEMPERATURE)

    try:
        resp = bedrock.converse(**request)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        log("Model call failed", request_id=request_id, session_id=session_id, model=MODEL_ID,
            error_code=code, error=e.response["Error"].get("Message", ""))
        return respond(502, {"error": "The model call failed", "code": code})

    answer = prompting.extract_text(resp)
    save_turn(session_id, question, answer)

    usage = resp.get("usage", {})
    log("Request complete", request_id=request_id, session_id=session_id, model=MODEL_ID,
        duration_ms=round((time.time() - started) * 1000), chunks=len(chunks),
        top_score=chunks[0]["score"] if chunks else None,
        input_tokens=usage.get("inputTokens"), output_tokens=usage.get("outputTokens"))

    return respond(200, {
        "answer": answer, "session_id": session_id,
        "sources": sorted({c["source"] for c in chunks}), "model": MODEL_ID,
    })
