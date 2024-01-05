"""Waylay Function Registry Service."""

from typing import TYPE_CHECKING
from ._base import WaylayServiceStub


# registry service
try:
    from waylay.services.registry.service import RegistryService
    registry_available = True
except ImportError:
    registry_available = False
    if not TYPE_CHECKING:
        RegistryService = WaylayServiceStub

try:
    from waylay.services.registry import models, queries
    registry_types_available = True
except ImportError:
    registry_types_available = False
