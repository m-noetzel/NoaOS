"""Coding task input/output schemas per SPEC.md §15.

Defines the contract for coding task requests and results.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, Field


class RiskTier(enum.StrEnum):
    """Risk tier for coding tasks per §15."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CodingConstraints(BaseModel):
    """Structured constraints for a coding task per §15."""

    language: str | None = None
    style: str | None = None
    performance: str | None = None


class CodingTaskInput(BaseModel):
    """Input schema for a coding task (§15).

    Matches the SPEC.md §15 JSON schema exactly.
    """

    repo: str = Field(..., description="Path to the repository/workspace.")
    base_commit: str | None = Field(
        default=None, description="Base commit SHA to diff against."
    )
    objective: str = Field(..., description="What the coding task should accomplish.")
    constraints: CodingConstraints = Field(
        default_factory=CodingConstraints,
        description="Structured constraints (language, style, performance).",
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="List of acceptance criteria the result must satisfy.",
    )
    test_command: str = Field(..., description="Shell command to run tests.")
    risk_tier: RiskTier = Field(
        default=RiskTier.LOW, description="Risk tier for this coding task."
    )
    max_iterations: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum edit-test iterations before aborting.",
    )


class CodingTaskOutput(BaseModel):
    """Output schema for a coding task (§15).

    Contains both raw outputs and the structured JSON summary per spec.
    """

    # Raw outputs
    diff: str = Field(..., description="Git diff / patch of changes made.")
    test_results: str = Field(..., description="Raw test output logs.")
    lint: str = Field(..., description="Lint/typecheck results.")

    # Structured summary per §15
    status: str = Field(..., description="'success' or 'failure'.")
    files_modified: list[str] = Field(
        default_factory=list, description="List of files modified."
    )
    tests_passed: bool = Field(..., description="Whether all tests passed.")
    summary: str = Field(..., description="Short description of what was done.")
    iterations_used: int = Field(..., ge=0, description="Number of iterations used.")

    @property
    def success(self) -> bool:
        """Convenience alias: True when status is 'success'."""
        return self.status == "success"
