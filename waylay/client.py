"""REST client for the Waylay Platform."""

from collections import defaultdict
from typing import (
    Optional, TypeVar, List, Mapping, Type, Iterable, Dict
)
import logging
import sys
if sys.version_info < (3, 10):
    from importlib_metadata import entry_points
else:
    from importlib.metadata import entry_points

from .service import (
    WaylayService,
    WaylayRESTService,
    WaylayServiceContext,
    ByomlService,
    TimeSeriesService,
    ResourcesService,
    StorageService,
    UtilService,
    ETLService,
    DataService,
    QueriesService,
    SERVICES
)

from .service.analytics import AnalyticsServiceLegacy
from .exceptions import ConfigError

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

S = TypeVar('S', bound=WaylayService)
logger = logging.getLogger(__name__)


class WaylayClient():
    """REST client for the Waylay Platform."""

    analytics: AnalyticsServiceLegacy = AnalyticsServiceLegacy()
    byoml: ByomlService
    config: WaylayConfig
    timeseries: TimeSeriesService
    resources: ResourcesService
    storage: StorageService
    util: UtilService
    etl: ETLService
    data: DataService
    queries: QueriesService

    @classmethod
    def from_profile(
        cls, profile: str = DEFAULT_PROFILE,
        *, interactive=True, gateway_url=None
    ):
        """Create a WaylayClient named profile.

        Uses credentials from environment variables or a locally stored configuration.
        """
        return cls(WaylayConfig.load(
            profile, interactive=interactive, gateway_url=gateway_url
        ))

    @classmethod
    def from_client_credentials(
        cls, api_key: str, api_secret: str, *,
        gateway_url=None, accounts_url=None,
        settings: TenantSettings = None
    ):
        """Create a WaylayClient using the given client credentials."""
        credentials = ClientCredentials(
            api_key, api_secret, **_auth_urls(gateway_url, accounts_url, settings)
        )
        return cls.from_credentials(credentials, settings=settings)

    @classmethod
    def from_token(
        cls, token_string: str, *,
        gateway_url=None, accounts_url=None, settings: TenantSettings = None
    ):
        """Create a WaylayClient using a waylay token."""
        credentials = TokenCredentials(
            token_string, **_auth_urls(gateway_url, accounts_url, settings)
        )
        return cls.from_credentials(credentials, settings=settings)

    @classmethod
    def from_credentials(
        cls, credentials: WaylayCredentials, settings: TenantSettings = None
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
        self.load_services()

    @property
    def services(self) -> List[WaylayService]:
        """Get the services that are available through this client."""
        return self._services

    @property
    def service_context(self) -> WaylayServiceContext:
        """Get the WaylayServiceContext view on this client."""
        return self

    def configure(self, config: WaylayConfig):
        """Update this client with the given configuration."""
        self.config = config
        for srv in self._services:
            srv.configure(self.config, context=self.service_context)

    def list_root_urls(self) -> Mapping[str, Optional[str]]:
        """List the currently configured root url for each of the registered REST services."""
        return {
            srv.config_key: srv.get_root_url()
            for srv in self._services if isinstance(srv, WaylayRESTService)
        }

    def __repr__(self):
        """Get a technical string representation of this instance."""
        return (
            f"<{self.__class__.__name__}("
            f"services=[{','.join(list(srv_class.service_key for srv_class in self.services))}],"
            f"config={self.config}"
            ")>"
        )

    def load_services(self):
        """Load all services that are registered with the `waylay_services` entry point."""
        registered_service_classes = [
            srv_class
            for entry_point in entry_points(group='waylay_services')
            for srv_class in entry_point.load()
        ]
        if not registered_service_classes:
            logger.warning(
                "The package %s "
                "seems not to be installed properly. "
                "If it was installed during this runtime session, "
                "please restart the runtime before continuing.",
                __package__
            )
            registered_service_classes = SERVICES
        self.register_service(*registered_service_classes)

    def register_service(self, *service_class: Type[S]) -> Iterable[S]:
        """Create and initialize one or more service of the given class.

        Replaces any existing with the same service_key.
        """
        new_services = [srv_class() for srv_class in service_class]
        new_plugin_priorities: Dict[str, int] = defaultdict(int)
        for srv in new_services:
            new_plugin_priorities[srv.service_key] = max(
                srv.plugin_priority, new_plugin_priorities[srv.service_key]
            )

        # delete existing services
        to_delete_service_index = [
            idx for idx, srv in enumerate(self._services)
            if (
                srv.service_key in new_plugin_priorities and
                srv.plugin_priority <= new_plugin_priorities[srv.service_key]
            )
        ]

        for idx in reversed(to_delete_service_index):
            # delete indexed entries in list from the back
            del self._services[idx]

        # change service list
        for srv in new_services:
            if srv.plugin_priority == new_plugin_priorities[srv.service_key]:
                self._services.append(srv)
                setattr(self, srv.service_key, srv)

        # reconfigure
        self.configure(self.config)
        return new_services

    # implements WaylayServiceContext protocol
    def get(self, service_class: Type[S]) -> Optional[S]:
        """Get the service instance for the provided class, if it is registered.

        Implements the `WaylayServiceContext.get` protocol.
        """
        for srv in self._services:
            if isinstance(srv, service_class):
                return srv
        return None

    def require(self, service_class: Type[S]) -> S:
        """Get the service instance for the given class or raise a ConfigError.

        Implements the `WaylayServiceContext.require` protocol.
        """
        srv = self.get(service_class)
        if srv is None:
            raise ConfigError(f"service {service_class.__name__} is not available.")
        return srv

    def list(self) -> List[WaylayService]:
        """List all registered Services.

        Implements the `WaylayServiceContext.list` protocol.
        """
        return list(self._services)


def _auth_urls(gateway_url=None, accounts_url=None, settings: TenantSettings = None):
    if settings:
        gateway_url = gateway_url or settings.get(SERVICE_KEY_GATEWAY)
        accounts_url = accounts_url or settings.get(SERVICE_KEY_ACCOUNTS)
    return {'gateway_url': gateway_url, 'accounts_url': accounts_url}
