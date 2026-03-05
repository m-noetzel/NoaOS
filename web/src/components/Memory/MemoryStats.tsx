/**
 * MemoryStats — displays total and per-category fact counts.
 */

import React from "react";
import type { FactCategory } from "../../store/memory";

const CATEGORY_LABELS: Record<FactCategory, string> = {
  preference: "Preference",
  habit: "Habit",
  project_context: "Project Context",
  personal_info: "Personal Info",
};

interface MemoryStatsProps {
  total: number;
  byCategory: Record<FactCategory, number>;
}

export const MemoryStats: React.FC<MemoryStatsProps> = ({
  total,
  byCategory,
}) => {
  return (
    <section aria-label="memory statistics">
      <h3>Memory Stats</h3>
      <p data-testid="total-count">Total facts: {total}</p>
      <ul>
        {(Object.keys(byCategory) as FactCategory[]).map((cat) => (
          <li key={cat} data-testid={`count-${cat}`}>
            {CATEGORY_LABELS[cat]}: {byCategory[cat]}
          </li>
        ))}
      </ul>
    </section>
  );
};
