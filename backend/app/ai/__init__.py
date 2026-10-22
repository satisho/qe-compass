"""Provider registry. Add new providers here and select one with QEC_AI_PROVIDER."""
from __future__ import annotations

import logging
from functools import lru_cache

from ..config import settings
from .base import AIProvider
from .rules import RulesProvider

log = logging.getLogger(__name__)

PROVIDERS: dict[str, type] = {
    "rules": RulesProvider,
    # "llm": LLMProvider,   # e.g. an adapter for Claude, Azure OpenAI or a self-hosted model
}


@lru_cache(maxsize=1)
def get_provider() -> AIProvider:
    cls = PROVIDERS.get(settings.ai_provider)
    if cls is None:
        log.warning("Unknown AI provider %r; using the offline rules engine.", settings.ai_provider)
        cls = RulesProvider
    return cls()
