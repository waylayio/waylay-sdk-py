"""REST client for the Waylay Platform."""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from .plugin.client import WithServicesAndTools
from .config.client import WaylayConfig, WithConfig, HttpClientOptions
from .api import ApiClient
from .api.http import AsyncClient


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

    alarms: "AlarmsService"
    data: "DataService"
    registry: "RegistryService"
    resources: "ResourcesService"
    rules: "RulesService"
    storage: "StorageService"

    def __init__(
        self,
        config: WaylayConfig | ApiClient,
        /,
        options: Optional[HttpClientOptions | AsyncClient] = None,
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
