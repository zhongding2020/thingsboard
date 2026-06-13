class ParameterError(Exception):
    code = "PARAMETER_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidTransitionError(ParameterError):
    code = "INVALID_TRANSITION"
