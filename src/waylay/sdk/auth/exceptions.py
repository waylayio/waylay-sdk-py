"""Auth exception utilities."""

import jwt.exceptions as jwt_exc

from ..exceptions import WaylayError

_AUTH_MESSAGE_FOR_EXCEPTON_CLASS = [
    (jwt_exc.ExpiredSignatureError, "token expired"),
    (jwt_exc.InvalidTokenError, "invalid token"),
    (jwt_exc.PyJWTError, "invalid token"),
    (TypeError, "could not decode token"),
    (ValueError, "could not decode token"),
]


def _auth_message_for_exception(exception):
    for exc_class, msg in _AUTH_MESSAGE_FOR_EXCEPTON_CLASS:
        if isinstance(exception, exc_class):
            return msg
    return "could not decode token"


class AuthError(WaylayError):
    """Exception class for waylay authentication errors."""


class TokenParseError(AuthError):
    """Error parsing a waylay token."""

    def __init__(self, exc):
        """Create a token parse error."""
        super().__init__(_auth_message_for_exception(exc))
