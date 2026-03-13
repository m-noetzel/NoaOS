"""External-worker shared state for in-process API wiring.

Mirrors the pattern established by noa.private_worker.handlers for the private
domain. The external MemoryStore is initialised here so that app.py can import
it without reaching into the private_worker package (ARCH L1, L3).

Imports MemoryStore from the shared noa.memory layer — not from
noa.private_worker.memory_store — to respect the cross-domain isolation
rule (ARCH L3: external_worker must not import from private_worker).
"""

from __future__ import annotations

from pathlib import Path

from noa.memory import MemoryStore

# Shared in-process external-domain memory store instance.
# Persists facts as JSON files under the private-data Docker volume
# in a separate namespace from the private-domain store.
_memory_store = MemoryStore(data_dir=Path("/data/memory/external"))
