"""Test tools and services."""

from typing import List, Type

from waylay.sdk import WaylayPlugin

from .plugins import ExampleService, ExampleTool

PLUGINS: List[Type[WaylayPlugin]] = [ExampleService, ExampleTool]
