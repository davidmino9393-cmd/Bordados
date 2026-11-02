"""H2: decisión del usuario sobre un análisis visual que terminó en needs_review.

Ambas decisiones crean un job nuevo (parent_job_id = el original, que no cambia). El cliente nunca fija estados.
"""
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, RootModel, model_validator

from .base import Identifier, Versioned


class AnalysisApprove(Versioned):
    """Aprobar el análisis: misma revisión, mismo asset; `analyzing` queda omitido con motivo."""

    action: Literal["approve"]
    # Metadato de la decisión: no altera geometría, no crea incidencias y no bloquea la aprobación (H3 las usará).
    flagged_region_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def unique_regions(self):
        if len(set(self.flagged_region_ids)) != len(self.flagged_region_ids):
            raise ValueError("flagged_region_ids must not repeat a region")
        return self


class AnalysisChangeProvider(Versioned):
    """Cambiar de proveedor: ai_provider es parte de JobSettings, así que el servidor crea una revisión analysis_retry."""

    action: Literal["change_provider"]
    ai_provider: Literal["openai", "ollama"]


AnalysisDecisionBody = Annotated[AnalysisApprove | AnalysisChangeProvider, Field(discriminator="action")]


class AnalysisDecision(RootModel[AnalysisDecisionBody]):
    model_config = ConfigDict(frozen=True)
