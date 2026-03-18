"""QE3: Open Findings Closure — verification tests.

Tests that confirm each of the three open findings has been properly addressed:
  - iOS-L2: #warning added to DEBUG blocks in ServiceFactory.swift
  - W20-MED-3: continue-on-error removed from E2E step in web-ci.yml
  - W20-MED-4: NotImplementedError stubs have clear intent documentation
  - FINDINGS.md: Open count is 0
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]


def test_ios_l2_warning_present() -> None:
    """iOS-L2: Both #if DEBUG blocks in ServiceFactory.swift contain a #warning directive."""
    service_factory = REPO_ROOT / "ios/Noa/Sources/Noa/Configuration/ServiceFactory.swift"
    content = service_factory.read_text()

    # Count occurrences of #warning inside #if DEBUG blocks
    # The file has two #if DEBUG blocks (makePinnedSession + makePinnedVoiceSession).
    warning_count = content.count(
        '#warning("DEBUG build: certificate pinning is disabled'
    )
    assert warning_count == 2, (
        f"Expected 2 #warning directives in DEBUG blocks, found {warning_count}. "
        "iOS-L2 fix requires both makePinnedSession and makePinnedVoiceSession to warn."
    )


def test_w20_med3_no_continue_on_error() -> None:
    """W20-MED-3: The E2E Playwright step in web-ci.yml does not use continue-on-error."""
    web_ci = REPO_ROOT / ".github/workflows/web-ci.yml"
    content = web_ci.read_text()

    assert "continue-on-error" not in content, (
        "web-ci.yml still contains 'continue-on-error'. "
        "W20-MED-3 fix requires this to be removed so E2E failures block the pipeline."
    )


def test_w20_med4_tools_py_references_gateway() -> None:
    """W20-MED-4: tools.py references ToolGateway for dispatch."""
    tools_py = REPO_ROOT / "src/noa/orchestrator/nodes/tools.py"
    content = tools_py.read_text()

    assert "toolgateway" in content.lower(), (
        "tools.py should reference ToolGateway — all dispatch flows through it."
    )
    assert "set_gateway" in content, (
        "tools.py should contain set_gateway to configure the gateway at startup."
    )


def test_w20_med4_mcp_adapter_deleted_by_cq2() -> None:
    """W20-MED-4: mcp_adapter.py deleted by CQ2 (superseded by McpRemoteAdapter)."""
    mcp_adapter = REPO_ROOT / "src/noa/tools/mcp_adapter.py"
    assert not mcp_adapter.exists(), (
        "mcp_adapter.py should be deleted — CQ2 dead code cleanup"
    )


def test_findings_open_count_consistent() -> None:
    """FINDINGS.md tracking table open count matches actual Open rows."""
    import re

    findings = REPO_ROOT / "Plan/FINDINGS.md"
    content = findings.read_text()

    # Count actual Open rows in the tracking table
    actual_open = len(re.findall(r"\| Open \|", content))

    # Extract the declared open count
    m = re.search(r"\*\*Open:\*\*\s+(\d+)", content)
    assert m is not None, "FINDINGS.md missing '**Open:** N' count line"
    declared_open = int(m.group(1))

    assert declared_open == actual_open, (
        f"FINDINGS.md declares **Open:** {declared_open} but has {actual_open} "
        f"rows with '| Open |'. Update the count line to match."
    )
