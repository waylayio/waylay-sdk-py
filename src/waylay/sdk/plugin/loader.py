"""Default tools and services."""

from typing import Type, List

from .base import WaylayPlugin
from waylay.sdk.services.gateway import GatewayService

PLUGINS: List[Type[WaylayPlugin]] = [GatewayService]
