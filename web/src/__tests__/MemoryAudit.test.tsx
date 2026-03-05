import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../test/mocks/server";
import { MemoryAudit } from "../components/Memory/MemoryAudit";
import { useMemoryStore } from "../store/memory";
import type { Fact } from "../store/memory";

const API_BASE = "http://localhost:8000/api/v1";

const makeFact = (overrides: Partial<Fact> = {}): Fact => ({
  id: "f1",
  fact: "Prefers dark mode",
  category: "preference",
  status: "approved",
  auto_extracted: false,
  created_at: "2026-01-01T00:00:00Z",
  ...overrides,
});

const sampleFacts: Fact[] = [
  makeFact({ id: "f1", fact: "Prefers dark mode", category: "preference", status: "approved" }),
  makeFact({ id: "f2", fact: "Runs every morning", category: "habit", status: "approved" }),
  makeFact({ id: "f3", fact: "Working on Noa project", category: "project_context", status: "pending" }),
  makeFact({ id: "f4", fact: "Lives in Berlin", category: "personal_info", status: "approved" }),
  makeFact({ id: "f5", fact: "Likes tea over coffee", category: "preference", status: "pending" }),
];

function setupMswHandlers(facts: Fact[] = sampleFacts) {
  const state = [...facts];

  server.use(
    http.get(`${API_BASE}/memory/facts`, () => {
      return HttpResponse.json({
        data: { facts: state },
        meta: { request_id: "r1", trace_id: "t1", timestamp: new Date().toISOString() },
      });
    }),

    http.post(`${API_BASE}/memory/facts/:factId/approve`, async ({ params, request }) => {
      const factId = params.factId as string;
      const body = (await request.json()) as Record<string, unknown>;
      const idx = state.findIndex((f) => f.id === factId);
      if (idx === -1) {
        return HttpResponse.json(
          { error: { code: "NOT_FOUND", message: "Fact not found" } },
          { status: 404 },
        );
      }
      state[idx] = {
        ...state[idx],
        status: "approved",
        ...(body.fact !== undefined ? { fact: body.fact as string } : {}),
      };
      return HttpResponse.json({
        data: state[idx],
        meta: { request_id: "r2", trace_id: "t2", timestamp: new Date().toISOString() },
      });
    }),

    http.post(`${API_BASE}/memory/facts/:factId/delete`, ({ params }) => {
      const factId = params.factId as string;
      const idx = state.findIndex((f) => f.id === factId);
      if (idx !== -1) {
        state.splice(idx, 1);
      }
      return HttpResponse.json({
        data: { success: true },
        meta: { request_id: "r3", trace_id: "t3", timestamp: new Date().toISOString() },
      });
    }),

    http.post(`${API_BASE}/memory/facts/:factId/update`, async ({ params, request }) => {
      const factId = params.factId as string;
      const body = (await request.json()) as Record<string, unknown>;
      const idx = state.findIndex((f) => f.id === factId);
      if (idx !== -1) {
        state[idx] = { ...state[idx], ...body } as Fact;
      }
      return HttpResponse.json({
        data: state[idx],
        meta: { request_id: "r4", trace_id: "t4", timestamp: new Date().toISOString() },
      });
    }),
  );
}

