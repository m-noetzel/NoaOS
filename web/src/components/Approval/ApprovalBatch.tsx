/**
 * ApprovalBatch — Batch approval controls.
 * Provides select-all and batch approve/deny actions.
 */

interface ApprovalBatchProps {
  totalCount: number;
  selectedCount: number;
  onSelectAll: () => void;
  onClearSelection: () => void;
  onBatchApprove: () => void;
  onBatchDeny: () => void;
}

export function ApprovalBatch({
  totalCount,
  selectedCount,
  onSelectAll,
  onClearSelection,
  onBatchApprove,
  onBatchDeny,
}: ApprovalBatchProps) {
  const allSelected = selectedCount === totalCount && totalCount > 0;

  return (
    <div className="approval-batch" role="toolbar" aria-label="Batch actions">
      <label>
        <input
          type="checkbox"
          checked={allSelected}
          onChange={allSelected ? onClearSelection : onSelectAll}
          aria-label="Select all approvals"
        />
        Select all ({selectedCount}/{totalCount})
      </label>
      {selectedCount > 0 && (
        <div className="batch-actions">
          <button
            onClick={onBatchApprove}
            aria-label={`Approve ${selectedCount} selected`}
          >
            Approve selected ({selectedCount})
          </button>
          <button
            onClick={onBatchDeny}
            aria-label={`Deny ${selectedCount} selected`}
          >
            Deny selected ({selectedCount})
          </button>
        </div>
      )}
    </div>
  );
}
