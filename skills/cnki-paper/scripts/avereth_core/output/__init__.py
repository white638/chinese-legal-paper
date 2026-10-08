"""Delivery rendering, QA, guards, and publication owned by the local engine."""

from .run import record_visual_qa, run_output, validate_completion

__all__ = ["record_visual_qa", "run_output", "validate_completion"]
