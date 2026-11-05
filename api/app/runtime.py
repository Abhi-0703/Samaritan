"""The long-lived objects the routers share: Gnani client, LLM service, storage and the worker."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import Settings
from app.db import session_factory
from app.detection.llm_judge import PROMPT_VERSION
from app.services.gnani_client import GnaniBatchClient, client_from_settings
from app.services.llm import build_llm_service
from app.services.llm.service import LLMService
from app.services.pipeline import process_call
from app.storage import get_storage
from app.storage.base import AudioStorage
from app.worker import Worker

log = logging.getLogger("runtime")


@dataclass
class Runtime:
    settings: Settings
    gnani: GnaniBatchClient
    llm: LLMService | None
    storage: AudioStorage
    worker: Worker


def make_worker(settings: Settings, gnani: GnaniBatchClient, llm: LLMService | None, storage: AudioStorage) -> Worker:
    def process(session: Session, call_id: uuid.UUID) -> None:
        process_call(session, call_id, gnani, llm, storage, settings)

    return Worker(session_factory(), process)


def build_runtime(settings: Settings) -> Runtime:
    gnani = client_from_settings(settings)
    llm: LLMService | None = None
    if settings.groq_api_key.get_secret_value() or settings.gemini_api_key.get_secret_value():
        try:
            llm = build_llm_service(settings, PROMPT_VERSION)
        except ValueError as e:
            log.warning("LLM disabled: %s", e)
    else:
        log.warning("No LLM key is set; calls will be analysed with keyword rules only.")
    storage = get_storage()
    return Runtime(settings, gnani, llm, storage, make_worker(settings, gnani, llm, storage))
