"""Method-specific artifact validators for the empirical-research layer.

These modules check objective structure, internal consistency, and
recomputability.  They deliberately do not assign a universal method-quality
score or decide whether a substantively correct metric is "good enough".
"""

from .common import Finding, ValidationContext

__all__ = ["Finding", "ValidationContext"]
