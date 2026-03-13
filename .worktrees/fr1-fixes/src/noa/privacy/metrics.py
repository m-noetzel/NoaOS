"""Classification metrics and drift detection.

Spec refs: SPEC.md §14.3 — false negative rate tracking and drift alerting.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DriftAlert:
    """Alert raised when classification drift exceeds threshold."""

    drift_amount: float
    baseline_rate: float
    current_rate: float
    message: str = ""


class ClassificationMetrics:
    """Tracks privacy classification metrics for drift detection (§14.3)."""

    def __init__(self) -> None:
        self._records: list[dict[str, str]] = []
        self._baseline_rate: float | None = None
        self._baseline_count: int = 0

    def record(self, *, predicted: str, actual: str) -> None:
        """Record a classification result with ground-truth label.

        Args:
            predicted: The predicted domain ("private" or "external").
            actual: The actual/ground-truth domain ("private" or "external").
        """
        self._records.append({"predicted": predicted, "actual": actual})

    def false_negative_rate(self, *, since_baseline: bool = False) -> float:
        """Compute the false negative rate.

        A false negative is when actual=private but predicted=external
        (i.e., a private task was incorrectly routed to external).

        Args:
            since_baseline: If True, only consider records after baseline snapshot.

        Returns:
            False negative rate as a float between 0.0 and 1.0.
        """
        records = self._records
        if since_baseline:
            records = records[self._baseline_count:]

        actual_private = [r for r in records if r["actual"] == "private"]
        if not actual_private:
            return 0.0

        false_negatives = [
            r for r in actual_private if r["predicted"] == "external"
        ]
        return len(false_negatives) / len(actual_private)

    def snapshot_baseline(self) -> None:
        """Take a snapshot of the current false negative rate as baseline.

        Records after this point are considered the "new period" for
        drift detection.
        """
        self._baseline_rate = self.false_negative_rate()
        self._baseline_count = len(self._records)

    def check_drift(self, *, threshold: float = 0.02) -> DriftAlert | None:
        """Check if false negative rate has drifted beyond threshold.

        Compares the current (post-baseline) false negative rate against
        the baseline rate. Returns a DriftAlert if the increase exceeds
        the threshold.

        Args:
            threshold: Maximum acceptable increase in false negative rate.

        Returns:
            DriftAlert if drift exceeds threshold, None otherwise.
        """
        if self._baseline_rate is None:
            return None

        current_rate = self.false_negative_rate(since_baseline=True)
        drift = current_rate - self._baseline_rate

        if drift > threshold:
            return DriftAlert(
                drift_amount=drift,
                baseline_rate=self._baseline_rate,
                current_rate=current_rate,
                message=(
                    f"False negative rate drifted by {drift:.4f} "
                    f"(baseline={self._baseline_rate:.4f}, "
                    f"current={current_rate:.4f}), "
                    f"exceeding threshold {threshold:.4f}."
                ),
            )
        return None
