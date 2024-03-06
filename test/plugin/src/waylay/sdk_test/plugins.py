"""Test plugins."""

from waylay.sdk import WaylayService, WaylayTool


class ExampleService(WaylayService):
    """Example service."""

    name = "exampleService"
    title = "Example Service"


class ExampleTool(WaylayTool):
    """Example tool."""

    name = "exampleTool"
    title = "Example Tool"
