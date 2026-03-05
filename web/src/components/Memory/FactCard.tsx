/**
 * FactCard — displays a single stored fact with category badge and actions.
 */

import React from "react";
import type { Fact } from "../../store/memory";
import { useMemoryStore } from "../../store/memory";

const CATEGORY_LABELS: Record<string, string> = {
  preference: "Preference",
  habit: "Habit",
  project_context: "Project Context",
  personal_info: "Personal Info",
};

interface FactCardProps {
  fact: Fact;
  onApprove: (id: string, content?: string) => void;
  onDelete: (id: string) => void;
}

export const FactCard: React.FC<FactCardProps> = ({
  fact,
  onApprove,
  onDelete,
}) => {
  const { editingFactId, editingContent, startEditing, setEditingContent, cancelEditing } =
    useMemoryStore();

  const isEditing = editingFactId === fact.id;

  const handleSaveEdit = () => {
    onApprove(fact.id, editingContent);
    cancelEditing();
  };

  return (
    <article aria-label={`fact: ${fact.fact}`} data-testid={`fact-${fact.id}`}>
      <span data-testid={`badge-${fact.category}`} className="category-badge">
        {CATEGORY_LABELS[fact.category] ?? fact.category}
      </span>

      {isEditing ? (
        <div>
          <input
            aria-label="edit fact content"
            value={editingContent}
            onChange={(e) => setEditingContent(e.target.value)}
          />
          <button onClick={handleSaveEdit}>Save</button>
          <button onClick={cancelEditing}>Cancel</button>
        </div>
      ) : (
        <p>{fact.fact}</p>
      )}

      <span className="fact-status">{fact.status}</span>

      <div className="fact-actions">
        {fact.status === "pending" && (
          <>
            <button
              aria-label={`approve fact ${fact.id}`}
              onClick={() => onApprove(fact.id)}
            >
              Approve
            </button>
            <button
              aria-label={`discard fact ${fact.id}`}
              onClick={() => onDelete(fact.id)}
            >
              Discard
            </button>
            {!isEditing && (
              <button
                aria-label={`edit fact ${fact.id}`}
                onClick={() => startEditing(fact.id, fact.fact)}
              >
                Edit
              </button>
            )}
          </>
        )}
        {fact.status !== "pending" && (
          <button
            aria-label={`delete fact ${fact.id}`}
            onClick={() => onDelete(fact.id)}
          >
            Delete
          </button>
        )}
      </div>
    </article>
  );
};
