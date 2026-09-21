"""Shared-secret API key check. IDENTICAL copies live in src/chat and src/upload
(a test enforces that). The key lives in Secrets Manager; the Lambda only gets its ARN.

If API_KEY_SECRET_ARN is not set (early phases), auth is skipped.
"""
import hmac
import os

import boto3

_expected = None


def _expected_key():
    global _expected
    arn = os.environ.get("API_KEY_SECRET_ARN")
    if not arn:
        return None
    if _expected is None:                                   # fetched once per container
        _expected = boto3.client("secretsmanager").get_secret_value(SecretId=arn)["SecretString"]
    return _expected


def is_authorized(event):
    expected = _expected_key()
    if expected is None:
        return True
    supplied = (event.get("headers") or {}).get("x-api-key", "")   # HTTP API lowercases header names
    return hmac.compare_digest(supplied.encode(), expected.encode())
