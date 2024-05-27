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

    # data broker service
    try:
        from waylay.services.data.service import DataService  # type: ignore
    except ImportError:

        class _DataServiceStub(_WaylayServiceStub):
            name = "data"
            title = "Data Broker (stub)"

        if not TYPE_CHECKING:
            DataService = _DataServiceStub

    # rules engine service
    try:
        from waylay.services.rules.service import RulesService  # type: ignore
    except ImportError:

        class _RulesServiceStub(_WaylayServiceStub):
            name = "rules"
            title = "Rules Engine (stub)"

        if not TYPE_CHECKING:
            RulesService = _RulesServiceStub

    # alarms service
    try:
        from waylay.services.alarms.service import AlarmsService  # type: ignore
    except ImportError:

        class _AlarmsServiceStub(_WaylayServiceStub):
            name = "alarms"
            title = "Alarms (stub)"

        if not TYPE_CHECKING:
            AlarmsService = _AlarmsServiceStub

    # resources service
    try:
        from waylay.services.resources.service import ResourcesService  # type: ignore
    except ImportError:

        class _ResourcesServiceStub(_WaylayServiceStub):
            name = "resources"
            title = "Resources (stub)"

        if not TYPE_CHECKING:
            ResourcesService = _ResourcesServiceStub

    # storage service
    try:
        from waylay.services.storage.service import StorageService  # type: ignore
    except ImportError:

        class _StorageServiceStub(_WaylayServiceStub):
            name = "storage"
            title = "Storage (stub)"

        if not TYPE_CHECKING:
            StorageService = _StorageServiceStub
