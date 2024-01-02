"""Integration tests for waylay.auth module."""
from waylay import (
    WaylayClient
)
import re

import waylay.auth_interactive
from waylay.config import (
    DEFAULT_PROFILE
)

# Matches versions like v1.2.3, v1.2, v1 or 0+untagged.1.gd418139
VERSION_STRING_PATTERN = r'(v\d+(\.\d+)?(\.\d+)?(\+.*)?|\d+\+[^.]+\.\d+\.\w+)'


def test_create_client_from_credentials(
    waylay_test_user_id, waylay_test_user_secret, waylay_test_gateway_url
):
    """Test authentication with client credentials."""
    waylay_client = WaylayClient.from_client_credentials(
        waylay_test_user_id, waylay_test_user_secret, gateway_url=waylay_test_gateway_url
    )
    assert waylay_client.config is not None

    cfg = waylay_client.config
    assert cfg.profile == DEFAULT_PROFILE

    cred = cfg.credentials
    assert cred.api_key == waylay_test_user_id
    assert cred.api_secret == waylay_test_user_secret
    assert cred.gateway_url == waylay_test_gateway_url
    assert cred.accounts_url is None

    assert isinstance(waylay_client.services, list)


def test_create_client_from_profile(
    waylay_test_user_id, waylay_test_user_secret, waylay_test_gateway_url, monkeypatch
):
    """Test profile creation dialog."""
    user_dialog = (response for response in [
        "alternate gateway", waylay_test_gateway_url,
        "apiKey", waylay_test_user_id,
        "apiSecret", waylay_test_user_secret,
        "store these credentials", 'N'
    ])

    def mock_ask(prompt: str) -> str:
        assert next(user_dialog) in prompt
        return next(user_dialog)

    def mock_ask_secret(prompt: str) -> str:
        assert 'Secret' in prompt
        assert next(user_dialog) in prompt
        return next(user_dialog)

    monkeypatch.setattr(waylay.auth_interactive, 'ask', mock_ask)
    monkeypatch.setattr(waylay.auth_interactive, 'ask_secret', mock_ask_secret)

    waylay_client = WaylayClient.from_profile('example', gateway_url=waylay_test_gateway_url)
    assert waylay_test_gateway_url == waylay_client.config.gateway_url
