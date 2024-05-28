"""Client configuration."""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import Any, Type

import httpx
from appdirs import user_config_dir

from ..auth import (
    AuthError,
    NoCredentials,
    WaylayCredentials,
    WaylayToken,
    parse_credentials,
)
from ..auth.interactive import (
    DEFAULT_GATEWAY_URL,
    _root_url_for,
    ask_gateway,
    request_client_credentials_interactive,
    request_migrate_to_gateway_interactive,
    request_store_config_interactive,
)
from ..auth.provider import (
    CredentialsCallback,
    WaylayTokenAuth,
)
from ..exceptions import ConfigError

log = logging.getLogger(__name__)

# http client dependencies
_http = httpx


def _http_get_global_settings(url, auth):
    return _http.get(url, auth=auth)


TenantSettings = Mapping[str, str]

Settings = MutableMapping[str, str]

DEFAULT_PROFILE = "_default_"
SERVICE_KEY_GATEWAY = "waylay_gateway"
SERVICE_KEY_ACCOUNTS = "waylay_accounts"
DEFAULT_DOC_URL: str = "https://docs.waylay.io/#"
DEFAULT_APIDOC_URL: str = "https://docs.waylay.io/openapi/public/redocly"
DOC_URL_KEY: str = "doc_url"
APIDOC_URL_KEY: str = "apidoc_url"


