import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../test/mocks/server";
import { ApprovalPanel } from "../components/Approval/ApprovalPanel";
import { useApprovalStore } from "../store/approvals";

const API_BASE = "http://localhost:8000/api/v1";

const mockApprovals = [
  {
    id: "appr-1",
    run_id: "run-100",
    risk_tier: "medium" as const,
    action_type: "send_email",
    preview: {
      summary: "Send email to user@example.com",
      details: { recipient: "user@example.com", subject: "Hello" },
    },
    created_at: "2026-03-05T10:00:00Z",
  },
  {
    id: "appr-2",
    run_id: "run-101",
    risk_tier: "high" as const,
    action_type: "delete_account",
    preview: {
      summary: "Delete user account permanently",
      details: { user_id: "u-42", irreversible: "true" },
    },
    created_at: "2026-03-05T10:05:00Z",
  },
  {
    id: "appr-3",
    run_id: "run-102",
    risk_tier: "medium" as const,
    action_type: "update_config",
    preview: {
      summary: "Update system configuration",
      details: { key: "max_retries", value: "5" },
    },
    created_at: "2026-03-05T10:10:00Z",
  },
];

function setupHandlers(approvals = mockApprovals) {
  const decidedIds: string[] = [];

  server.use(
    http.get(`${API_BASE}/approvals/pending`, () => {
      return HttpResponse.json({
        data: {
          approvals: approvals.filter((a) => !decidedIds.includes(a.id)),
        },
        meta: {
          request_id: "req-appr-1",
          trace_id: "trace-appr-1",
          timestamp: new Date().toISOString(),
        },
      });
    }),
    http.post(`${API_BASE}/approvals/:id/decide`, async ({ params }) => {
      const id = params.id as string;
      decidedIds.push(id);
      return HttpResponse.json({
        data: { approval_id: id, status: "decided" },
        meta: {
          request_id: "req-decide-1",
          trace_id: "trace-decide-1",
          timestamp: new Date().toISOString(),
        },
      });
    }),
  );
}

describe("ApprovalPanel", () => {
  beforeEach(() => {
    // Reset store state before each test
    useApprovalStore.setState({
      approvals: [],
      selectedIds: new Set(),
      loading: false,
      error: null,
    });
  });

  it("renders pending approvals list", async () => {
    setupHandlers();
    render(<ApprovalPanel />);

    await waitFor(() => {
      expect(screen.getByText("send_email")).toBeInTheDocument();
    });

    expect(screen.getByText("delete_account")).toBeInTheDocument();
    expect(screen.getByText("update_config")).toBeInTheDocument();

    const list = screen.getByRole("list", { name: /pending approvals/i });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(3);
  });

  it("each approval shows risk tier badge (medium=yellow, high=red)", async () => {
    setupHandlers();
    render(<ApprovalPanel />);

    await waitFor(() => {
      expect(screen.getByText("send_email")).toBeInTheDocument();
    });

    // Medium risk approvals get yellow badges
    const yellowBadges = screen.getAllByTestId("risk-badge-yellow");
    expect(yellowBadges.length).toBe(2); // appr-1 and appr-3

    // High risk approval gets red badge
    const redBadges = screen.getAllByTestId("risk-badge-red");
    expect(redBadges.length).toBe(1); // appr-2

    // Verify badge text
    yellowBadges.forEach((badge) => {
      expect(badge).toHaveTextContent("MEDIUM");
    });
    redBadges.forEach((badge) => {
      expect(badge).toHaveTextContent("HIGH");
    });
  });

  it("dry-run preview displays formatted action summary", async () => {
    setupHandlers();
    render(<ApprovalPanel />);

    await waitFor(() => {
      expect(
        screen.getByText("Send email to user@example.com"),
      ).toBeInTheDocument();
    });

    expect(
      screen.getByText("Delete user account permanently"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Update system configuration"),
    ).toBeInTheDocument();

    // Verify preview regions exist
    const previews = screen.getAllByRole("region", {
      name: /dry-run preview/i,
    });
    expect(previews.length).toBe(3);
  });

  it("approve button sends approval and removes from list", async () => {
    setupHandlers();
    const user = userEvent.setup();
    render(<ApprovalPanel />);

    await waitFor(() => {
      expect(screen.getByText("send_email")).toBeInTheDocument();
    });

    // Click approve on the first item
    const approveButton = screen.getByRole("button", {
      name: /approve send_email/i,
    });
    await user.click(approveButton);

    // Item should be removed from the list
    await waitFor(() => {
      expect(screen.queryByText("send_email")).not.toBeInTheDocument();
    });

    // Other items remain
    expect(screen.getByText("delete_account")).toBeInTheDocument();
    expect(screen.getByText("update_config")).toBeInTheDocument();
  });

  it("deny button sends denial and removes from list", async () => {
    setupHandlers();
    const user = userEvent.setup();
    render(<ApprovalPanel />);

    await waitFor(() => {
      expect(screen.getByText("delete_account")).toBeInTheDocument();
    });

    // Click deny on the high-risk item
    const denyButton = screen.getByRole("button", {
      name: /deny delete_account/i,
    });
    await user.click(denyButton);

    // Item should be removed from the list
    await waitFor(() => {
      expect(screen.queryByText("delete_account")).not.toBeInTheDocument();
    });

    // Other items remain
    expect(screen.getByText("send_email")).toBeInTheDocument();
    expect(screen.getByText("update_config")).toBeInTheDocument();
  });

  it("high-risk approvals show step-up auth indicator", async () => {
    setupHandlers();
    render(<ApprovalPanel />);

    await waitFor(() => {
      expect(screen.getByText("delete_account")).toBeInTheDocument();
    });

    // Only the high-risk approval should have the step-up auth indicator
    const stepUpIndicators = screen.getAllByTestId("step-up-auth");
    expect(stepUpIndicators.length).toBe(1);
    expect(stepUpIndicators[0]).toHaveTextContent(
      "Step-up auth required",
    );

    // Verify it's associated with the high-risk item
    const highRiskItem = screen.getByTestId("approval-item-appr-2");
    expect(
      within(highRiskItem).getByTestId("step-up-auth"),
    ).toBeInTheDocument();

    // Medium risk items should NOT have step-up auth
    const mediumItem = screen.getByTestId("approval-item-appr-1");
    expect(
      within(mediumItem).queryByTestId("step-up-auth"),
    ).not.toBeInTheDocument();
  });

  it("batch approval: select-all approves multiple at once", async () => {
    setupHandlers();
    const user = userEvent.setup();
    render(<ApprovalPanel />);

    await waitFor(() => {
      expect(screen.getByText("send_email")).toBeInTheDocument();
    });

    // Click select all checkbox
    const selectAllCheckbox = screen.getByRole("checkbox", {
      name: /select all approvals/i,
    });
    await user.click(selectAllCheckbox);

    // Batch approve button should appear
    const batchApproveButton = screen.getByRole("button", {
      name: /approve 3 selected/i,
    });
    expect(batchApproveButton).toBeInTheDocument();

    // Click batch approve
    await user.click(batchApproveButton);

    // All items should be removed
    await waitFor(() => {
      expect(screen.getByText("No pending approvals")).toBeInTheDocument();
    });
  });

  it("empty state shows 'No pending approvals' message", async () => {
    setupHandlers([]);
    render(<ApprovalPanel />);

    await waitFor(() => {
      expect(screen.getByText("No pending approvals")).toBeInTheDocument();
    });

    expect(
      screen.getByTestId("approval-panel-empty"),
    ).toBeInTheDocument();
  });
});
