"""Default tools and services."""

from __future__ import annotations

from waylay.sdk.services.gateway import GatewayService

from .base import WaylayPlugin

PLUGINS: list[type[WaylayPlugin]] = [GatewayService]

__all__ = ["WaylayPlugin"]