class WaylayConfig:
    """Manages the authentication and endpoint configuration for the Waylay Platform."""

    profile: str
    _auth: WaylayTokenAuth
    _local_settings: Settings
    _tenant_settings: TenantSettings | None = None
    _token_auth_provider: Type[WaylayTokenAuth] = WaylayTokenAuth

    def __init__(
        self,
        credentials: WaylayCredentials | None = None,
        profile: str = DEFAULT_PROFILE,
        settings: TenantSettings | None = None,
        fetch_tenant_settings=True,
        credentials_callback: CredentialsCallback | None = None,
    ):
        """Create a WaylayConfig."""
        self.profile = profile
        if credentials is None:
            credentials = NoCredentials()
        self._local_settings = {}
        if settings:
            self.set_local_settings(**settings)
        self._auth = self._token_auth_provider(
            credentials, credentials_callback=credentials_callback
        )
        if not fetch_tenant_settings:
            self._tenant_settings = {}

    @property
    def credentials(self):
        """Get current credentials.

        As configured or returned by last callback.

        """
        return self._auth.credentials

    def get_root_url(
        self,
        config_key: str,
        *,
        default_root_url: str | None = None,
        gateway_root_path: str | None = None,
        default_root_path: str = "",
        resolve_settings: bool = True,
    ) -> str | None:
        """Get the root url for a waylay service."""
        config_key = _root_url_key_for(config_key)
        # only resolve remote settings if no gateway available
        use_gateway = gateway_root_path is not None and self.gateway_url is not None
        default_url = (
            f"{self.gateway_url}{gateway_root_path}"
            if use_gateway
            else default_root_url
        )
        settings = self.local_settings
        if not use_gateway:
            resolve_settings = (
                resolve_settings
                # do not lookup settings for the bootstrap services
                and config_key not in (SERVICE_KEY_ACCOUNTS)
            )
            settings = self.get_settings(resolve=resolve_settings)
        url_override = settings.get(config_key)
        if url_override is not None:
            url_override = _root_url_for(url_override)
            if url_override.endswith(default_root_path):
                return url_override
            else:
                return f"{url_override}{default_root_path}"
        if default_url is not None:
            return _root_url_for(default_url)
        return None

    def set_root_url(self, config_key: str, root_url: str | None):
        """Override the root url for the given server.

        Will persist on `save`.
        Setting a `None` value will remove the override.

        """
        config_key = _root_url_key_for(config_key)
        self.set_local_settings(**{config_key: root_url})

    @property
    def accounts_url(self) -> str | None:
        """Get the accounts url."""
        url = self.credentials.accounts_url
        return _root_url_for(url) if url else None

    @property
    def gateway_url(self):
        """Get the gateway url."""
        url = self.credentials.gateway_url
        return _root_url_for(url) if url else None

    @property
    def doc_url(self) -> str:
        """Get the root url of the documentation site."""
        return self.settings.get(DOC_URL_KEY, DEFAULT_DOC_URL)

    @property
    def apidoc_url(self) -> str:
        """Get the root url of the api documentation site."""
        return self.settings.get(APIDOC_URL_KEY, DEFAULT_APIDOC_URL)

    @property
    def tenant_settings(self) -> TenantSettings:
        """Get the tenant settings as stored on accounts.

        Will fetch settings when not present and initialised with
        'fetch_tenant_settings=True'.

        """
        if self._tenant_settings is None:
            self._tenant_settings = self._request_settings()

        return self._tenant_settings

    @property
    def local_settings(self) -> TenantSettings:
        """Get the settings overrides for this configuration.

        These include the endpoint overrides that are stored with the
        profile.

        """
        return self._local_settings

    def set_local_settings(self, **settings: str | None) -> TenantSettings:
        """Set a local endpoint url override for a service."""
        for config_key, value in settings.items():
            if value is None and config_key in self._local_settings:
                del self._local_settings[config_key]
            if value is not None:
                self._local_settings[config_key] = value
        return self.local_settings

    @property
    def settings(self) -> TenantSettings:
        """Get settings, from tenant configuration and local overrides."""
        return self.get_settings(resolve=True)

    def get_settings(self, resolve=True) -> TenantSettings:
        """Get the tenant settings.

        As resolved form the accounts backend, and overridden with local
        settings. If `resolve=True`, fetch and cache tenant settings
        from the accounts backend.

        """
        return {
            **(self.tenant_settings if resolve else self._tenant_settings or {}),
            **self.local_settings,
        }

    async def get_valid_token(self) -> WaylayToken:
        """Get the current valid authentication token or fail."""
        if isinstance(self.auth, WaylayTokenAuth):
            try:
                return await self.auth.assure_valid_token_async()
            except AuthError as exc:
                raise ConfigError(f"Cannot get valid token: {exc}") from exc
        raise ConfigError("not using token authentication")  # pragma: no cover

    @property
    def auth(self) -> _http.Auth:
        """Get the current http authentication interceptor."""
        return self._auth

    @property
    def global_settings_url(self) -> str:
        """Get the REST url that fetches global settings."""
        root_url = self.get_root_url(
            "api",
            default_root_url=None,
            gateway_root_path="/configs/v1",
            resolve_settings=False,
        )
        return f"{root_url}/settings"

    def _request_settings(self) -> TenantSettings:
        try:
            settings_resp = _http_get_global_settings(
                self.global_settings_url, auth=self.auth
            )
            settings_resp.raise_for_status()
            return {
                key: value
                for key, value in settings_resp.json().items()
                if key.startswith("waylay_")
            }
        except _http.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                log.warning(
                    "You are not authorised to fetch tenant settings.\n"
                    "The Waylay SAAS defaults will be used, unless you\n"
                    "provide explicit overrides in the SDK Configuration profile."
                )
                return {}
            raise ConfigError(
                "Cannot resolve tenant settings"
            ) from exc  # pragma: no cover
        except (_http.HTTPError, AuthError) as exc:
            raise ConfigError(
                "Cannot resolve tenant settings"
            ) from exc  # pragma: no cover

    # config persistency methods
    @classmethod
    def config_file_path(cls, profile: str = DEFAULT_PROFILE) -> str:
        """Compute the default OS path used to store this configuration."""
        return os.path.join(
            user_config_dir("Waylay"), "python_sdk", f".profile.{profile}.json"
        )

    @classmethod
    def load(
        cls,
        profile: str = DEFAULT_PROFILE,
        *,
        interactive: bool = True,
        skip_error: bool = False,
        gateway_url: str = DEFAULT_GATEWAY_URL,
    ):
        """Load a stored waylay configuration."""
        profile = DEFAULT_PROFILE if profile is None else profile
        try:
            with open(cls.config_file_path(profile), encoding="utf-8") as config_file:
                config_json = json.load(config_file)
            waylay_config = cls.from_dict(config_json)
            if not waylay_config.gateway_url:
                msg = (
                    f"WaylayConfig profile '{profile}' uses a "
                    f"legacy accounts endpoint {waylay_config.accounts_url}."
                )
                if interactive:
                    if request_migrate_to_gateway_interactive(profile, msg):
                        gateway_url = ask_gateway(waylay_config.accounts_url)
                        waylay_config.credentials.gateway_url = gateway_url
                        waylay_config.save()
                else:
                    log.warning(msg)
            return waylay_config
        except (FileNotFoundError, ValueError) as exc:
            msg = f"Config profile '{profile}' not found or invalid."
            if skip_error:
                log.warning(msg)
                return None
            if not interactive:
                raise ConfigError(msg) from exc
            credentials = request_client_credentials_interactive(
                default_gateway_url=gateway_url
            )
            instance = cls(credentials, profile=profile)
            request_store_config_interactive(profile, save_callback=instance.save)
            return instance

    @classmethod
    def from_dict(cls, config_json: Mapping[str, Any]):
        """Create a WaylayConfig from a dict representation."""
        config_json = dict(config_json)
        if "credentials" in config_json:
            config_json["credentials"] = parse_credentials(config_json["credentials"])
        return cls(**config_json)

    def to_dict(self, obfuscate=True):
        """Get the (obfuscated) attributes of this WaylayConfig.

        Secret credentials are obfuscated.

        """
        return {
            "credentials": self.credentials.to_dict(obfuscate),
            "profile": self.profile,
            "settings": self.local_settings,
        }

    def save(self) -> str:
        """Save the configuration as specified in the profile.

        Returns the save location.

        """
        config_path = Path(self.config_file_path(self.profile))
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, mode="w", encoding="utf-8") as config_file:
            json.dump(self.to_dict(obfuscate=False), config_file)
            log.info("wrote waylay configuration: %s", config_path)
        return str(config_path)

    @classmethod
    def delete(cls, profile: str = DEFAULT_PROFILE) -> str:
        """Delete a stored profile.

        Returns the deleted location.

        """
        config_path = Path(cls.config_file_path(profile))
        if config_path.exists():
            config_path.unlink()
            log.warning("waylay configuration removed: %s", config_path)
        else:
            log.warning("waylay configuration not found: %s", config_path)
        return str(config_path)

    @classmethod
    def list_profiles(cls):
        """List stored config profiles."""
        config_dir = Path(cls.config_file_path()).parent
        return {
            profile_match[1]: str(config_file)
            for config_file in config_dir.iterdir()
            for profile_match in [re.match(r"\.profile\.(.*)\.json", config_file.name)]
            if profile_match
        }

    def __repr__(self):
        """Show the implementation class an main attributes."""
        return f"<WaylayConfig({str(self)})>"

    def __str__(self):
        """Show the main (obfuscated) attributes as a string."""
        return json.dumps(self.to_dict(obfuscate=True))


def _root_url_key_for(config_key: str):
    if config_key.startswith("waylay_"):
        return config_key
    return f"waylay_{config_key}"
