"""Parse credentials."""

from typing import Dict, Any

from .model import (
    NoCredentials,
    ClientCredentials,
    WaylayCredentials,
    ApplicationCredentials,
    TokenCredentials,
)


def parse_credentials(json_obj: Dict[str, Any]) -> WaylayCredentials:
    """Convert a parsed json representation to a WaylayCredentials object."""
    cred_type = json_obj.get("type", None)
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
