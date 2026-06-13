import pytest

from process_opt.parameters.errors import InvalidTransitionError
from process_opt.parameters.schemas import ParameterStatus
from process_opt.parameters.state_machine import validate_transition


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (ParameterStatus.DRAFT, ParameterStatus.PROPOSED),
        (ParameterStatus.PROPOSED, ParameterStatus.APPROVED),
        (ParameterStatus.PROPOSED, ParameterStatus.REJECTED),
        (ParameterStatus.APPROVED, ParameterStatus.ACTIVE),
        (ParameterStatus.ACTIVE, ParameterStatus.ARCHIVED),
        (ParameterStatus.APPROVED, ParameterStatus.ARCHIVED),
    ],
)
def test_validate_transition_allows_valid_status_changes(from_status: ParameterStatus, to_status: ParameterStatus) -> None:
    validate_transition(from_status, to_status)


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (ParameterStatus.PROPOSED, ParameterStatus.ACTIVE),
        (ParameterStatus.REJECTED, ParameterStatus.ACTIVE),
        (ParameterStatus.ARCHIVED, ParameterStatus.ACTIVE),
        (ParameterStatus.ACTIVE, ParameterStatus.DRAFT),
        (ParameterStatus.ACTIVE, ParameterStatus.PROPOSED),
    ],
)
def test_validate_transition_rejects_invalid_status_changes(from_status: ParameterStatus, to_status: ParameterStatus) -> None:
    with pytest.raises(InvalidTransitionError) as exc_info:
        validate_transition(from_status, to_status)

    assert exc_info.value.code == "INVALID_TRANSITION"
