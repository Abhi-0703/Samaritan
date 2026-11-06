"""A fake Supabase Storage REST API (httpx MockTransport): upload, download, sign, remove, with the key checked."""

from __future__ import annotations

import json
import re
from urllib.parse import quote

import httpx

SERVICE_KEY = "test-service-role-key-0000"
PROJECT = "https://abc.supabase.co"


class FakeSupabaseStorage:
    def __init__(self, bucket: str = "call-audio") -> None:
        self.bucket = bucket
        self.objects: dict[str, bytes] = {}
        self.requests: list[tuple[str, str]] = []
        self.upsert_headers: list[str | None] = []
        self.fail_with: int | None = None  # next request answers with this status

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handle))

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append((request.method, request.url.path))
        if (
            request.headers.get("authorization") != f"Bearer {SERVICE_KEY}"
            or request.headers.get("apikey") != SERVICE_KEY
        ):
            return httpx.Response(401, json={"message": "Invalid API key"})
        if self.fail_with:
            status, self.fail_with = self.fail_with, None
            return httpx.Response(status, json={"message": "boom"})
        path = request.url.path
        prefix = "/storage/v1/object/"
        if not path.startswith(prefix):
            return httpx.Response(404, json={"message": "no such route"})
        rest = path[len(prefix) :]
        if request.method == "POST" and rest.startswith("sign/"):
            bucket, _, key = rest[len("sign/") :].partition("/")
            if key not in self.objects or bucket != self.bucket:
                return httpx.Response(400, json={"message": "Object not found"})
            assert json.loads(request.content) == {"expiresIn": 3600}
            return httpx.Response(200, json={"signedURL": f"/object/sign/{bucket}/{quote(key)}?token=tok123"})
        if request.method == "DELETE" and "/" not in rest:
            for k in json.loads(request.content)["prefixes"]:
                self.objects.pop(k, None)
            return httpx.Response(200, json=[])
        bucket, _, key = rest.partition("/")
        if bucket != self.bucket:
            return httpx.Response(404, json={"message": "Bucket not found"})
        if request.method == "POST":
            self.upsert_headers.append(request.headers.get("x-upsert"))
            self.objects[key] = bytes(request.content)
            return httpx.Response(200, json={"Key": f"{bucket}/{key}"})
        if request.method == "GET":
            if key not in self.objects:
                return httpx.Response(400, json={"message": "Object not found"})
            return httpx.Response(200, content=self.objects[key])
        return httpx.Response(405, json={"message": re.sub(r"\W", "", request.method)})
