/**
 * Approval API client.
 * Handles fetching pending approvals and submitting decisions.
 */

import { apiClient } from "./client";
import type { ApprovalRequest } from "../store/approvals";

interface PendingApprovalsResponse {
  approvals: ApprovalRequest[];
}

interface DecisionResponse {
  approval_id: string;
  status: "decided";
}

export async function fetchPendingApprovals(): Promise<ApprovalRequest[]> {
  const res = await apiClient.get<PendingApprovalsResponse>(
    "/approvals/pending",
  );
  return res.data.approvals;
}

export async function submitDecision(
  approvalId: string,
  decision: "approve" | "deny",
): Promise<DecisionResponse> {
  const res = await apiClient.post<DecisionResponse>(
    `/approvals/${approvalId}/decide`,
    { decision },
  );
  return res.data;
}