describe("MemoryAudit", () => {
  beforeEach(() => {
    // Reset zustand store between tests
    useMemoryStore.setState({
      facts: [],
      filterCategory: null,
      loading: false,
      error: null,
      editingFactId: null,
      editingContent: "",
    });
  });

  it("renders stored facts with category badges", async () => {
    setupMswHandlers();
    render(<MemoryAudit />);

    await waitFor(() => {
      expect(screen.getByText("Prefers dark mode")).toBeInTheDocument();
    });

    expect(screen.getByText("Runs every morning")).toBeInTheDocument();
    expect(screen.getByText("Working on Noa project")).toBeInTheDocument();
    expect(screen.getByText("Lives in Berlin")).toBeInTheDocument();
    expect(screen.getByText("Likes tea over coffee")).toBeInTheDocument();

    // Check category badges exist
    const badges = screen.getAllByText(/Preference|Habit|Project Context|Personal Info/);
    expect(badges.length).toBeGreaterThanOrEqual(5);
  });

  it("filter by category works", async () => {
    setupMswHandlers();
    const user = userEvent.setup();
    render(<MemoryAudit />);

    await waitFor(() => {
      expect(screen.getByText("Prefers dark mode")).toBeInTheDocument();
    });

    // Click "Habit" filter
    await user.click(screen.getByRole("button", { name: "Habit" }));

    // Only habit fact should be shown
    expect(screen.getByText("Runs every morning")).toBeInTheDocument();
    expect(screen.queryByText("Prefers dark mode")).not.toBeInTheDocument();
    expect(screen.queryByText("Working on Noa project")).not.toBeInTheDocument();

    // Click "Preference" filter
    await user.click(screen.getByRole("button", { name: "Preference" }));
    expect(screen.getByText("Prefers dark mode")).toBeInTheDocument();
    expect(screen.getByText("Likes tea over coffee")).toBeInTheDocument();
    expect(screen.queryByText("Runs every morning")).not.toBeInTheDocument();

    // Click "All" to reset filter
    await user.click(screen.getByRole("button", { name: "All" }));
    expect(screen.getByText("Prefers dark mode")).toBeInTheDocument();
    expect(screen.getByText("Runs every morning")).toBeInTheDocument();
  });

  it("pending facts show approve/discard buttons", async () => {
    setupMswHandlers();
    render(<MemoryAudit />);

    await waitFor(() => {
      expect(screen.getByText("Working on Noa project")).toBeInTheDocument();
    });

    // Pending fact f3 should have approve and discard buttons
    expect(screen.getByLabelText("approve fact f3")).toBeInTheDocument();
    expect(screen.getByLabelText("discard fact f3")).toBeInTheDocument();

    // Pending fact f5
    expect(screen.getByLabelText("approve fact f5")).toBeInTheDocument();
    expect(screen.getByLabelText("discard fact f5")).toBeInTheDocument();

    // Approved fact f1 should NOT have approve/discard buttons
    expect(screen.queryByLabelText("approve fact f1")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("discard fact f1")).not.toBeInTheDocument();
  });

  it("approve button changes fact status to approved", async () => {
    setupMswHandlers();
    const user = userEvent.setup();
    render(<MemoryAudit />);

    await waitFor(() => {
      expect(screen.getByText("Working on Noa project")).toBeInTheDocument();
    });

    // Click approve on pending fact f3
    await user.click(screen.getByLabelText("approve fact f3"));

    // After approval, the approve/discard buttons should disappear for f3
    await waitFor(() => {
      expect(screen.queryByLabelText("approve fact f3")).not.toBeInTheDocument();
    });

    // The fact should still be visible
    expect(screen.getByText("Working on Noa project")).toBeInTheDocument();

    // Now a delete button should be present instead
    expect(screen.getByLabelText("delete fact f3")).toBeInTheDocument();
  });

  it("delete button removes fact from list", async () => {
    setupMswHandlers();
    const user = userEvent.setup();
    render(<MemoryAudit />);

    await waitFor(() => {
      expect(screen.getByText("Prefers dark mode")).toBeInTheDocument();
    });

    // Delete approved fact f1 using the delete button
    await user.click(screen.getByLabelText("delete fact f1"));

    await waitFor(() => {
      expect(screen.queryByText("Prefers dark mode")).not.toBeInTheDocument();
    });

    // Other facts still present
    expect(screen.getByText("Runs every morning")).toBeInTheDocument();
  });

  it("memory stats display total and per-category counts", async () => {
    setupMswHandlers();
    render(<MemoryAudit />);

    await waitFor(() => {
      expect(screen.getByText("Prefers dark mode")).toBeInTheDocument();
    });

    // Stats section
    expect(screen.getByLabelText("memory statistics")).toBeInTheDocument();
    expect(screen.getByTestId("total-count")).toHaveTextContent("Total facts: 5");
    expect(screen.getByTestId("count-preference")).toHaveTextContent("Preference: 2");
    expect(screen.getByTestId("count-habit")).toHaveTextContent("Habit: 1");
    expect(screen.getByTestId("count-project_context")).toHaveTextContent("Project Context: 1");
    expect(screen.getByTestId("count-personal_info")).toHaveTextContent("Personal Info: 1");
  });

  it("empty state shows 'No stored facts' message", async () => {
    setupMswHandlers([]);
    render(<MemoryAudit />);

    await waitFor(() => {
      expect(screen.getByText("No stored facts")).toBeInTheDocument();
    });
  });

  it("edit button on pending fact allows editing content before approval", async () => {
    setupMswHandlers();
    const user = userEvent.setup();
    render(<MemoryAudit />);

    await waitFor(() => {
      expect(screen.getByText("Working on Noa project")).toBeInTheDocument();
    });

    // Click edit on pending fact f3
    await user.click(screen.getByLabelText("edit fact f3"));

    // An input should appear with the current fact content
    const input = screen.getByLabelText("edit fact content");
    expect(input).toBeInTheDocument();
    expect(input).toHaveValue("Working on Noa project");

    // Edit the content
    await user.clear(input);
    await user.type(input, "Working on Noa v2 project");

    // Click save (which approves with updated content)
    await user.click(screen.getByText("Save"));

    // After save, the fact should be updated and approved
    await waitFor(() => {
      expect(screen.getByText("Working on Noa v2 project")).toBeInTheDocument();
    });

    // Approve/discard buttons should be gone (now approved)
    expect(screen.queryByLabelText("approve fact f3")).not.toBeInTheDocument();
  });
});
