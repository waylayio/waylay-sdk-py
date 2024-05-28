"""REST client for the Waylay Platform."""

from __future__ import annotations

from typing import TYPE_CHECKING

from waylay.sdk.services.gateway import GatewayService

from .api import ApiClient
from .api.http import AsyncClient
from .config.client import HttpClientOptions, WaylayConfig, WithConfig
from .plugin.client import WithServicesAndTools

if TYPE_CHECKING:
    from .plugin.type_stubs import (
        AlarmsService,
        DataService,
        RegistryService,
        ResourcesService,
        RulesService,
        StorageService,
    )


class WaylayClient(WithConfig, WithServicesAndTools):
    """REST client for the Waylay Platform."""

    gateway: GatewayService
    alarms: AlarmsService
    data: DataService
    registry: RegistryService
    resources: ResourcesService
    rules: RulesService
    storage: StorageService

    def __init__(
        self,
        config: WaylayConfig | ApiClient,
        /,
        options: HttpClientOptions | AsyncClient | None = None,
    ):
        """Create a WaylayConfig instance."""
        client_config: WaylayConfig
        api_client: ApiClient
        if isinstance(config, ApiClient):
            api_client = config
            client_config = api_client.config
            if options:
                api_client.set_options(options)
        else:
            client_config = config
            api_client = ApiClient(client_config, options)
        WithConfig.__init__(self, client_config)
        WithServicesAndTools.__init__(self, api_client)

    def __repr__(self):
        """Get a technical string representation of this instance."""
        return (
            f"<{self.__class__.__name__}("
            f"services=[{','.join(self._services.keys())}],"
            f"tools=[{','.join(self._tools.keys())}],"
            f"config={self.config}"
            ")>"
        )
