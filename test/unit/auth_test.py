"""Test jwt token handling."""

from __future__ import annotations

from typing import Any, cast

import jwt
import pytest

from waylay.sdk import WaylayToken
from waylay.sdk.auth.exceptions import AuthError, TokenParseError

OK = "--OK--"
TOKEN_CASES: list[tuple[str, dict[str, Any], str]] = [
    ("valid", {"tenant": "xyz", "exp": 1999999999}, OK),
    ("expired", {"tenant": "xyz", "exp": 0}, "token expired"),
    ("notenant", {"exp": 0}, "invalid token"),
    ("empty", {}, "could not parse token data"),
]
CASES: list[tuple[str, str | None, dict[str, Any] | None, type | None, str]] = [
    # token_string, token_data, err_class, err_text
    ("empty-none", "", None, TokenParseError, "invalid token"),
    ("none", None, {}, AuthError, "no token"),
    ("empty", "", {}, AuthError, "no token"),
    # test with pre-decoded data
    *(
        (
            f"p-{case}",
            "fake-token",
            token_data,
            AuthError if err_text is not OK else None,
            err_text,
        )
        for (case, token_data, err_text) in TOKEN_CASES
    ),
    # tests with tokens (no signature validation)
    *(
        (
            f"t-{case}",
            jwt.encode(token_data, key=""),
            None,
            AuthError if err_text is not OK else None,
            err_text,
        )
        for (case, token_data, err_text) in TOKEN_CASES
    ),
]


@pytest.mark.parametrize(
    "token_string, token_data, err_class, err_text",
    [c[1:] for c in CASES],
    ids=[c[0] for c in CASES],
)
def test_tokens(
    token_string: str | None,
    token_data: dict | None,
    err_class: type | None,
    err_text: str,
):
    """Test token validation (without signature verification)."""
    try:
        maybe_empty_token_string = cast(str, token_string)
        token = WaylayToken(maybe_empty_token_string, token_data)
        assert token.token_string == token_string
        assert token == token.validate()
        assert err_class is None
    except AssertionError:
        raise
    except Exception as e:
        assert err_class is not None
        assert isinstance(e, err_class)
        assert err_text in str(e)
