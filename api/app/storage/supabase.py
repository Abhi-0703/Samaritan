"""Audio in a private Supabase Storage bucket, over the Storage REST API (no extra SDK).

The service-role key stays on the server. The browser only ever gets a signed URL that expires (about an hour), so the
bucket can stay private. Endpoints (as supabase-js uses them): upload `POST /object/{bucket}/{path}` with
`x-upsert`, signed URL `POST /object/sign/{bucket}/{path}`, download `GET /object/{bucket}/{path}`, remove
`DELETE /object/{bucket}` with `{"prefixes": [...]}`; all under `{SUPABASE_URL}/storage/v1`.
"""

from __future__ import annotations

import mimetypes
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import httpx

SIGNED_URL_SECONDS = 3600


class StorageError(RuntimeError):
    """A Supabase Storage call failed. The message never contains the key."""


class SupabaseStorage:
    def __init__(
        self,
        project_url: str,
        service_key: str,
        bucket: str,
        http: httpx.Client | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        if not project_url or not service_key:
            raise StorageError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set for the supabase backend.")
        self.base = project_url.rstrip("/") + "/storage/v1"
        self.bucket = bucket
        self._headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}
        self._http = http or httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))
        self._cache = cache_dir or Path(tempfile.gettempdir()) / "samaritan-audio"
        self._cache.mkdir(parents=True, exist_ok=True)

    # -- helpers ---------------------------------------------------------------------------------------------------

    def _object(self, key: str) -> str:
        return f"{self.base}/object/{self.bucket}/{quote(key, safe='/')}"

    def _check(self, res: httpx.Response, what: str) -> httpx.Response:
        if res.is_success:
            return res
        detail = ""
        try:
            body = res.json()
            detail = str(body.get("message") or body.get("error") or "")[:160]
        except ValueError:
            pass
        raise StorageError(f"Supabase Storage could not {what} (HTTP {res.status_code}). {detail}".strip())

    # -- the AudioStorage interface ----------------------------------------------------------------------------------

    def save(self, call_id: str, source: Path, filename: str) -> str:
        suffix = Path(filename).suffix.lower() or ".wav"
        key = f"{call_id}{suffix}"
        content_type = mimetypes.guess_type(f"x{suffix}")[0] or "application/octet-stream"
        with source.open("rb") as fh:
            res = self._http.post(
                self._object(key),
                content=fh.read(),
                headers={**self._headers, "Content-Type": content_type, "x-upsert": "true"},
            )
        self._check(res, "store the audio")
        return key

    def local_path(self, key: str) -> Path:
        """Downloads the object to a temporary file and returns its path (the pipeline needs a real file)."""
        path = self._cache / key.replace("/", "_")
        if path.exists() and path.stat().st_size:
            return path
        res = self._check(self._http.get(self._object(key), headers=self._headers), "download the audio")
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(res.content)
        tmp.replace(path)
        return path

    def url(self, call_id: str, key: str) -> tuple[str, datetime | None]:
        res = self._http.post(
            f"{self.base}/object/sign/{self.bucket}/{quote(key, safe='/')}",
            json={"expiresIn": SIGNED_URL_SECONDS},
            headers=self._headers,
        )
        signed = self._check(res, "sign the audio URL").json().get("signedURL")
        if not signed:
            raise StorageError("Supabase Storage returned no signed URL.")
        return self.base + signed, datetime.now(UTC) + timedelta(seconds=SIGNED_URL_SECONDS - 30)

    def delete(self, key: str) -> None:
        res = self._http.request(
            "DELETE", f"{self.base}/object/{self.bucket}", json={"prefixes": [key]}, headers=self._headers
        )
        self._check(res, "delete the audio")
        (self._cache / key.replace("/", "_")).unlink(missing_ok=True)
