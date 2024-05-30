"""Test suite for package `waylay.sdk.config`."""

from datetime import datetime
from typing import Iterator, Mapping

import pytest
from httpx import Request, Response

import waylay.sdk.auth.interactive
import waylay.sdk.config
from waylay.sdk import WaylayConfig
from waylay.sdk.auth.provider import (
    ClientCredentials,
    NoCredentials,
    TokenCredentials,
    WaylayTokenAuth,
)
from waylay.sdk.exceptions import ConfigError

from .fixtures import MOCK_API_URL, MOCK_DOMAIN, MOCK_TENANT_SETTINGS, WaylayTokenStub


def _mock_send_single_request_accounts(target, request: Request, *args) -> Response:
    return Response(status_code=200, request=request, json=MOCK_TENANT_SETTINGS)


def _mock_send_single_request_no_accounts(target, request: Request, *args) -> Response:
    return Response(status_code=403, request=request)


@pytest.fixture
def mock_token(mocker):
    """Mock the auth module to use a WaylayTokenStub."""
    mocker.patch(
        "waylay.sdk.auth.provider.WaylayTokenAuth._request_token_async",
        lambda *args: "",
    )
    mocker.patch(
        "waylay.sdk.auth.provider.WaylayTokenAuth._create_and_validate_token_async",
        lambda *args: WaylayTokenStub(),
    )
    mocker.patch(
        "waylay.sdk.auth.provider.WaylayTokenAuth._request_token_sync",
        lambda *args: "",
    )
    mocker.patch(
        "waylay.sdk.auth.provider.WaylayTokenAuth._create_and_validate_token_sync",
        lambda *args: WaylayTokenStub(),
    )


@pytest.fixture
def mock_httpx_accounts(mocker):
    """Mock the httpx module to return an accounts settings http response."""
    mocker.patch(
        "httpx._client.Client._send_single_request", _mock_send_single_request_accounts
    )


@pytest.fixture
def mock_httpx_no_accounts(mocker):
    """Mock the httpx module to fail the accounts settings http request."""
    mocker.patch(
        "httpx._client.Client._send_single_request",
        _mock_send_single_request_no_accounts,
    )


async def test_empty_config():
    """Test an unconfigured WaylayConfig."""
    cfg = WaylayConfig()
    assert isinstance(cfg.auth, WaylayTokenAuth)
    assert not cfg.local_settings
    assert isinstance(cfg.credentials, NoCredentials)
    for property_callback in [
        lambda: cfg.tenant_settings,
        lambda: cfg.tenant_settings,
        lambda: cfg.get_root_url("a_service"),
        lambda: cfg.get_root_url("api"),
    ]:
        with pytest.raises(ConfigError) as exc:
            property_callback()
        assert "Cannot get valid token: No credentials" in format(
            exc.value
        ) or "Cannot resolve tenant settings" in format(exc.value)


def test_config_settings():
    """Test handling of local settings."""
    cfg = WaylayConfig()
    local_settings = {"waylay_api": "xxx", "waylay_abc": "http://yyy"}
    cfg = WaylayConfig(settings=local_settings, fetch_tenant_settings=False)
    assert cfg.local_settings == local_settings
    assert not cfg.tenant_settings
    assert cfg.settings == local_settings
    assert cfg.gateway_url is None
    assert cfg.accounts_url is None
    assert isinstance(cfg.credentials, NoCredentials)
    assert cfg.get_root_url("a_service") is None
    assert cfg.get_root_url("api") == "https://xxx"
    assert cfg.get_root_url("abc") == "http://yyy"


def test_doc_config_settings():
    """Test doc urls."""
    cfg = WaylayConfig(fetch_tenant_settings=False)
    assert cfg.doc_url == waylay.sdk.config.model.DEFAULT_DOC_URL
    assert cfg.apidoc_url == waylay.sdk.config.model.DEFAULT_APIDOC_URL
    cfg = WaylayConfig(
        settings={"doc_url": "A", "apidoc_url": "B"}, fetch_tenant_settings=False
    )
    assert cfg.doc_url == "A"
    assert cfg.apidoc_url == "B"


def test_tenant_settings(mock_httpx_accounts, mock_token):
    """Test handling of tenant accounts settings."""
    local_settings = {"waylay_api": "xxx", "waylay_abc": "http://yyy/"}
    cfg = WaylayConfig(credentials=TokenCredentials("_"), settings=local_settings)
    assert cfg.local_settings == local_settings
    assert cfg.tenant_settings == MOCK_TENANT_SETTINGS
    assert cfg.settings == {**MOCK_TENANT_SETTINGS, **local_settings}
    assert cfg.credentials.token == "_"
    assert cfg.get_root_url("a_service") is None
    assert cfg.get_root_url("api") == "https://xxx"
    assert cfg.get_root_url("abc") == "http://yyy"


def test_gateway_settings(mock_httpx_accounts, mock_token):
    """Test resolution of gateway endpoints urls."""
    credentials = ClientCredentials("", "", gateway_url="https://gateway")
    cfg = WaylayConfig(credentials=credentials)
    assert not cfg.local_settings
    assert cfg.tenant_settings == MOCK_TENANT_SETTINGS
    assert cfg.settings == MOCK_TENANT_SETTINGS
    assert cfg.credentials == credentials
    assert cfg.get_root_url("api") == f"https://{MOCK_DOMAIN}/api"
    assert (
        cfg.get_root_url("srv", gateway_root_path="/srv/v1") == "https://gateway/srv/v1"
    )
    assert cfg.global_settings_url == "https://gateway/configs/v1/settings"


