"""Shared constants used across domains per SPEC.md.

Moved here from domain-specific modules to avoid cross-domain imports (C2).
"""

from __future__ import annotations

# Maximum number of results for memory recall queries (SPEC.md §9.1).
MAX_N_RESULTS: int = 20
