"""AI provider contract.

QE Compass ships with an offline rules engine (`RulesProvider`). To connect a
language model later, implement this interface in a new module (for example
`app/ai/llm.py`), register it in `app/ai/__init__.py`, and set
`QEC_AI_PROVIDER` in `.env`. Nothing else in the application changes: routers
only talk to `get_provider()`.

Every method receives plain data (no database sessions), so a provider can be
unit-tested in isolation and can safely run in a worker thread.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class FocusAreaRef:
    id: int
    key: str
    name: str
    pillar: str
    description: str
    question: str
    recommendation: str
    horizon: str


@dataclass
class Finding:
    focus_area_id: int
    score: int | None
    confidence: str  # low | med | high
    finding: str
    followup: str = ""
    applied: bool = False


@dataclass
class Classification:
    doc_type: str
    summary: str
    focus_area_ids: list[int]
    signals: list[str] = field(default_factory=list)


@dataclass
class LevelSuggestion:
    level: int | None
    cues: list[str]


@dataclass
class AnalystRequest:
    question: str
    scope_name: str
    # structured, JSON-serializable view of the workspace (see ai/context.py)
    context: dict
    history: list[dict] = field(default_factory=list)  # [{role, content}]


class AIProvider(Protocol):
    name: str

    def suggest_level(self, notes: str, scale: list[str]) -> LevelSuggestion: ...

    def extract_findings(
        self, notes: str, stakeholder: str, entity: str, focus_areas: list[FocusAreaRef], scale: list[str]
    ) -> list[Finding]: ...

    def classify_evidence(self, filename: str, text: str, focus_areas: list[FocusAreaRef]) -> Classification: ...

    def analyst(self, req: AnalystRequest) -> str:
        """Answer in Markdown (## headings, - bullets, **bold**)."""
        ...

    def executive_summary(self, snapshot: dict, client: str) -> str: ...
