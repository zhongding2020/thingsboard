from __future__ import annotations

from typing import Any


ANALYSIS_ERROR_CODES: dict[str, str] = {
    "EMPTY_DATASET": "The dataset contains no samples",
    "INSUFFICIENT_SAMPLES": "Not enough samples for meaningful analysis",
    "FIELD_NOT_FOUND": "Requested field does not exist in the data",
    "NON_NUMERIC_FIELD": "Field contains non-numeric values",
    "TOO_MANY_SAMPLES": "Dataset exceeds maximum allowed sample count",
    "SEARCH_SPACE_TOO_LARGE": "Search space exceeds computational limits",
    "MODEL_FIT_FAILED": "Model fitting failed to converge",
    "INVALID_CONSTRAINT": "Constraint parameters are invalid",
}


class AnalysisError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.suggestion = suggestion
