#!/usr/bin/env python3
"""End-to-end smoke test of a running Samaritan API (standard library only).

    python3 scripts/smoke.py                                  # read-only checks against http://localhost:8000
    python3 scripts/smoke.py --base-url https://api.example.com
    python3 scripts/smoke.py --upload --passcode SECRET       # also uploads a synthetic 20 s tone and waits

The read-only checks cost nothing. `--upload` queues a real call, which on a live server spends Gnani and LLM
credits, so it is off unless asked for.
"""

from __future__ import annotations

import argparse
import io
import json
import struct
import sys
import time
import uuid
import wave
from urllib import error, request


def call(base: str, method: str, path: str, headers: dict | None = None, data: bytes | None = None):
    req = request.Request(base + path, data=data, method=method, headers=headers or {})
    try:
        with request.urlopen(req, timeout=60) as res:
            return res.status, json.loads(res.read() or b"null")
    except error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def tone_wav(seconds: int = 20, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", 3000 if (i // 40) % 2 else -3000) for i in range(rate * seconds)))
    return buf.getvalue()


def multipart(fields: dict[str, str], filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body = b""
    for name, value in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{filename}"\r\n'
        "Content-Type: audio/wav\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--upload", action="store_true", help="also upload a synthetic call (spends credits on a live server)")
    p.add_argument("--passcode", default="", help="X-Upload-Passcode for demo mode")
    p.add_argument("--wait-minutes", type=float, default=6)
    args = p.parse_args()
    base = args.base_url.rstrip("/")
    failures = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        failures += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {name}" + (f": {detail}" if detail else ""))

    status, body = call(base, "GET", "/health")
    check("health", status == 200 and body == {"status": "ok"}, f"{status}")
    status, rules = call(base, "GET", "/rules")
    check("nine rules", status == 200 and len(rules) == 9)
    status, overview = call(base, "GET", "/stats/overview")
    check("overview", status == 200 and "calls_audited" in overview, f"{overview.get('calls_audited')} audited")
    status, page = call(base, "GET", "/calls?page_size=5")
    check("list calls", status == 200 and "items" in page, f"{page.get('total')} calls")
    done = next((c for c in page.get("items", []) if c["status"] == "done"), None)
    if done:
        status, detail = call(base, "GET", f"/calls/{done['id']}")
        check("open a finished call", status == 200 and detail["segments"], f"{len(detail['segments'])} segments")
        status, audio = call(base, "GET", f"/calls/{done['id']}/audio")
        check("audio url", status == 200 and audio["url"].startswith("http"))
    else:
        print("skip open a call: no finished call yet")
    status, ev = call(base, "GET", "/eval/latest")
    check("accuracy data", status == 200 and set(ev) == {"rules_only", "rules_plus_llm"})
    status, err = call(base, "GET", "/calls/not-a-call")
    check("error envelope", status == 404 and err["error"]["code"] == "not_found")

    if args.upload:
        meta = [{"filename": "smoke.wav", "agent_name": "Smoke Test", "called_at": "2026-11-03T11:20:00+05:30",
                 "language": "hinglish", "loan_ref": "SMOKE-001"}]  # fmt: skip
        body, ctype = multipart({"metadata": json.dumps(meta)}, "smoke.wav", tone_wav())
        headers = {"Content-Type": ctype}
        if args.passcode:
            headers["X-Upload-Passcode"] = args.passcode
        status, created = call(base, "POST", "/calls/upload", headers, body)
        check("upload", status == 200 and created and created[0]["status"] == "queued", f"{status}")
        if status == 200:
            cid, deadline = created[0]["id"], time.time() + args.wait_minutes * 60
            state = "queued"
            while time.time() < deadline and state not in ("done", "failed"):
                time.sleep(5)
                _, c = call(base, "GET", f"/calls/{cid}")
                state = c["status"]
            check("call reaches a final status", state in ("done", "failed"), state)
            check("call finished without error", state == "done", (c.get("error") or "") if state != "done" else "")
    print("passed" if not failures else f"{failures} check(s) failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
