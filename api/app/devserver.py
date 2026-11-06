"""A local API server with fake Gnani and a fake language model. For developing and demonstrating the web app
without spending credits or needing keys. Never used in production.

    python -m app.devserver            # http://localhost:8000, data in api/.data/dev/

Every upload "transcribes" a short canned conversation that contains one false-threat line, so the whole flow
(queued, transcribing, analysing, done, a flagged moment) can be seen. Set DEMO_MODE=true and UPLOAD_PASSCODE to try
the passcode.
"""

from __future__ import annotations

import os
import time

from app.config import API_DIR

DEV_DIR = API_DIR / ".data" / "dev"
DEV_DIR.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{DEV_DIR / 'dev.db'}"
os.environ["LOCAL_AUDIO_DIR"] = str(DEV_DIR / "audio")
os.environ.setdefault("ADMIN_TOKEN", "dev-admin-token")
os.environ["WORKER_ENABLED"] = "true"

from app.config import Settings, get_settings  # noqa: E402
from app.db import session_scope  # noqa: E402
from app.detection.llm_judge import PROMPT_VERSION  # noqa: E402
from app.main import create_app  # noqa: E402
from app.runtime import Runtime, make_worker  # noqa: E402
from app.services.gnani_client import GnaniBatchClient  # noqa: E402
from app.services.llm.cache import DbLlmCache  # noqa: E402
from app.services.llm.limiter import TokenLimiter  # noqa: E402
from app.services.llm.service import LLMService  # noqa: E402
from app.storage import get_storage  # noqa: E402
from tests.fakes.gnani_fake import FakeGnani  # noqa: E402
from tests.fakes.llm_fake import FakeProvider, answer, flag  # noqa: E402

SEGMENTS = [
    (0.0, 4.2, 1, "Namaste, main Rohit Patil bol raha hoon Sahyog Finance se."),
    (4.4, 6.0, 2, "Haan ji, boliye. Mera number 9876543210 hai."),
    (6.2, 12.5, 1, "Sir, aapke personal loan ki EMI pending hai, 5500 rupaye. Kab tak ho payega?"),
    (12.8, 16.0, 2, "Agle hafte tak kar dunga."),
    (16.4, 24.0, 1, "Agle hafte nahi, kal tak bharo, nahi toh main aapke padosiyon ko bata dunga ki aap defaulter ho."),
    (24.5, 27.0, 2, "Aisa mat kijiye, main kal bhar dunga."),
]


def dev_runtime(settings: Settings) -> Runtime:
    fake = FakeGnani(api_key=settings.gnani_api_key.get_secret_value() or "dev-key")
    fake.default_segments = SEGMENTS
    fake.on_request = lambda method, path: time.sleep(1.5) if path.endswith("/start") else None
    gnani = GnaniBatchClient("https://api.vachana.ai", fake.api_key, http=fake.client(), sleep=lambda s: time.sleep(1))
    provider = FakeProvider(
        "dev-llm", "fake", [answer([flag("V5", 4, "padosiyon ko bata dunga", why="Threatens to disclose the debt.")])]
    )
    provider.on_call = lambda: time.sleep(1.5)
    llm = LLMService(
        provider, None, {provider.name: TokenLimiter(1000, 10_000_000)},
        DbLlmCache(session_scope, False), PROMPT_VERSION,
    )  # fmt: skip
    storage = get_storage()
    return Runtime(settings, gnani, llm, storage, make_worker(settings, gnani, llm, storage))


app = create_app(dev_runtime)

if __name__ == "__main__":
    import uvicorn

    get_settings.cache_clear()
    uvicorn.run("app.devserver:app", host="127.0.0.1", port=8000, log_level="info")
