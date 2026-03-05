"""Coding task input/output schemas per SPEC.md §15.

Defines the contract for coding task requests and results.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CodingTaskInput(BaseModel):
    """Input schema for a coding task (§15).

    All fields are required except max_iterations which defaults to 3.
    """

    repo: str = Field(..., description="Path to the repository/workspace.")
    objective: str = Field(..., description="What the coding task should accomplish.")
    constraints: list[str] = Field(
        default_factory=list,
        description="Constraints the implementation must respect.",
    )
    test_command: str = Field(..., description="Shell command to run tests.")
    max_iterations: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum edit-test iterations before aborting.",
    )


class CodingTaskOutput(BaseModel):
    """Output schema for a coding task (§15).

    Contains the diff, test results, lint output, and a summary.
    """

    diff: str = Field(..., description="Unified diff of changes made.")
    test_results: str = Field(..., description="Output from the test command.")
    lint: str = Field(..., description="Lint/static analysis output.")
    summary: str = Field(..., description="Human-readable summary of what was done.")
    iterations_used: int = Field(..., ge=0, description="Number of iterations used.")
    success: bool = Field(..., description="Whether the task completed successfully.")
