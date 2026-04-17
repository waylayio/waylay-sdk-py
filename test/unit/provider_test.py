"""Tests for WaylayTokenAuth provider (token refresh logic)."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx
import jwt
import pytest

from waylay.sdk.auth.model import ClientCredentials, WaylayToken
from waylay.sdk.auth.provider import WaylayTokenAuth

GATEWAY_URL = "https://gateway.example.com"


def _make_token(exp_offset: int = 100_000) -> str:
    return jwt.encode(
        {
            "domain": "example.waylay.io",
            "tenant": "tenant-abc",
            "sub": "users/user-1",
            "exp": int(datetime.now().timestamp()) + exp_offset,
        },
        key="",
    )


@pytest.fixture
def token() -> str:
    return _make_token()


@pytest.fixture
def expired_token() -> str:
    return _make_token(exp_offset=-1)


def mock_token_response(token: str, refresh_token: str | None = None) -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    data: dict = {"token": token}
    if refresh_token:
        data["refresh_token"] = refresh_token
    response.json.return_value = data
    response.raise_for_status.return_value = None
    return response


@pytest.fixture
def auth() -> WaylayTokenAuth:
    return WaylayTokenAuth(
        ClientCredentials(
            api_key="aabbccddeeff00112233",
            api_secret="YWJjZGVmZ2hpamtsbW5vcHFyc3Q=",
            gateway_url=GATEWAY_URL,
        )
    )


def test_token_request_includes_renewal_for_client_credentials(auth):
    body = json.loads(auth._token_request(auth.credentials).content)
    assert body.get("renewal") is True


def test_parse_token_response_clears_refresh_token_when_absent(auth, token):
    auth._refresh_token = "old-rt"
    auth._parse_token_response(mock_token_response(token))
    assert auth._refresh_token is None


def test_assure_valid_token_uses_refresh_token_when_expired(auth, token, expired_token):
    auth.current_token = WaylayToken(expired_token)
    auth._refresh_token = "rt-valid"

    with patch.object(
        auth.http_client_sync,
        "send",
        return_value=mock_token_response(token, "rt-new"),
    ) as mock_send:
        result = auth.assure_valid_token()

    sent_req: httpx.Request = mock_send.call_args[0][0]
    assert "grant_type=refresh_token" in str(sent_req.url)
    assert auth._refresh_token == "rt-new"
    assert result.is_valid


@pytest.mark.anyio
async def test_assure_valid_token_async_uses_refresh_token_when_expired(
    auth, token, expired_token
):
    auth.current_token = WaylayToken(expired_token)
    auth._refresh_token = "rt-valid"

    captured: list[httpx.Request] = []

    async def fake_send(req, **_kwargs):
        captured.append(req)
        return mock_token_response(token, "rt-new")

    with patch.object(auth.http_client_async, "send", side_effect=fake_send):
        result = await auth.assure_valid_token_async()

    assert "grant_type=refresh_token" in str(captured[0].url)
    assert auth._refresh_token == "rt-new"
    assert result.is_valid


def test_assure_valid_token_falls_back_to_credentials_when_no_refresh_token(
    auth, token
):
    with patch.object(
        auth.http_client_sync,
        "send",
        return_value=mock_token_response(token),
    ) as mock_send:
        result = auth.assure_valid_token()

    sent_req: httpx.Request = mock_send.call_args[0][0]
    assert "grant_type=client_credentials" in str(sent_req.url)
    assert result.is_valid
