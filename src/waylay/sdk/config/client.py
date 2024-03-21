"""Config mixin for the SDK client."""

from __future__ import annotations
from typing import Optional

from ..auth import (
    WaylayCredentials,
    ClientCredentials,
    TokenCredentials,
)

from .model import (
    WaylayConfig,
    TenantSettings,
    DEFAULT_PROFILE,
    SERVICE_KEY_GATEWAY,
    SERVICE_KEY_ACCOUNTS,
)
from ..api import HttpClientOptions, AsyncClient


class WithConfig:
    """A configuration Mixin."""

    config: WaylayConfig
    http_options: HttpClientOptions

    def __init__(self, config: WaylayConfig, **args):
        """Create a configured entity."""
        self.config = config

    @classmethod
    def from_profile(
        cls,
        profile: str = DEFAULT_PROFILE,
        *,
        interactive=True,
        gateway_url=None,
        options: Optional[HttpClientOptions | AsyncClient] = None,
    ):
        """Create a WaylayClient named profile.

        Uses credentials from environment variables or a locally stored
        configuration.

        """
        return cls(
            WaylayConfig.load(
                profile, interactive=interactive, gateway_url=gateway_url
            ),
            options=options,
        )

    @classmethod
    def from_client_credentials(
        cls,
        api_key: str,
        api_secret: str,
        *,
        gateway_url=None,
        accounts_url=None,
        settings: Optional[TenantSettings] = None,
        options: Optional[HttpClientOptions | AsyncClient] = None,
    ):
        """Create a WaylayClient using the given client credentials."""
        credentials = ClientCredentials(
            api_key, api_secret, **_auth_urls(gateway_url, accounts_url, settings)
        )
        return cls.from_credentials(credentials, settings=settings, options=options)

    @classmethod
    def from_token(
        cls,
        token_string: str,
        *,
        gateway_url=None,
        accounts_url=None,
        settings: Optional[TenantSettings] = None,
        options: Optional[HttpClientOptions | AsyncClient] = None,
    ):
        """Create a WaylayClient using a waylay token."""
        credentials = TokenCredentials(
            token_string, **_auth_urls(gateway_url, accounts_url, settings)
        )
        return cls.from_credentials(credentials, settings=settings, options=options)

    @classmethod
    def from_credentials(
        cls,
        credentials: WaylayCredentials,
        settings: Optional[TenantSettings] = None,
        options: Optional[HttpClientOptions | AsyncClient] = None,
    ):
        """Create a WaylayClient using the given client credentials."""
        return cls(
            WaylayConfig(
                credentials,
                settings=settings,
            ),
            options=options,
        )


def _auth_urls(
    gateway_url=None, accounts_url=None, settings: Optional[TenantSettings] = None
):
    if settings:
        gateway_url = gateway_url or settings.get(SERVICE_KEY_GATEWAY)
        accounts_url = accounts_url or settings.get(SERVICE_KEY_ACCOUNTS)
    return {"gateway_url": gateway_url, "accounts_url": accounts_url}
