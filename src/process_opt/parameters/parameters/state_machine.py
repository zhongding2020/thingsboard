from process_opt.parameters.errors import InvalidTransitionError
from process_opt.parameters.schemas import ParameterStatus


_ALLOWED_TRANSITIONS = {
    (ParameterStatus.DRAFT, ParameterStatus.PROPOSED),
    (ParameterStatus.PROPOSED, ParameterStatus.APPROVED),
    (ParameterStatus.PROPOSED, ParameterStatus.REJECTED),
    (ParameterStatus.APPROVED, ParameterStatus.ACTIVE),
    (ParameterStatus.ACTIVE, ParameterStatus.ARCHIVED),
    (ParameterStatus.APPROVED, ParameterStatus.ARCHIVED),
}


def validate_transition(from_status: ParameterStatus, to_status: ParameterStatus) -> None:
    if (from_status, to_status) not in _ALLOWED_TRANSITIONS:
        raise InvalidTransitionError(f"Invalid parameter status transition: {from_status} -> {to_status}")
