"""Type imports for known services."""

from typing import TYPE_CHECKING
from .base import WaylayService


class _WaylayServiceStub(WaylayService):
    """Dummy Waylay service stub."""

    def __getattr__(self, name):
        """Get attribute."""
        raise ImportError(f"Waylay '{self.title}' service is not installed")

    def __bool__(self):
        """Cast to boolean."""
        return False


if TYPE_CHECKING:
    # registry service
    try:
        from waylay.services.registry.service import RegistryService  # type: ignore
    except ImportError:

        class _RegistryServiceStub(_WaylayServiceStub):
            name = "registry"
            title = "Function Registry (stub)"

        if not TYPE_CHECKING:
            RegistryService = _RegistryServiceStub

    # broker services
    try:
        from waylay.services.broker.service import BrokerService  # type: ignore
    except ImportError:

        class _BrokerServiceStub(_WaylayServiceStub):
            name = "broker"
            title = "Data Broker (stub)"

        if not TYPE_CHECKING:
            BrokerService = _BrokerServiceStub
