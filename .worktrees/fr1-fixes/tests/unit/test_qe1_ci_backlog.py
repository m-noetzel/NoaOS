"""
QE1: CI Backlog Triage & Process Gate Application

Verifies that all APPLIED CI proposals are present in target files.
Tests parse the actual files to confirm content is present — behavioral
verification that the triage decisions took effect.

Phase: QE1
Spec refs: Pipeline evaluation §5 (Continuous Improvement), CI-001 through CI-033
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def read(rel: str) -> str:
    """Read a file relative to repo root."""
    return (ROOT / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# CI Backlog: zero PROPOSED items remain
# ---------------------------------------------------------------------------


def test_no_proposed_items_in_backlog() -> None:
    """Verify every CI proposal has been triaged (no PROPOSED status)."""
    content = read("Plan/CI/IMPROVEMENT_BACKLOG.md")
    # Skip the header row (which contains "Proposed" as a column name)
    lines_with_proposed = [
        line
        for line in content.splitlines()
        if "| PROPOSED |" in line and not line.startswith("| ID |")
    ]
    assert lines_with_proposed == [], (
        f"Found {len(lines_with_proposed)} PROPOSED items in backlog:\n"
        + "\n".join(lines_with_proposed)
    )


def test_all_p1_items_applied_or_rejected() -> None:
    """All P1 proposals must be APPLIED, RESOLVED, or REJECTED — never PROPOSED or DEFERRED."""
    content = read("Plan/CI/IMPROVEMENT_BACKLOG.md")
    p1_lines = [line for line in content.splitlines() if "| P1 |" in line]
    bad = [
        line
        for line in p1_lines
        if "| PROPOSED |" in line or "| DEFERRED |" in line
    ]
    assert bad == [], (
        "P1 proposals must not be PROPOSED or DEFERRED:\n" + "\n".join(bad)
    )


def test_backlog_has_expected_row_count() -> None:
    """Backlog should have all 33 CI items (CI-001 through CI-033)."""
    content = read("Plan/CI/IMPROVEMENT_BACKLOG.md")
    ci_ids = re.findall(r"\| CI-(\d+) \|", content)
    nums = {int(n) for n in ci_ids}
    expected = set(range(1, 34))
    missing = expected - nums
    assert missing == set(), f"Missing CI IDs from backlog: {sorted(missing)}"


# ---------------------------------------------------------------------------
# CLAUDE.md — CI-001, CI-002, CI-003, CI-004, CI-015, CI-016, CI-025, CI-033
# ---------------------------------------------------------------------------


def test_claude_md_ci001_implementation_first_bias() -> None:
    """CI-001: CLAUDE.md must contain implementation-first bias section."""
    content = read("CLAUDE.md")
    assert "Session Focus" in content or "implementation-first" in content.lower() or "CI-001" in content, (
        "CLAUDE.md missing CI-001 implementation-first bias content"
    )
    # More specific: the rule text should be present
    assert "start the work immediately" in content or "Implementation-First" in content


def test_claude_md_ci002_canonical_output_locations() -> None:
    """CI-002: CLAUDE.md must contain canonical output locations rule."""
    content = read("CLAUDE.md")
    assert "Canonical Output Locations" in content or "CI-002" in content


def test_claude_md_ci003_docker_environment_awareness() -> None:
    """CI-003: CLAUDE.md must contain Docker environment awareness rule."""
    content = read("CLAUDE.md")
    assert "Docker Environment Awareness" in content or "CI-003" in content
    assert "WAL" in content  # SQLite WAL mode rule is a key detail


def test_claude_md_ci004_key_directories_table() -> None:
    """CI-004: CLAUDE.md must contain key directories table."""
    content = read("CLAUDE.md")
    assert "Key Directories" in content
    assert "src/noa/" in content
    assert "web/" in content
    assert "tests/" in content


def test_claude_md_ci015_findings_sync_gate() -> None:
    """CI-015: CLAUDE.md must have findings sync as a named blocking gate."""
    content = read("CLAUDE.md")
    assert "Findings Sync" in content
    assert "CI-015" in content or "blocking" in content.lower()


def test_claude_md_ci016_s5_integration_baseline() -> None:
    """CI-016: CLAUDE.md must have S5 integration baseline rule for DB-touching endpoints."""
    content = read("CLAUDE.md")
    assert "S5 integration baseline" in content or "CI-016" in content
    # The rule should mention real DB tests
    assert "non-mocked integration test" in content or "real DB" in content


def test_claude_md_ci025_ios_contract_audit() -> None:
    """CI-025: CLAUDE.md must have iOS-backend contract audit step."""
    content = read("CLAUDE.md")
    assert "iOS" in content
    assert "Pydantic request model" in content or "contract audit" in content.lower()


def test_claude_md_ci033_pre_qa_deliverable_check() -> None:
    """CI-033: CLAUDE.md must have pre-QA deliverable completeness check."""
    content = read("CLAUDE.md")
    assert "CI-033" in content or "Pre-QA deliverable check" in content
    assert "deliverable" in content.lower()


# ---------------------------------------------------------------------------
# Plan/QA_CHECKLIST.md — M-gates and S-gates
# ---------------------------------------------------------------------------


def test_qa_checklist_m2b_write_path_test_fidelity() -> None:
    """CI-014: QA_CHECKLIST.md must contain M2b Write-Path Test Fidelity gate."""
    content = read("Plan/QA_CHECKLIST.md")
    assert "M2b" in content
    assert "Write-Path Test Fidelity" in content


def test_qa_checklist_m2c_source_inspection_gate() -> None:
    """CI-028: QA_CHECKLIST.md must contain M2c Source-Inspection Test Gate."""
    content = read("Plan/QA_CHECKLIST.md")
    assert "M2c" in content
    assert "Source-Inspection" in content


def test_qa_checklist_m3b_write_path_user_scoping() -> None:
    """CI-011: QA_CHECKLIST.md must contain M3b Write-Path User Scoping check."""
    content = read("Plan/QA_CHECKLIST.md")
    assert "M3b" in content
    assert "Write-Path User Scoping" in content


def test_qa_checklist_m4b_mock_interface_accuracy() -> None:
    """CI-008: QA_CHECKLIST.md must contain M4b Mock Interface Accuracy gate."""
    content = read("Plan/QA_CHECKLIST.md")
    assert "M4b" in content
    assert "Mock Interface Accuracy" in content


def test_qa_checklist_m5b_findings_currency() -> None:
    """CI-013: QA_CHECKLIST.md must contain M5b Findings Currency gate."""
    content = read("Plan/QA_CHECKLIST.md")
    assert "M5b" in content
    assert "Findings Currency" in content


def test_qa_checklist_m5c_related_issue_scope() -> None:
    """CI-026: QA_CHECKLIST.md must contain M5c Related-Issue Scope Completeness gate."""
    content = read("Plan/QA_CHECKLIST.md")
    assert "M5c" in content
    assert "Related-Issue Scope Completeness" in content or "Scope Completeness" in content


def test_qa_checklist_m8b_cross_language_optionality() -> None:
    """CI-017: QA_CHECKLIST.md must contain M8b Cross-Language Field Optionality gate."""
    content = read("Plan/QA_CHECKLIST.md")
    assert "M8b" in content
    assert "Cross-Language Field Optionality" in content


def test_qa_checklist_s5b_frontend_behavioral_coverage() -> None:
    """CI-012: QA_CHECKLIST.md must contain S5b Frontend Fix Behavioral Coverage gate."""
    content = read("Plan/QA_CHECKLIST.md")
    assert "S5b" in content
    assert "Behavioral Coverage" in content or "Frontend Fix" in content


def test_qa_checklist_s5_escalation_rule() -> None:
    """CI-010: QA_CHECKLIST.md must contain S5 escalation rule for persistent OPEN."""
    content = read("Plan/QA_CHECKLIST.md")
    assert "S5 Escalation Rule" in content or "CI-010" in content
    assert "3+" in content or "3 consecutive" in content or "three consecutive" in content.lower()


def test_qa_checklist_s5_audit_fix_carveout() -> None:
    """CI-029: QA_CHECKLIST.md must include audit-fix phase exemption in S5 escalation."""
    content = read("Plan/QA_CHECKLIST.md")
    assert "audit-fix" in content.lower() or "CI-029" in content


def test_qa_checklist_m7_app_state_write_only_detection() -> None:
    """CI-031: QA_CHECKLIST.md M7 must include app.state write-only detection."""
    content = read("Plan/QA_CHECKLIST.md")
    assert "CI-031" in content or "app.state" in content
    assert "dead-end store" in content.lower() or "no reader" in content.lower() or "write with no reader" in content.lower()


# ---------------------------------------------------------------------------
# Plan/ARCH_INVARIANTS.md — L12, L13, L14
# ---------------------------------------------------------------------------


def test_arch_invariants_l12_write_path_user_scoping() -> None:
    """CI-009: ARCH_INVARIANTS.md must contain L12 Write-Path User Scoping invariant."""
    content = read("Plan/ARCH_INVARIANTS.md")
    assert "L12" in content
    assert "Write-Path User Scoping" in content or "user_id" in content


def test_arch_invariants_l13_default_resolution() -> None:
    """CI-018: ARCH_INVARIANTS.md must contain L13 Default Resolution at API Boundary."""
    content = read("Plan/ARCH_INVARIANTS.md")
    assert "L13" in content
    assert "Default Resolution" in content or "API Boundary" in content


def test_arch_invariants_l14_cross_language_contract() -> None:
    """CI-022: ARCH_INVARIANTS.md must contain L14 Cross-Language Contract Completeness."""
    content = read("Plan/ARCH_INVARIANTS.md")
    assert "L14" in content
    assert "Cross-Language Contract" in content or "Contract Completeness" in content


def test_arch_invariants_has_sequential_l_numbers() -> None:
    """ARCH_INVARIANTS.md L-numbers should be sequential 1-14."""
    content = read("Plan/ARCH_INVARIANTS.md")
    found = {int(m) for m in re.findall(r"## L(\d+):", content)}
    expected = set(range(1, 15))
    missing = expected - found
    assert missing == set(), f"Missing L-numbers in ARCH_INVARIANTS.md: {sorted(missing)}"


# ---------------------------------------------------------------------------
# .claude/agents/implement.md — CI-023 pre-phase test plan
# ---------------------------------------------------------------------------


def test_implement_agent_ci023_pre_phase_test_plan() -> None:
    """CI-023: implement.md must have pre-phase test plan step."""
    content = read(".claude/agents/implement.md")
    assert "CI-023" in content or "Pre-Phase Test Plan" in content
    assert "test plan" in content.lower()
    # Should cover the key elements
    assert "happy-path" in content.lower() or "happy path" in content.lower()
    assert "negative-path" in content.lower() or "negative path" in content.lower() or "Negative" in content


# ---------------------------------------------------------------------------
# .claude/skills/phase-planning/SKILL.md — CI-024, CI-032
# ---------------------------------------------------------------------------


def test_phase_planning_skill_ci024_multi_platform_multiplier() -> None:
    """CI-024: phase-planning SKILL.md must have multi-platform duration multiplier."""
    content = read(".claude/skills/phase-planning/SKILL.md")
    assert "CI-024" in content or "multi-platform" in content.lower()
    assert "1.5x" in content or "2x" in content


def test_phase_planning_skill_ci032_infrastructure_estimate_bracket() -> None:
    """CI-032: phase-planning SKILL.md must have infrastructure phase estimate bracket."""
    content = read(".claude/skills/phase-planning/SKILL.md")
    assert "CI-032" in content or "Infrastructure" in content
    assert "20-30" in content or "20–30" in content


# ---------------------------------------------------------------------------
# Deferred/Rejected items: verify they are correctly marked
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ci_id,expected_status", [
    ("CI-005", "DEFERRED"),
    ("CI-006", "REJECTED"),
    ("CI-007", "DEFERRED"),
    ("CI-019", "DEFERRED"),
])
def test_deferred_rejected_items_correctly_marked(ci_id: str, expected_status: str) -> None:
    """Verify deferred/rejected items are correctly marked in the backlog."""
    content = read("Plan/CI/IMPROVEMENT_BACKLOG.md")
    # Find the row for this CI ID in the table
    pattern = rf"\| {re.escape(ci_id)} \|[^|]+\| [^|]+\| ([A-Z]+) \|"
    matches = re.findall(pattern, content)
    assert matches, f"Could not find status for {ci_id} in backlog table"
    status = matches[0].strip()
    assert status == expected_status, (
        f"{ci_id} expected {expected_status} but found {status}"
    )


# ---------------------------------------------------------------------------
# Integration: files actually exist and are parseable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rel_path", [
    "CLAUDE.md",
    "Plan/QA_CHECKLIST.md",
    "Plan/ARCH_INVARIANTS.md",
    "Plan/CI/IMPROVEMENT_BACKLOG.md",
    ".claude/agents/implement.md",
    ".claude/skills/phase-planning/SKILL.md",
])
def test_target_files_exist_and_readable(rel_path: str) -> None:
    """All target files for CI triage must exist and be non-empty."""
    path = ROOT / rel_path
    assert path.exists(), f"File not found: {rel_path}"
    content = path.read_text(encoding="utf-8")
    assert len(content) > 100, f"File appears empty or too short: {rel_path}"
