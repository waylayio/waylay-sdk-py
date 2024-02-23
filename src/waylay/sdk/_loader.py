"""Loads services or stubs."""
from importlib import import_module
from typing import Dict, Type, TYPE_CHECKING
from .service import WaylayService, WaylayServiceStub

_SERVICE_NAMES = ["broker", "registry"]


def load_services() -> Dict[str, Type[WaylayService]]:
    """Load service plugins."""
    service_classes: Dict[str, Type[WaylayService]] = {}
    for service_name in _SERVICE_NAMES:
        try:
            module = import_module("waylay.services.{0}.service".format(service_name))
            service_cls = getattr(module, "{0}Service".format(service_name.title()))
        except (ImportError, AttributeError):
            service_cls = WaylayServiceStub
        service_classes[service_name] = service_cls
    return service_classes


if TYPE_CHECKING:
    # registry service
    try:
        from waylay.services.registry.service import RegistryService  # type: ignore
    except ImportError:
        if not TYPE_CHECKING:
            RegistryService = WaylayServiceStub

    # broker service
    try:
        from waylay.services.broker.service import BrokerService  # type: ignore
    except ImportError:
        if not TYPE_CHECKING:
            BrokerService = WaylayServiceStub
