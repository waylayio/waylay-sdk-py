"""REST client for the Waylay Platform."""

from typing import List, Optional, Type

from .service import WaylayService
from ._loader import SERVICE_CLASSES, RegistryService
from .api import ApiClient

from .config import (
    WaylayConfig,
    TenantSettings,
    DEFAULT_PROFILE,
    SERVICE_KEY_GATEWAY,
    SERVICE_KEY_ACCOUNTS
)
from .auth import (
    WaylayCredentials,
    ClientCredentials,
    TokenCredentials,
)


class WaylayClient():
    """REST client for the Waylay Platform."""

    config: WaylayConfig
    api_client: ApiClient

    # services
    registry: 'RegistryService'
    # TODO, do we want to load the services dynamically like in previous waylay-py
    # + only register installed services
    # - lose type info

    @classmethod
    def from_profile(
        cls, profile: str = DEFAULT_PROFILE,
        *, interactive=True, gateway_url=None
    ):
        """Create a WaylayClient named profile.

        Uses credentials from environment variables or a locally stored
        configuration.

        """
        return cls(WaylayConfig.load(
            profile, interactive=interactive, gateway_url=gateway_url
        ))

    @classmethod
    def from_client_credentials(
        cls, api_key: str, api_secret: str, *,
        gateway_url=None, accounts_url=None,
        settings: Optional[TenantSettings] = None
    ):
        """Create a WaylayClient using the given client credentials."""
        credentials = ClientCredentials(
            api_key, api_secret, **_auth_urls(gateway_url, accounts_url, settings)
        )
        return cls.from_credentials(credentials, settings=settings)

    @classmethod
    def from_token(
        cls, token_string: str, *,
        gateway_url=None, accounts_url=None, settings: Optional[TenantSettings] = None
    ):
        """Create a WaylayClient using a waylay token."""
        credentials = TokenCredentials(
            token_string, **_auth_urls(gateway_url, accounts_url, settings)
        )
        return cls.from_credentials(credentials, settings=settings)

    @classmethod
    def from_credentials(
        cls, credentials: WaylayCredentials, settings: Optional[TenantSettings] = None
    ):
        """Create a WaylayClient using the given client credentials."""
        return cls(WaylayConfig(
            credentials,
            settings=settings
        ))

    def __init__(self, config: WaylayConfig):
        """Create a WaylayConfig instance."""
        self._services: List[WaylayService] = []
        self.config = config
        self.load_services(config)

    def __repr__(self):
        """Get a technical string representation of this instance."""
        return (
            f"<{self.__class__.__name__}("
            # f"services=[{','.join(list(srv_class.service_key for srv_class in self.services))}],"
            f"config={self.config}"
            ")>"
        )

    @property
    def services(self) -> List[WaylayService]:
        """Get the services that are available through this client."""
        return self._services

    def configure(self, config: WaylayConfig):
        """Update this client with the given configuration."""
        self.config = config
        for srv in self._services:
            srv.configure(ApiClient(config))

    def load_services(self, config: WaylayConfig):
        """Load all services that are installed."""
        self.api_client = ApiClient(config)
        for service_name, service_class in SERVICE_CLASSES.items():
            self._register_service(service_name, service_class)

    def _register_service(self, service_name: str, service_class: Type[WaylayService]):
        service = service_class(self.api_client, service_name)
        self._services.append(service)
        setattr(self, service_name, service)


def _auth_urls(gateway_url=None, accounts_url=None, settings: Optional[TenantSettings] = None):
    if settings:
        gateway_url = gateway_url or settings.get(SERVICE_KEY_GATEWAY)
        accounts_url = accounts_url or settings.get(SERVICE_KEY_ACCOUNTS)
    return {'gateway_url': gateway_url, 'accounts_url': accounts_url}
