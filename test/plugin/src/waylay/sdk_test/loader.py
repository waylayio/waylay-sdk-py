"""Test tools and services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .plugins import ExampleService, ExampleTool

if TYPE_CHECKING:
    from waylay.sdk import WaylayPlugin

PLUGINS: list[type[WaylayPlugin]] = [ExampleService, ExampleTool]
