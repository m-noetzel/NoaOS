"""Tests for Phase MR2: Memory Persistence.

MemoryStore gains JSON-file-per-fact persistence: write on store(),
remove on delete(), rewrite on update_status(), load all .json files
on __init__.

Spec refs: SPEC.md §13.2
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from noa.private_worker.memory_store import MemoryStore

pytestmark = pytest.mark.mr2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _store_fact(
    store: MemoryStore,
    fact: str = "User prefers dark mode",
    category: str = "preference",
    embedding: list[float] | None = None,
    source_thread_id: str = "thread-abc",
    auto_extracted: bool = False,
) -> str:
    """Store a fact and return its ID (asserts non-None)."""
    fact_id = store.store(
        fact=fact,
        category=category,
        embedding=embedding or [0.1, 0.2, 0.3],
        source_thread_id=source_thread_id,
        auto_extracted=auto_extracted,
    )
    assert fact_id is not None
    return fact_id


# ---------------------------------------------------------------------------
# In-memory backward compatibility
# ---------------------------------------------------------------------------


class TestInMemoryBackwardCompat:
    """MemoryStore without data_dir must work exactly as before."""

    def test_init_without_data_dir_works(self):
        """Constructing without data_dir gives a pure in-memory store."""
        store = MemoryStore()
        fact_id = _store_fact(store)
        assert store.get_by_id(fact_id) is not None

    def test_init_with_none_data_dir_works(self):
        """Passing data_dir=None is equivalent to omitting it."""
        store = MemoryStore(data_dir=None)
        fact_id = _store_fact(store)
        assert store.get_by_id(fact_id) is not None


# ---------------------------------------------------------------------------
# Disk persistence — store()
# ---------------------------------------------------------------------------


class TestStoreWritesFile:
    """store() must write a JSON file to data_dir."""

    def test_store_writes_json_file(self, tmp_path: Path):
        """store() creates {data_dir}/{fact_id}.json."""
        store = MemoryStore(data_dir=tmp_path)
        fact_id = _store_fact(store)

        json_file = tmp_path / f"{fact_id}.json"
        assert json_file.exists(), f"Expected {json_file} to exist"

    def test_stored_file_contains_correct_data(self, tmp_path: Path):
        """The JSON file must contain the full fact dict."""
        store = MemoryStore(data_dir=tmp_path)
        fact_id = _store_fact(store, fact="Likes coffee")

        json_file = tmp_path / f"{fact_id}.json"
        data = json.loads(json_file.read_text())

        assert data["id"] == fact_id
        assert data["fact"] == "Likes coffee"
        assert data["category"] == "preference"
        assert data["embedding"] == [0.1, 0.2, 0.3]
        assert data["source_thread_id"] == "thread-abc"
        assert data["status"] == "approved"
        assert data["auto_extracted"] is False
        assert "created_at" in data

    def test_store_creates_data_dir_if_missing(self, tmp_path: Path):
        """If data_dir does not exist, it should be created automatically."""
        nested = tmp_path / "sub" / "dir"
        assert not nested.exists()

        store = MemoryStore(data_dir=nested)
        _store_fact(store)

        assert nested.is_dir()


# ---------------------------------------------------------------------------
# Disk persistence — delete()
# ---------------------------------------------------------------------------


class TestDeleteRemovesFile:
    """delete() must remove the JSON file."""

    def test_delete_removes_json_file(self, tmp_path: Path):
        """delete() must remove {data_dir}/{fact_id}.json."""
        store = MemoryStore(data_dir=tmp_path)
        fact_id = _store_fact(store)

        json_file = tmp_path / f"{fact_id}.json"
        assert json_file.exists()

        store.delete(fact_id)
        assert not json_file.exists()


# ---------------------------------------------------------------------------
# Disk persistence — update_status()
# ---------------------------------------------------------------------------


class TestUpdateStatusRewritesFile:
    """update_status() must rewrite the JSON file with the new status."""

    def test_update_status_rewrites_file(self, tmp_path: Path):
        """update_status() rewrites the file with new status value."""
        store = MemoryStore(data_dir=tmp_path)
        fact_id = _store_fact(store, auto_extracted=True)

        json_file = tmp_path / f"{fact_id}.json"
        before = json.loads(json_file.read_text())
        assert before["status"] == "pending"

        store.update_status(fact_id, "approved")

        after = json.loads(json_file.read_text())
        assert after["status"] == "approved"


# ---------------------------------------------------------------------------
# Load from disk on init
# ---------------------------------------------------------------------------


class TestLoadFromDisk:
    """MemoryStore.__init__ must load all *.json files from data_dir."""

    def test_load_restores_facts(self, tmp_path: Path):
        """Facts persisted by one store instance are loaded by a new one."""
        store1 = MemoryStore(data_dir=tmp_path)
        fact_id = _store_fact(store1, fact="Persisted fact")

        # New instance should load the file
        store2 = MemoryStore(data_dir=tmp_path)
        restored = store2.get_by_id(fact_id)

        assert restored is not None
        assert restored["fact"] == "Persisted fact"

    def test_load_ignores_invalid_json(self, tmp_path: Path):
        """Invalid JSON files in data_dir must be silently skipped."""
        # Write a valid fact
        store1 = MemoryStore(data_dir=tmp_path)
        fact_id = _store_fact(store1, fact="Valid fact")

        # Write an invalid JSON file
        bad_file = tmp_path / "garbage.json"
        bad_file.write_text("not valid json {{{")

        # New instance should load without error, keeping the valid fact
        store2 = MemoryStore(data_dir=tmp_path)
        assert store2.get_by_id(fact_id) is not None
        assert len(store2.list_all()) == 1

    def test_list_all_includes_loaded_facts(self, tmp_path: Path):
        """list_all() must include facts loaded from disk."""
        store1 = MemoryStore(data_dir=tmp_path)
        _store_fact(store1, fact="Fact A")
        _store_fact(store1, fact="Fact B")

        store2 = MemoryStore(data_dir=tmp_path)
        all_facts = store2.list_all()

        fact_texts = {f["fact"] for f in all_facts}
        assert "Fact A" in fact_texts
        assert "Fact B" in fact_texts

    def test_recall_works_after_reload(self, tmp_path: Path):
        """recall() must find facts loaded from disk."""
        store1 = MemoryStore(data_dir=tmp_path)
        _store_fact(
            store1,
            fact="User prefers dark mode",
            embedding=[1.0, 0.0, 0.0],
        )

        store2 = MemoryStore(data_dir=tmp_path)
        results = store2.recall(
            query_embedding=[0.9, 0.1, 0.0],
            n_results=5,
        )

        assert len(results) >= 1
        assert results[0]["fact"] == "User prefers dark mode"

    def test_deduplication_works_after_reload(self, tmp_path: Path):
        """Deduplication must work against facts loaded from disk."""
        store1 = MemoryStore(data_dir=tmp_path)
        _store_fact(store1, fact="Unique fact")

        store2 = MemoryStore(data_dir=tmp_path)
        dup_id = store2.store(
            fact="Unique fact",
            category="preference",
            embedding=[0.1],
            source_thread_id="thread-new",
        )

        assert dup_id is None  # Duplicate rejected


# ---------------------------------------------------------------------------
# handlers.py singleton uses /data/memory
# ---------------------------------------------------------------------------


class TestHandlersSingleton:
    """handlers.py must configure the singleton with data_dir."""

    def test_handlers_singleton_uses_data_memory_path(self):
        """The _memory_store singleton in handlers must use /data/memory."""
        import sys

        # Remove cached module so we can re-import cleanly
        sys.modules.pop("noa.private_worker.handlers", None)

        # Import triggers module-level MemoryStore(data_dir=Path("/data/memory"))
        # Since /data may not exist in test env, the constructor now tolerates
        # a missing data_dir (no eager mkdir).
        from noa.private_worker import handlers

        store = handlers._memory_store
        assert store._data_dir == Path("/data/memory")
