"""Parse credentials."""

from typing import Any, Dict

from .model import (
    ApplicationCredentials,
    ClientCredentials,
    NoCredentials,
    TokenCredentials,
    WaylayCredentials,
)


def parse_credentials(json_obj: Dict[str, Any]) -> WaylayCredentials:
    """Convert a parsed json representation to a WaylayCredentials object."""
    cred_type = json_obj.get("type")
    if cred_type is None:
        raise ValueError("invalid json for credentials: missing type")

    for clz in [
        NoCredentials,
        ClientCredentials,
        ApplicationCredentials,
        TokenCredentials,
    ]:
        if clz.credentials_type == cred_type:  # type: ignore
            return clz(**{k: v for k, v in json_obj.items() if k != "type"})

    raise ValueError(f"cannot parse json for credential type {cred_type}")
