import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ArtifactViewer } from "../components/Artifacts/ArtifactViewer";
import type { Artifact } from "../store/artifacts";

const mockArtifacts: Artifact[] = [
  {
    id: "a1",
    run_id: "run-1",
    type: "file",
    name: "output.txt",
    mime_type: "text/plain",
    size_bytes: 1024,
    created_at: "2026-03-01T10:00:00Z",
  },
  {
    id: "a2",
    run_id: "run-1",
    type: "diff",
    name: "changes.patch",
    mime_type: "text/x-diff",
    size_bytes: 512,
    content: "@@ -1,3 +1,4 @@\n context line\n-removed line\n+added line\n more context",
    created_at: "2026-03-01T10:01:00Z",
  },
  {
    id: "a3",
    run_id: "run-1",
    type: "export",
    name: "report.csv",
    mime_type: "text/csv",
    size_bytes: 2048,
    created_at: "2026-03-01T10:02:00Z",
  },
  {
    id: "a4",
    run_id: "run-1",
    type: "preview",
    name: "screenshot.png",
    mime_type: "image/png",
    size_bytes: 4096,
    created_at: "2026-03-01T10:03:00Z",
  },
];

describe("ArtifactViewer", () => {
  it("renders artifact list with type icons (file, diff, export, preview)", () => {
    render(<ArtifactViewer artifacts={mockArtifacts} />);

    const list = screen.getByRole("list", { name: /artifact list/i });
    expect(list).toBeInTheDocument();

    // Each artifact type has an icon with the correct label
    expect(screen.getByLabelText("File")).toBeInTheDocument();
    expect(screen.getByLabelText("Diff")).toBeInTheDocument();
    expect(screen.getByLabelText("Export")).toBeInTheDocument();
    expect(screen.getByLabelText("Preview")).toBeInTheDocument();

    // Verify icon test ids
    expect(screen.getByTestId("icon-file")).toBeInTheDocument();
    expect(screen.getByTestId("icon-diff")).toBeInTheDocument();
    expect(screen.getByTestId("icon-export")).toBeInTheDocument();
    expect(screen.getByTestId("icon-preview")).toBeInTheDocument();
  });

  it("diff viewer renders with syntax highlighting markers", () => {
    render(
      <ArtifactViewer
        artifacts={mockArtifacts}
        selectedArtifactId="a2"
      />,
    );

    // The diff viewer region should be present
    const diffRegion = screen.getByRole("region", { name: /diff: changes\.patch/i });
    expect(diffRegion).toBeInTheDocument();

    // Check for syntax highlighting markers via data-diff-type attributes
    const additions = diffRegion.querySelectorAll('[data-diff-type="diff-addition"]');
    const removals = diffRegion.querySelectorAll('[data-diff-type="diff-removal"]');
    const hunks = diffRegion.querySelectorAll('[data-diff-type="diff-hunk"]');

    expect(additions.length).toBeGreaterThan(0);
    expect(removals.length).toBeGreaterThan(0);
    expect(hunks.length).toBeGreaterThan(0);
  });

  it("file artifacts show name, size, and mime type", () => {
    render(<ArtifactViewer artifacts={mockArtifacts} />);

    // File artifact shows name
    expect(screen.getByText("output.txt")).toBeInTheDocument();
    // File artifact shows size (1024 bytes = 1.0 KB)
    expect(screen.getByText("1.0 KB")).toBeInTheDocument();
    // File artifact shows mime type
    expect(screen.getByText("text/plain")).toBeInTheDocument();
  });

  it("artifact metadata panel shows creation time and size", () => {
    render(
      <ArtifactViewer
        artifacts={mockArtifacts}
        selectedArtifactId="a1"
      />,
    );

    const metadataRegion = screen.getByRole("region", { name: /artifact metadata/i });
    expect(metadataRegion).toBeInTheDocument();

    // Check that the metadata panel has the creation time
    // The formatted date will vary by locale, but should contain "2026"
    expect(metadataRegion.textContent).toContain("2026");

    // Check size is present in metadata
    expect(metadataRegion.textContent).toContain("1.0 KB");
  });

  it("download button present for export artifacts", () => {
    render(
      <ArtifactViewer
        artifacts={mockArtifacts}
        selectedArtifactId="a3"
      />,
    );

    const downloadButton = screen.getByRole("button", { name: /download/i });
    expect(downloadButton).toBeInTheDocument();
    expect(downloadButton).toHaveAttribute("download", "report.csv");
  });

  it('empty state shows "No artifacts" message', () => {
    render(<ArtifactViewer artifacts={[]} />);

    expect(screen.getByText("No artifacts")).toBeInTheDocument();
  });
});
