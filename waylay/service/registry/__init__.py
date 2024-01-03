"""Waylay Function Registry Service."""

from typing import TYPE_CHECKING

from ..base import WaylayServiceStub, WaylayService

try:
    from registry.service import RegistryService
    import registry.api as api
    # from registry import *
    registry_available = True

except ImportError:
    registry_available = False
    if not TYPE_CHECKING:
        RegistryService = WaylayServiceStub

try:
    import registry.models as models
    import registry.queries as queries
    registry_types_available = True

except ImportError:
    registry_types_available = False
