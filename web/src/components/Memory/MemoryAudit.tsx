/**
 * MemoryAudit — main memory audit panel.
 * Displays facts, category filter, stats, and actions.
 */

import React, { useEffect } from "react";
import { useMemoryStore, FACT_CATEGORIES } from "../../store/memory";
import type { FactCategory } from "../../store/memory";
import { FactCard } from "./FactCard";
import { MemoryStats } from "./MemoryStats";
import * as memoryApi from "../../api/memory";

const CATEGORY_LABELS: Record<FactCategory, string> = {
  preference: "Preference",
  habit: "Habit",
  project_context: "Project Context",
  personal_info: "Personal Info",
};

export const MemoryAudit: React.FC = () => {
  const {
    filteredFacts,
    stats,
    filterCategory,
    setFilterCategory,
    setFacts,
    updateFact,
    removeFact,
    setLoading,
    setError,
    loading,
    error,
  } = useMemoryStore();

  const displayedFacts = filteredFacts();
  const memoryStats = stats();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    memoryApi
      .fetchFacts()
      .then((facts) => {
        if (!cancelled) {
          setFacts(facts);
          setLoading(false);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [setFacts, setLoading, setError]);

  const handleApprove = async (id: string, updatedContent?: string) => {
    try {
      const updated = await memoryApi.approveFact(id, updatedContent);
      updateFact(id, {
        status: updated.status,
        fact: updated.fact,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Approve failed");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await memoryApi.deleteFact(id);
      removeFact(id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  if (loading) {
    return <div>Loading facts...</div>;
  }

  if (error) {
    return <div role="alert">{error}</div>;
  }

  return (
    <div>
      <h2>Memory Audit</h2>

      <MemoryStats total={memoryStats.total} byCategory={memoryStats.byCategory} />

      <div role="group" aria-label="category filter">
        <button
          aria-pressed={filterCategory === null}
          onClick={() => setFilterCategory(null)}
        >
          All
        </button>
        {FACT_CATEGORIES.map((cat) => (
          <button
            key={cat}
            aria-pressed={filterCategory === cat}
            onClick={() => setFilterCategory(cat)}
          >
            {CATEGORY_LABELS[cat]}
          </button>
        ))}
      </div>

      {displayedFacts.length === 0 ? (
        <p>No stored facts</p>
      ) : (
        <div role="list" aria-label="facts list">
          {displayedFacts.map((fact) => (
            <div role="listitem" key={fact.id}>
              <FactCard
                fact={fact}
                onApprove={handleApprove}
                onDelete={handleDelete}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
