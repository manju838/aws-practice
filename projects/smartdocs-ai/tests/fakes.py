"""Tiny in-memory stand-ins for S3, Bedrock and DynamoDB (no AWS, no network)."""
import hashlib
import io
import json
import zlib

import numpy as np
from botocore.exceptions import ClientError


class FakeS3:
    class exceptions:                       # mirrors client.exceptions.NoSuchKey
        class NoSuchKey(Exception):
            pass

    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body):
        self.objects[Key] = Body.encode() if isinstance(Body, str) else bytes(Body)

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise self.exceptions.NoSuchKey(Key)
        data = self.objects[Key]
        return {"Body": io.BytesIO(data), "ETag": f'"{hashlib.md5(data).hexdigest()}"'}

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject")
        return {"ETag": f'"{hashlib.md5(self.objects[Key]).hexdigest()}"'}


def fake_embedding(text, dim=1024):
    """Bag-of-words hashing: texts sharing words get similar vectors. Deterministic."""
    vec = np.zeros(dim, dtype=np.float32)
    for word in text.lower().split():
        vec[zlib.crc32(word.encode()) % dim] += 1.0
    return vec.tolist()


class FakeBedrockEmbeddings:
    def invoke_model(self, modelId, body):
        text = json.loads(body)["inputText"]
        return {"body": io.BytesIO(json.dumps({"embedding": fake_embedding(text)}).encode())}


class FakeBedrockChat:
    """Records the request; replies with a canned Converse response or raises."""
    def __init__(self, answer="The answer.", error=None):
        self.answer, self.error, self.calls = answer, error, []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"output": {"message": {"role": "assistant", "content": [{"text": self.answer}]}},
                "usage": {"inputTokens": 100, "outputTokens": 20}}


class FakeTable:
    """One conversation's worth of items, oldest first."""
    def __init__(self, items=None):
        self.items = list(items or [])

    def query(self, KeyConditionExpression, ScanIndexForward, Limit):
        rows = list(reversed(self.items)) if not ScanIndexForward else list(self.items)
        return {"Items": rows[:Limit]}

    def put_item(self, Item):
        self.items.append(Item)
