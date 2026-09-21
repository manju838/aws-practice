"""Upload Lambda: hands out short-lived presigned S3 URLs so clients upload PDFs
straight to S3. The file never passes through Lambda or API Gateway (which cap
payloads at 6 MB / 10 MB). The upload lands in docs/ and triggers the indexer.
"""
import base64
import json
import logging
import os
import re
import uuid

import boto3
from botocore.config import Config

import auth

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "ap-south-2")
BUCKET = os.environ["DOCS_BUCKET"]
EXPIRES_IN = 300          # seconds the URL stays valid
MAX_NAME = 100

# Regional endpoint + SigV4 avoids redirect problems with presigned URLs outside us-east-1.
s3 = boto3.client("s3", region_name=REGION, config=Config(signature_version="s3v4"),
                  endpoint_url=f"https://s3.{REGION}.amazonaws.com")


def safe_filename(name):
    """Keep only a plain, safe *.pdf file name: no paths, no odd characters."""
    base = os.path.basename(str(name or "")).strip()
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)[:MAX_NAME]
    if not base or base.startswith("."):
        base = f"{uuid.uuid4().hex[:12]}.pdf"
    if not base.lower().endswith(".pdf"):
        base += ".pdf"
    return base


def respond(status, payload):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(payload)}


def lambda_handler(event, context):
    if not auth.is_authorized(event):
        return respond(401, {"error": "Missing or invalid x-api-key"})
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    try:
        body = json.loads(raw)
        if not isinstance(body, dict):
            raise ValueError
    except ValueError:
        return respond(400, {"error": "Request body must be a JSON object"})

    key = f"docs/{safe_filename(body.get('filename'))}"
    url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": key, "ContentType": "application/pdf"},
        ExpiresIn=EXPIRES_IN,
    )
    logger.info(json.dumps({"msg": "Presigned upload URL issued", "key": key}))
    return respond(200, {
        "upload_url": url, "key": key, "expires_in": EXPIRES_IN,
        "note": "PUT the file to upload_url with header Content-Type: application/pdf",
    })
