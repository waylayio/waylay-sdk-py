"""Base classes for Waylay SDK Plugins."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Generic, Type, TypeVar

from ..api import ApiClient, HttpClientOptions
from ..api.exceptions import SyncCtxMgtNotSupportedError

P = TypeVar("P", bound="WaylayPlugin")
PI = TypeVar("PI", bound="WaylayPlugin")


class WithApiClient:
    """Base Waylay plugin class."""

    api_client: ApiClient

    def __init__(self, api_client: ApiClient):
        """Create a Waylay SDK plugin."""
        self.api_client = api_client

    async def __aenter__(self):
        """Initialize the api client."""
        self(None)
        self.api_client = await self.api_client.__aenter__()
        return self

    def __call__(self, http_options: HttpClientOptions | None = None):
        """Initialize the http client."""
        if self.api_client.is_closed:
            self.api_client.set_options(http_options)
        else:
            # create a new api client.
            # leave the previous client for other services.
            self.api_client = self.api_client.clone(http_options)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close the http client."""
        await self.api_client.aclose()

    def __enter__(self):
        """Dissallows sync context management."""
        raise SyncCtxMgtNotSupportedError(self)

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Disallow sync context management."""
        raise SyncCtxMgtNotSupportedError(self)


class WaylayPlugin(WithApiClient):
    """Plugin for the Waylay SDK client."""

    name: str = "__NO_NAME__"
    title: str = "__NO_TITLE__"
    description: str | None = None

    def __str__(self):
        """Get a plugin descripton."""
        return f"{self.name}: {self.title}"

    def __repr__(self):
        """Get a plugin representation."""
        return f"<{self.__class__.__name__}({self.name})>"


class WaylayService(WaylayPlugin):
    """Base Waylay service class."""


class PluginAccess(Mapping[str, P], Generic[P]):
    """A lookup API for tools or services."""

    base_class: Type[P]

    def __init__(self, items: Mapping[str, P], base_class: Type[P]):
        """Create accessor for SDK plugins."""
        self._items = items
        self.base_class = base_class

    def __getitem__(self, __key: str) -> P:
        """Get an SDK plugin by key."""
        return self._items.__getitem__(__key)

    def __iter__(self) -> Iterator[str]:
        """Iterate SDK plugin keys."""
        return self._items.__iter__()

    def __len__(self) -> int:
        """Count registred SDK plugin."""
        return self._items.__len__()

    def iter(self, item_class: Type[PI], name: str | None = None) -> Iterator[PI]:
        """Iterate over the plugins that satisfy the requirements."""
        if name:
            plug = self._items.get(name, None)
            if isinstance(plug, item_class):
                yield plug
            return
        for plug in self._items.values():
            if isinstance(plug, item_class):
                yield plug

    def select(self, item_class: Type[PI], name: str | None = None) -> PI | None:
        """Select the first SDK plugin that satifies the class and name requirements."""
        return next(self.iter(item_class, name), None)

    def require(self, item_class: Type[PI], name: str | None = None) -> PI:
        """Get the SDK plugin for the given class or raise a ConfigError."""
        item = self.select(item_class, name)
        if item is None:
            info = f"{item_class.__name__} '{name}'" if name else item_class.__name__
            raise AttributeError(f"{info} is not available.")
        return item

    def __getattr__(self, name: str) -> P:
        """Get a plugin by name."""
        return self.require(self.base_class, name)

    def __repr__(self):
        """Get string representation."""
        return repr(self._items)


class WaylayTool(WaylayPlugin):
    """A tool extension for the waylay sdk."""

    _services: PluginAccess[WaylayService]
    _tools: "PluginAccess[WaylayTool]"

    def __init__(
        self,
        api_client: ApiClient,
        *,
        services: PluginAccess[WaylayService],
        tools: "PluginAccess[WaylayTool]",
    ):
        """Create a Waylay Tool."""
        super().__init__(api_client)
        self._services = services
        self._tools = tools
