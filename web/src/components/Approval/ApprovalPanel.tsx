/**
 * ApprovalPanel — Main approval panel.
 * Fetches pending approvals on mount, displays list with risk badges,
 * dry-run previews, and approve/deny controls.
 */

import { useEffect, useCallback } from "react";
import { useApprovalStore } from "../../store/approvals";
import { fetchPendingApprovals, submitDecision } from "../../api/approvals";
import { PreviewCard } from "./PreviewCard";
import { ApprovalBatch } from "./ApprovalBatch";
import type { ApprovalRequest } from "../../store/approvals";

function RiskBadge({ tier }: { tier: ApprovalRequest["risk_tier"] }) {
  const color = tier === "high" ? "red" : "yellow";
  return (
    <span
      className={`risk-badge risk-badge--${color}`}
      data-testid={`risk-badge-${color}`}
      role="status"
      aria-label={`Risk tier: ${tier}`}
    >
      {tier.toUpperCase()}
    </span>
  );
}

function StepUpAuthIndicator() {
  return (
    <span
      className="step-up-auth"
      data-testid="step-up-auth"
      role="alert"
      aria-label="Step-up authentication required"
    >
      Step-up auth required
    </span>
  );
}

export function ApprovalPanel() {
  const {
    approvals,
    selectedIds,
    loading,
    setApprovals,
    removeApproval,
    removeApprovals,
    toggleSelected,
    selectAll,
    clearSelection,
    setLoading,
    setError,
  } = useApprovalStore();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchPendingApprovals()
      .then((data) => {
        if (!cancelled) {
          setApprovals(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [setApprovals, setLoading, setError]);

  const handleDecision = useCallback(
    async (id: string, decision: "approve" | "deny") => {
      await submitDecision(id, decision);
      removeApproval(id);
    },
    [removeApproval],
  );

  const handleBatchApprove = useCallback(async () => {
    const ids = Array.from(selectedIds);
    await Promise.all(ids.map((id) => submitDecision(id, "approve")));
    removeApprovals(ids);
  }, [selectedIds, removeApprovals]);

  const handleBatchDeny = useCallback(async () => {
    const ids = Array.from(selectedIds);
    await Promise.all(ids.map((id) => submitDecision(id, "deny")));
    removeApprovals(ids);
  }, [selectedIds, removeApprovals]);

  if (loading) {
    return <div role="status">Loading approvals...</div>;
  }

  if (approvals.length === 0) {
    return (
      <div
        className="approval-panel approval-panel--empty"
        data-testid="approval-panel-empty"
      >
        <p>No pending approvals</p>
      </div>
    );
  }

  return (
    <div className="approval-panel" data-testid="approval-panel">
      <ApprovalBatch
        totalCount={approvals.length}
        selectedCount={selectedIds.size}
        onSelectAll={selectAll}
        onClearSelection={clearSelection}
        onBatchApprove={handleBatchApprove}
        onBatchDeny={handleBatchDeny}
      />
      <ul role="list" aria-label="Pending approvals">
        {approvals.map((approval) => (
          <li key={approval.id} data-testid={`approval-item-${approval.id}`}>
            <div className="approval-header">
              <input
                type="checkbox"
                checked={selectedIds.has(approval.id)}
                onChange={() => toggleSelected(approval.id)}
                aria-label={`Select approval ${approval.id}`}
              />
              <span className="action-type">{approval.action_type}</span>
              <RiskBadge tier={approval.risk_tier} />
              {approval.risk_tier === "high" && <StepUpAuthIndicator />}
            </div>
            <PreviewCard preview={approval.preview} />
            <div className="approval-actions">
              <button
                onClick={() => handleDecision(approval.id, "approve")}
                aria-label={`Approve ${approval.action_type}`}
              >
                Approve
              </button>
              <button
                onClick={() => handleDecision(approval.id, "deny")}
                aria-label={`Deny ${approval.action_type}`}
              >
                Deny
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
