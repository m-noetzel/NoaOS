"""Migration chain consistency test — FR3-L1.

Validates Alembic migration graph without touching a database:
- Every down_revision references an existing revision
- Exactly one head (no branch splits)
- No orphaned migrations (every non-head is reachable from head)
- Chain walks continuously from head to base (None)
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

VERSIONS_DIR = Path(__file__).resolve().parents[2] / "alembic" / "versions"


def _load_migration(path: Path) -> ModuleType:
    """Load a migration file as a module without executing upgrade/downgrade."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None, f"Cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    # Register in sys.modules so relative imports inside migrations don't fail.
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _collect_revisions() -> dict[str, str | None]:
    """Return {revision_id: down_revision} for every migration file."""
    revisions: dict[str, str | None] = {}
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        if path.name.startswith("__"):
            continue
        mod = _load_migration(path)
        revision: str = mod.revision
        down_revision: str | None = getattr(mod, "down_revision", None)
        # down_revision can be a tuple for merge migrations; normalise to str or None.
        if isinstance(down_revision, tuple):
            # Merge migrations have multiple parents — not expected in this project.
            # Store the first parent so chain detection catches the branch.
            down_revision = down_revision[0] if down_revision else None
        revisions[revision] = down_revision
    return revisions


class TestMigrationChain:
    """Static consistency checks on the Alembic migration graph."""

    def test_versions_directory_is_non_empty(self) -> None:
        """There must be at least one migration file."""
        files = [p for p in VERSIONS_DIR.glob("*.py") if not p.name.startswith("__")]
        assert len(files) > 0, "No migration files found in alembic/versions/"

    def test_every_down_revision_exists(self) -> None:
        """Every non-None down_revision must point to an existing revision."""
        revisions = _collect_revisions()
        known = set(revisions.keys())
        errors: list[str] = []
        for rev, down in revisions.items():
            if down is not None and down not in known:
                errors.append(f"Revision {rev!r} references missing down_revision {down!r}")
        assert not errors, "Broken down_revision references:\n" + "\n".join(errors)

    def test_exactly_one_head(self) -> None:
        """Exactly one revision must not appear as a down_revision of any other (the head)."""
        revisions = _collect_revisions()
        all_downs = {v for v in revisions.values() if v is not None}
        heads = [rev for rev in revisions if rev not in all_downs]
        assert len(heads) == 1, (
            f"Expected exactly 1 head revision, found {len(heads)}: {heads}. "
            "Multiple heads indicate an unmerged branch."
        )

    def test_exactly_one_base(self) -> None:
        """Exactly one revision must have down_revision=None (the initial migration)."""
        revisions = _collect_revisions()
        bases = [rev for rev, down in revisions.items() if down is None]
        assert len(bases) == 1, (
            f"Expected exactly 1 base revision (down_revision=None), found {len(bases)}: {bases}"
        )

    def test_chain_walks_from_head_to_base(self) -> None:
        """Walking down_revision links from head must visit every revision exactly once."""
        revisions = _collect_revisions()
        all_downs = {v for v in revisions.values() if v is not None}
        heads = [rev for rev in revisions if rev not in all_downs]
        assert len(heads) == 1, "Cannot walk chain: multiple heads detected"

        current: str | None = heads[0]
        visited: list[str] = []
        seen: set[str] = set()

        while current is not None:
            if current in seen:
                raise AssertionError(
                    f"Cycle detected in migration chain at revision {current!r}. "
                    f"Walk so far: {visited}"
                )
            if current not in revisions:
                raise AssertionError(
                    f"Chain broken: revision {current!r} not found. "
                    f"Walk so far: {visited}"
                )
            seen.add(current)
            visited.append(current)
            current = revisions[current]

        # Every revision must have been visited — no orphans.
        all_revisions = set(revisions.keys())
        orphans = all_revisions - seen
        assert not orphans, (
            f"Orphaned migrations not reachable from head: {sorted(orphans)}. "
            "These migrations are unreachable and will never be applied."
        )

    def test_no_duplicate_revision_ids(self) -> None:
        """No two migration files may declare the same revision ID."""
        seen: dict[str, str] = {}  # revision_id -> filename
        duplicates: list[str] = []
        for path in sorted(VERSIONS_DIR.glob("*.py")):
            if path.name.startswith("__"):
                continue
            mod = _load_migration(path)
            revision: str = mod.revision
            if revision in seen:
                duplicates.append(
                    f"Revision {revision!r} declared in both {seen[revision]} and {path.name}"
                )
            else:
                seen[revision] = path.name
        assert not duplicates, "Duplicate revision IDs:\n" + "\n".join(duplicates)
