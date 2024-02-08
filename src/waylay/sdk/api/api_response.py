"""API response object."""

from __future__ import annotations
from typing import Dict, Optional, Generic, TypeVar
from dataclasses import dataclass, field

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
    headers: Optional[Dict[str, str]] = field(default_factory=dict)
    """HTTP headers."""