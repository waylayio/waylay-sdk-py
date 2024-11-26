"""Test jwt token handling."""
from __future__ import annotations

import pytest

import jwt

from waylay.sdk.auth.exceptions import TokenParseError, AuthError
from waylay.sdk import WaylayToken

CASES = [
    # token_string, token_data, err_class, err_text
    ["empty","", None, TokenParseError, "invalid token"],
    ["p-none",None, {}, AuthError, 'no token'],
    ["p-empty","", {}, AuthError, 'no token'],
    ["p-fake","fake", {}, AuthError, 'could not parse'],
    ["p-invalid","fake", {'abc':'xyz'}, AuthError, 'invalid token'],
    ["p-tenant","fake", {'tenant':'xyz'}, AuthError, 'token expired'],
    ["p-expired","fake", {'tenant':'xyz','exp':0}, AuthError, 'token expired'],
    # minimal check: tenant and expiry ok
    ["p-not-expired","fake", {'tenant':'xyz','exp':1999999999}, None, '--OK--'],
    # tests with tokens (no signature validation)
    *(
        [
            f"t-{case}", jwt.encode(token_data, key=''), None,
            AuthError if err_text else None, err_text
        ] for case, token_data, err_text in [
            ('valid',{'tenant':'xyz','exp':1999999999}, None),
            ('expired',{'tenant':'xyz','exp':0}, 'token expired'),
            ('notenant',{'exp':0}, 'invalid token'),
        ]
    )
]


@pytest.mark.parametrize(
    "token_string, token_data, err_class, err_text",
    [c[1:] for c in CASES],
    ids=[c[0] for c in CASES],
)
def test_tokens(
    token_string: str| None, token_data: dict | None, err_class: type | None, err_text: str
):
    """Test token validation (without signature verification)."""
    try:
        token = WaylayToken(token_string, token_data)
        assert token.token_string == token_string
        assert token == token.validate()
        assert err_class is None
    except AssertionError:
        raise
    except Exception as e:
        assert err_class is not None
        assert isinstance(e, err_class)
        assert err_text in str(e)
