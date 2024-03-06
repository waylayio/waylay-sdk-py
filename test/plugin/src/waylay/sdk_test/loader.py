"""Test tools and services."""

from typing import Type, List

from waylay.sdk import WaylayPlugin

from .plugins import ExampleService, ExampleTool

PLUGINS: List[Type[WaylayPlugin]] = [ExampleService, ExampleTool]
