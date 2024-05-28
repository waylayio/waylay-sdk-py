"""Default tools and services."""

from typing import List, Type

from waylay.sdk.services.gateway import GatewayService

from .base import WaylayPlugin

PLUGINS: List[Type[WaylayPlugin]] = [GatewayService]
