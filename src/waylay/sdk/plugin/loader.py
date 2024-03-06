"""Default tools and services."""

from typing import Type, List

from .base import WaylayPlugin

# no default services or tools for now.
PLUGINS: List[Type[WaylayPlugin]] = []