def test_empty_config_no_accounts(mock_httpx_no_accounts, mock_token):
    """Test handling of failure to retrieve accounts settings."""
    cfg = WaylayConfig(credentials=TokenCredentials("_"))
    assert isinstance(cfg.auth, WaylayTokenAuth)
    assert not cfg.local_settings
    assert not cfg.tenant_settings
    assert not cfg.settings
    assert cfg.get_root_url("a_service") is None
    assert cfg.get_root_url("api") is None


def test_get_set_root_url(mock_httpx_accounts, mock_token):
    """Test setting of root urls for services."""
    cfg = WaylayConfig(credentials=TokenCredentials("_"))

    assert cfg.get_root_url("a_service") is None
    assert (
        cfg.get_root_url("a_service", default_root_url="xxx.waylay.io")
        == "https://xxx.waylay.io"
    )

    assert (
        cfg.get_root_url(
            "a_service",
            default_root_url="https://xxx.waylay.io/xxx/v1",
            default_root_path="/xxx/v1",
        )
        == "https://xxx.waylay.io/xxx/v1"
    )

    cfg.set_root_url("a_service", "http://a_service.waylay.io/api/")

    assert cfg.get_root_url("a_service") == "http://a_service.waylay.io/api"
    assert (
        cfg.get_root_url("a_service", default_root_path="/api")
        == "http://a_service.waylay.io/api"
    )
    assert (
        cfg.get_root_url("a_service", default_root_path="/xxx/v1")
        == "http://a_service.waylay.io/api/xxx/v1"
    )

    cfg.set_local_settings(waylay_a_service="yyy.waylay.io")
    assert cfg.get_root_url("a_service") == "https://yyy.waylay.io"
    assert cfg.get_root_url("waylay_a_service") == "https://yyy.waylay.io"
    assert (
        cfg.get_root_url("a_service", default_root_path="/api")
        == "https://yyy.waylay.io/api"
    )
    assert (
        cfg.get_root_url("a_service", default_root_path="/xxx/v1")
        == "https://yyy.waylay.io/xxx/v1"
    )

    cfg.set_local_settings(waylay_a_service=None)
    assert cfg.get_root_url("a_service") is None

    assert cfg.get_root_url("api") == MOCK_API_URL


def test_representations(mock_httpx_accounts, mock_token):
    """Test the __str__ and __repr__ representations."""
    cfg = WaylayConfig(credentials=TokenCredentials("_"), settings=dict(a="b"))
    assert '"a": "b"' in str(cfg)
    assert '"token": "***' in str(cfg)
    assert '"a": "b"' in repr(cfg)
    assert '"token": "***' in repr(cfg)
    assert "***" in cfg.to_dict()["credentials"]["token"]
    assert cfg.to_dict(obfuscate=False)["credentials"]["token"] == "_"


def test_save_load_delete_profile(mock_token, monkeypatch, mocker):
    """Test saving, loading and deletion of config profiles."""
    responses: Iterator[Mapping] = iter(
        [
            dict(status_code=400),
            dict(status_code=401),
            dict(status_code=200, json=MOCK_TENANT_SETTINGS),
        ]
    )

    def respond_http(target, request, *args):
        kwargs = next(responses)
        return Response(request=request, **kwargs)

    mocker.patch("httpx._client.Client._send_single_request", respond_http)
    user_dialog = iter(
        [
            "use an api-gateway?",
            "y",
            "enter to confirm",
            "raising-400.waylay.io",
            "enter to confirm",
            "api-staging.waylay.io",
        ]
    )

    def mock_ask(prompt: str, secret: bool = False) -> str:
        assert secret == ("Secret" in prompt)
        assert next(user_dialog) in prompt
        return next(user_dialog)

    monkeypatch.setattr(waylay.sdk.auth.interactive, "ask", mock_ask)

    profile_name = f"_unit_test_{int(datetime.now().timestamp())}"
    with pytest.raises(ConfigError) as exc:
        WaylayConfig.load(profile_name, interactive=False)
    assert "not found" in format(exc.value)

    cfg = WaylayConfig(
        profile=profile_name, credentials=TokenCredentials("_"), settings=dict(a="b")
    )

    cfg.save()

    cfg_saved = WaylayConfig.load(profile_name)
    assert cfg_saved.get_settings(resolve=False) == cfg.get_settings(resolve=False)

    assert any(profile_name in profile for profile in WaylayConfig.list_profiles())

    WaylayConfig.delete(profile_name)
    WaylayConfig.delete(profile_name)

    with pytest.raises(ConfigError) as exc:
        WaylayConfig.load(profile_name, interactive=False)
    assert "not found" in format(exc.value)


def test_load_interactive(mocker, mock_token):
    """Test the interactive handling of loading a config."""
    mocker.patch(
        "waylay.sdk.config.model.request_client_credentials_interactive",
        lambda default_gateway_url: TokenCredentials("_"),
    )
    mocker.patch(
        "waylay.sdk.config.model.request_store_config_interactive",
        lambda profile, save_callback: save_callback(),
    )

    profile_name = f"_unit_test_{int(datetime.now().timestamp())}"
    cfg = WaylayConfig.load(profile_name)

    assert cfg.credentials.token == "_"

    assert any(profile_name in profile for profile in WaylayConfig.list_profiles())

    WaylayConfig.delete(profile_name)

    assert not any(profile_name in profile for profile in WaylayConfig.list_profiles())
