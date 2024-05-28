"""Client mixin for plugins."""

from __future__ import annotations

import sys
import warnings
from importlib.metadata import entry_points
from typing import Dict, Type

from ..api import ApiClient
from .base import PluginAccess, WaylayPlugin, WaylayService, WaylayTool, WithApiClient


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
        ep_group = "dynamic"
        ep_name = "waylay_sdk_plugins"
        if sys.version_info >= (3, 10):
            waylay_entry_points = entry_points(group=ep_group, name=ep_name)
        else:
            waylay_entry_points = [
                ep for ep in entry_points().get(ep_group, []) if ep.name == ep_name
            ]
        for ep in waylay_entry_points:
            for plugin_class in ep.load():
                self.register(plugin_class)

    def register(self, plugin_class: Type[WaylayPlugin]) -> WaylayPlugin | None:
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
        warnings.warn(message=f"Invalid plug class: {plugin_class}", stacklevel=1)
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
