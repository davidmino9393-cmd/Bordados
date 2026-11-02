"""E1: deterministic raster colour masks in the frozen document contract."""
from .pipeline import vectorize
from .types import VectorizeFailure, VectorizeResult

__all__ = ["vectorize", "VectorizeFailure", "VectorizeResult"]
