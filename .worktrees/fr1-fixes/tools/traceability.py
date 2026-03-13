#!/usr/bin/env python3
"""
tools/traceability.py — Requirements Traceability Matrix generator.

Parses SPEC.md section headers, PHASE_DETAILS.md phase→spec mappings, and
test file docstrings for SPEC citations. Produces Plan/TRACEABILITY.md with
a coverage table and summary counts.

Usage:
    python tools/traceability.py              # generate Plan/TRACEABILITY.md
    python tools/traceability.py --check      # non-zero exit if critical orphans exist
    python tools/traceability.py --check --output /dev/null   # check only, no file

Critical sections: §1–§25 (must all be covered for --check to pass)
Non-critical sections: §26+ (flagged but not blocking)
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
SPEC_PATH = REPO_ROOT / "SPEC.md"
PHASE_DETAILS_PATH = REPO_ROOT / "Plan" / "PHASE_DETAILS.md"
PLAN_PATH = REPO_ROOT / "Plan" / "PLAN.md"
TESTS_DIR = REPO_ROOT / "tests"
OUTPUT_PATH = REPO_ROOT / "Plan" / "TRACEABILITY.md"

# Sections §1–§25 are "critical" — orphans here fail --check
CRITICAL_TOP_LEVEL_THRESHOLD = 25


# ─────────────────────────────────────────────────────────────
# Section parsing
# ─────────────────────────────────────────────────────────────

def parse_spec_sections(spec_path: Path) -> list[str]:
    """
    Return all section identifiers from SPEC.md in canonical form.

    Top-level sections like "# 5. Authentication" → "§5"
    Subsections like "## 5.3 Authentication Flow" → "§5.3"
    """
    sections: list[str] = []
    seen: set[str] = set()

    # Pattern: lines starting with "# N." or "## N.M" (numbered sections)
    top_re = re.compile(r"^#\s+(\d+)\.\s+")
    sub_re = re.compile(r"^#{2,}\s+(\d+(?:\.\d+)+)\s+")

    with spec_path.open() as f:
        for line in f:
            m = sub_re.match(line)
            if m:
                sec = f"§{m.group(1)}"
                if sec not in seen:
                    sections.append(sec)
                    seen.add(sec)
                continue
            m = top_re.match(line)
            if m:
                sec = f"§{m.group(1)}"
                if sec not in seen:
                    sections.append(sec)
                    seen.add(sec)

    return sections


def section_number(sec: str) -> tuple[int, ...]:
    """Return a sortable tuple from a section string like '§5.3'."""
    digits = sec.lstrip("§")
    return tuple(int(x) for x in digits.split("."))


def is_critical(sec: str) -> bool:
    """True if the section is §1–§25 (top-level number ≤ 25)."""
    top = section_number(sec)[0]
    return top <= CRITICAL_TOP_LEVEL_THRESHOLD


# ─────────────────────────────────────────────────────────────
# Reference extraction
# ─────────────────────────────────────────────────────────────

# Matches "§5.3", "§12", "§2.1" etc. anywhere in text
_SEC_RE = re.compile(r"§(\d+(?:\.\d+)*)")


def _extract_sections_from_text(text: str) -> set[str]:
    """Extract all §N or §N.M references from arbitrary text."""
    return {f"§{m.group(1)}" for m in _SEC_RE.finditer(text)}


def parse_phase_details(phase_details_path: Path) -> dict[str, set[str]]:
    """
    Return mapping: phase_id → set of spec sections.

    Looks for lines of the form:
        **Spec refs:** SPEC.md §4.1, §7.1, §8.1, ...
    and associates them with the most recently seen phase header.
    """
    phase_to_sections: dict[str, set[str]] = defaultdict(set)

    phase_header_re = re.compile(
        r"###\s+Phase\s+([A-Za-z0-9]+(?:[A-Za-z0-9_\-\.]+)?)\s*:"
    )
    # Also catch "### QE1:", "### TM1:", etc. (no "Phase" prefix)
    phase_header2_re = re.compile(r"###\s+([A-Z]{1,4}\d+)\s*:")
    spec_ref_re = re.compile(r"\*\*Spec refs:\*\*\s*(.+)")

    current_phase: str | None = None

    with phase_details_path.open() as f:
        for line in f:
            m = phase_header_re.search(line)
            if m:
                current_phase = m.group(1).strip()
                continue
            m = phase_header2_re.search(line)
            if m:
                current_phase = m.group(1).strip()
                continue
            m = spec_ref_re.search(line)
            if m and current_phase:
                refs = _extract_sections_from_text(m.group(1))
                phase_to_sections[current_phase].update(refs)

    return dict(phase_to_sections)


def parse_test_files(tests_dir: Path) -> dict[str, set[str]]:
    """
    Return mapping: test_file (relative path) → set of spec sections.

    Searches file-level docstrings and inline docstrings of test functions
    for §N.M references. Also looks for bare text like "SPEC.md §5.3".
    """
    file_to_sections: dict[str, set[str]] = defaultdict(set)

    for test_file in tests_dir.rglob("test_*.py"):
        try:
            source = test_file.read_text(encoding="utf-8")
        except OSError:
            continue

        refs = _extract_sections_from_text(source)
        if refs:
            # Use tests_dir as base when possible, fall back to REPO_ROOT, then absolute
            try:
                rel = str(test_file.relative_to(REPO_ROOT))
            except ValueError:
                try:
                    rel = str(test_file.relative_to(tests_dir))
                except ValueError:
                    rel = str(test_file)
            file_to_sections[rel].update(refs)

    return dict(file_to_sections)


# ─────────────────────────────────────────────────────────────
# Coverage computation
# ─────────────────────────────────────────────────────────────

def _is_ancestor(ancestor: str, descendant: str) -> bool:
    """True if ancestor is a parent of descendant (e.g., §2 is ancestor of §2.1)."""
    a = section_number(ancestor)
    d = section_number(descendant)
    if len(d) <= len(a):
        return False
    return d[: len(a)] == a


def build_coverage(
    all_sections: list[str],
    phase_to_sections: dict[str, set[str]],
    file_to_sections: dict[str, set[str]],
) -> list[dict]:
    """
    For each spec section, compute phases and test files that reference it.

    Inheritance: a parent section (e.g., §2) inherits coverage from its
    children (e.g., §2.1, §2.2) for the purpose of status computation.
    This prevents parent-level introductory headers from appearing as
    orphans when their subsections are fully covered.

    Status:
      - Covered  → referenced (directly or via children) by ≥1 phase AND ≥1 test file
      - Partial  → referenced (directly or via children) by ≥1 phase OR ≥1 test file
      - Orphaned → neither direct nor child coverage in phase or test
    """
    # Invert: section → set of phases (direct references only)
    section_to_phases: dict[str, set[str]] = defaultdict(set)
    for phase, secs in phase_to_sections.items():
        for sec in secs:
            section_to_phases[sec].add(phase)

    # Invert: section → set of test files (direct references only)
    section_to_files: dict[str, set[str]] = defaultdict(set)
    for fpath, secs in file_to_sections.items():
        for sec in secs:
            section_to_files[sec].add(fpath)

    section_set = set(all_sections)

    rows = []
    for sec in all_sections:
        # Direct references
        phases: set[str] = set(section_to_phases.get(sec, set()))
        files: set[str] = set(section_to_files.get(sec, set()))

        # Inherit from child sections (so §2 is covered if §2.1 is covered)
        for other in section_set:
            if _is_ancestor(sec, other):
                phases.update(section_to_phases.get(other, set()))
                files.update(section_to_files.get(other, set()))

        phases_sorted = sorted(phases)
        files_sorted = sorted(files)

        has_phase = bool(phases)
        has_test = bool(files)

        if has_phase and has_test:
            status = "Covered"
        elif has_phase or has_test:
            status = "Partial"
        else:
            status = "Orphaned"

        rows.append(
            {
                "section": sec,
                "phases": phases_sorted,
                "files": files_sorted,
                "status": status,
                "critical": is_critical(sec),
            }
        )

    return rows


# ─────────────────────────────────────────────────────────────
# Markdown generation
# ─────────────────────────────────────────────────────────────

def _shorten_file(path: str) -> str:
    """Strip leading 'tests/' prefix for readability."""
    return path.replace("tests/unit/", "").replace("tests/integration/", "integration/")


def generate_markdown(rows: list[dict]) -> str:
    covered = sum(1 for r in rows if r["status"] == "Covered")
    partial = sum(1 for r in rows if r["status"] == "Partial")
    orphaned = sum(1 for r in rows if r["status"] == "Orphaned")
    total = len(rows)

    critical_orphans = [r for r in rows if r["status"] == "Orphaned" and r["critical"]]
    noncritical_orphans = [
        r for r in rows if r["status"] == "Orphaned" and not r["critical"]
    ]

    lines: list[str] = [
        "# Requirements Traceability Matrix",
        "",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Total SPEC sections | {total} |",
        f"| Covered (phase + test) | {covered} |",
        f"| Partial (phase or test only) | {partial} |",
        f"| Orphaned (no coverage) | {orphaned} |",
        f"| Critical orphans (\u00a71\u2013\u00a725) | {len(critical_orphans)} |",
        f"| Non-critical orphans (\u00a726+) | {len(noncritical_orphans)} |",
        "",
    ]

    if critical_orphans:
        lines += [
            "## Critical Orphans (FAIL — §1–§25 with no coverage)",
            "",
        ]
        for r in critical_orphans:
            lines.append(f"- **{r['section']}**")
        lines.append("")

    if noncritical_orphans:
        lines += [
            "## Non-Critical Orphans (§26+ deferred/future)",
            "",
        ]
        for r in noncritical_orphans:
            lines.append(f"- {r['section']}")
        lines.append("")

    # Full coverage table
    lines += [
        "## Full Coverage Table",
        "",
        "| SPEC Section | Phase(s) | Test File(s) | Status |",
        "|---|---|---|---|",
    ]

    for r in rows:
        sec = r["section"]
        phases_str = ", ".join(r["phases"]) if r["phases"] else "\u2014"
        files_str = (
            ", ".join(_shorten_file(f) for f in r["files"]) if r["files"] else "\u2014"
        )
        status = r["status"]
        # Visual indicator
        _indicators = {
            "Covered": "COVERED",
            "Partial": "PARTIAL",
            "Orphaned": "ORPHANED",
        }
        indicator = _indicators.get(status, status)
        lines.append(f"| {sec} | {phases_str} | {files_str} | {indicator} |")

    lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def run(
    output_path: Path | None = OUTPUT_PATH,
    check_mode: bool = False,
) -> int:
    """
    Execute traceability analysis.

    Returns 0 on success, 1 if --check and critical orphans exist.
    """
    if not SPEC_PATH.exists():
        print(f"ERROR: SPEC.md not found at {SPEC_PATH}", file=sys.stderr)
        return 1

    all_sections = parse_spec_sections(SPEC_PATH)
    phase_to_sections = parse_phase_details(PHASE_DETAILS_PATH)
    file_to_sections = parse_test_files(TESTS_DIR)

    rows = build_coverage(all_sections, phase_to_sections, file_to_sections)
    md = generate_markdown(rows)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # M3: Preserve content below <!-- MANUAL SECTIONS --> sentinel if present
        sentinel = "<!-- MANUAL SECTIONS -->"
        manual_suffix = ""
        if output_path.exists():
            existing = output_path.read_text(encoding="utf-8")
            sentinel_idx = existing.find(sentinel)
            if sentinel_idx != -1:
                manual_suffix = existing[sentinel_idx:]

        if manual_suffix:
            output_path.write_text(md + "\n" + manual_suffix, encoding="utf-8")
        else:
            output_path.write_text(md, encoding="utf-8")
        print(f"Written: {output_path}")

    # Stats
    covered = sum(1 for r in rows if r["status"] == "Covered")
    partial = sum(1 for r in rows if r["status"] == "Partial")
    orphaned_all = sum(1 for r in rows if r["status"] == "Orphaned")
    critical_orphans = [r for r in rows if r["status"] == "Orphaned" and r["critical"]]

    print(
        f"Sections: {len(rows)} total | "
        f"{covered} covered | {partial} partial | {orphaned_all} orphaned"
    )
    print(f"Critical orphans (§1–§25): {len(critical_orphans)}")

    if check_mode and critical_orphans:
        msg = "\nFAIL \u2014 the following critical sections have no coverage:"
        print(msg, file=sys.stderr)
        for r in critical_orphans:
            print(f"  {r['section']}", file=sys.stderr)
        return 1

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Requirements Traceability Matrix for NoaOS."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if critical (§1–§25) sections are orphaned.",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_PATH),
        help=(
            f"Output path for TRACEABILITY.md (default: {OUTPUT_PATH}). "
            "Use /dev/null to skip."
        ),
    )
    args = parser.parse_args()

    out = None if args.output == "/dev/null" else Path(args.output)
    sys.exit(run(output_path=out, check_mode=args.check))


if __name__ == "__main__":
    main()
