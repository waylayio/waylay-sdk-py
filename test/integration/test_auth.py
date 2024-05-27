"""Integration tests for waylay.sdk.auth module."""

from waylay.sdk.auth.provider import TokenCredentials, WaylayTokenAuth


async def test_client_authentication(waylay_test_client_credentials):
    """Test that WaylayTokenAuth resolves a token from client credentials."""
    auth = WaylayTokenAuth(waylay_test_client_credentials)
    assert auth.current_token is None
    token = await auth.assure_valid_token()
    assert auth.current_token is token
    assert_valid_token(token)


async def test_token_authentication(waylay_test_gateway_url, waylay_test_token_string):
    """Test authentication with  TokenCredentials."""
    token_cred = TokenCredentials(
        waylay_test_token_string, gateway_url=waylay_test_gateway_url
    )
    auth = WaylayTokenAuth(token_cred)
    assert auth.current_token is not None
    current_token = auth.current_token
    assert current_token == await auth.assure_valid_token()
    assert auth.current_token is current_token
    assert_valid_token(current_token)


def assert_valid_token(token):
    """Validate a token."""
    assert token.domain is not None
    assert token.subject is not None
    assert token.expires_at is not None
    assert token.is_valid
    assert token.permissions
    assert token.tenant is not None
    assert token is token.validate()
    assert token.groups is not None
