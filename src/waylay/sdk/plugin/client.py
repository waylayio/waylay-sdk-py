"""Client mixin for plugins."""

from typing import Type, Dict, Optional
from importlib.metadata import entry_points
import warnings

from .base import (
    WaylayService, WaylayTool,
    WithApiClient,
    WaylayPlugin, PluginAccess
)
from ..api import ApiClient


class WithServicesAndTools(WithApiClient):
    """Client as loader of service and tool plugins."""

    services: PluginAccess[WaylayService]
    tools: PluginAccess[WaylayTool]
    _services: Dict[str, WaylayService]
    _tools: Dict[str, WaylayTool]

    def __init__(self, api_client: ApiClient):
        """Create a WaylayConfig instance."""
        super().__init__(api_client)
        self._services = {}
        self.services = PluginAccess[WaylayService](self._services, WaylayService)
        self._tools = {}
        self.tools = PluginAccess[WaylayTool](self._tools, WaylayTool)
        self._load_plugins()

    def _load_plugins(self):
        for entry_point in entry_points(group='dynamic', name='waylay_sdk_plugins'):
            for plugin_class in entry_point.load():
                self.register(plugin_class)

    def register(self, plugin_class: Type[WaylayPlugin]) -> Optional[WaylayPlugin]:
        """Register and instantiate plugin class."""
        if issubclass(plugin_class, WaylayService):
            service = plugin_class(self.api_client)
            self._services[service.name] = service
            return service
        if issubclass(plugin_class, WaylayTool):
            tool = plugin_class(
                self.api_client,
                services=self.services,
                tools=self.tools,
            )
            self._tools[tool.name] = tool
            return tool
        warnings.warn(f'Invalid plug class: {plugin_class}')
        return None

    def __getattr__(self, name: str):
        """Get plugin by name."""
        if name in self._services:
            return self._services[name]
        if name in self._tools:
            return self._tools[name]
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )
