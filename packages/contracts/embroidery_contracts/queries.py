"""Paged project/history reads. No history is silently truncated."""
from typing import Annotated

from pydantic import Field, model_validator

from .base import Versioned
from .jobs import JobResponse, ProjectResponse, RevisionResponse
from .settings import SourceAsset

Cursor = Annotated[str, Field(min_length=1, max_length=2048)]


class ProjectList(Versioned):
    items: tuple[ProjectResponse, ...]
    next_cursor: Cursor | None


class ProjectDetail(Versioned):
    project: ProjectResponse
    assets: tuple[SourceAsset, ...]
    jobs: tuple[JobResponse, ...]
    assets_next_cursor: Cursor | None
    jobs_next_cursor: Cursor | None

    @model_validator(mode="after")
    def own_project_history(self):
        if any(item.project_id != self.project.project_id for item in (*self.assets, *self.jobs)):
            raise ValueError("All assets/jobs must belong to the returned project")
        return self


class RevisionList(Versioned):
    items: tuple[RevisionResponse, ...]
    next_cursor: Cursor | None
