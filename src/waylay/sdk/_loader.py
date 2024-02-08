"""Loads services or stubs."""

from typing import Dict, Type, TYPE_CHECKING
from .service import WaylayService, WaylayServiceStub

SERVICE_CLASSES: Dict[str, Type[WaylayService]] = {}

# registry service
try:
    from waylay.services.registry.service import RegistryService  # type: ignore
except ImportError:
    if not TYPE_CHECKING:
        RegistryService = WaylayServiceStub

SERVICE_CLASSES['registry'] = RegistryService
