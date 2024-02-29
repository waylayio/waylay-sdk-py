"""API response object."""

from __future__ import annotations
from typing import Generic, TypeVar
from dataclasses import dataclass, field

from .http import HeaderTypes

T = TypeVar("T")


@dataclass
class ApiResponse(Generic[T]):
    """API response object."""

    status_code: int
    """HTTP status code."""
    data: T
    """Deserialized data given the data type."""
    raw_data: bytes
    """Raw data (HTTP response body)"""
    headers: HeaderTypes = field(default_factory=dict)
    """HTTP headers."""
