"""Interactive authentication callback for client credentials."""

from __future__ import annotations

import logging
import re
import urllib.parse
from getpass import getpass

import httpx

from .model import AuthError, ClientCredentials, WaylayCredentials

DEFAULT_GATEWAY_URL = "https://api.waylay.io"
DEFAULT_ACCOUNTS_URL = "https://accounts-api.waylay.io"
ACCOUNTS_USERS_ME_PATH = "/accounts/v1/users/me"

_http = httpx
log = logging.getLogger(__name__)


def tell(message: str):
    """Show an interactive authentication message."""
    print(message)


def ask(prompt: str) -> str:
    """Prompt user for information."""
    return input(prompt)


def ask_secret(prompt: str) -> str:
    """Prompt user for credential information."""
    return getpass(prompt=prompt)


def ask_yes_no(prompt: str, default: bool | None = None) -> bool:
    """Keep prompting the user until response starts with a true or false character."""
    while True:
        resp = ask(prompt)
        if not resp and default is not None:
            return default
        resp_char = resp.lower()[0]
        if resp_char in ("n", "f"):
            return False
        if resp_char in ("t", "y"):
            return True


def ask_gateway(default_gateway_url: str):
    """Ask for the gateway api in an interactive dialog."""
    gateway_url: str = _gateway_url_for(default_gateway_url)
    gateway_validated = False
    while not gateway_validated:
        tell(f"Proposed api gateway: {gateway_url}")
        tell("Please confirm, or specify a gateway by platform id, hostname or url.")
        tell(
            """Examples:
    'enterprise' (or 'api.waylay.io') for the Enterprise platform,
    'https://waylay-api.mycompany.com' as a custom endpoint url
        """
        )
        gateway_url = (
            ask(
                "> Press enter to confirm, "
                f"or specify an alternate gateway [{gateway_url}]: "
            )
            or gateway_url
        )
        gateway_url = _gateway_url_for(gateway_url)
        try:
            gateway_status_resp = _http.get(f"{gateway_url}{ACCOUNTS_USERS_ME_PATH}")
        except Exception as err:
            tell(f"Cannot connect to '{gateway_url}: {err}")
            gateway_url = _gateway_url_for(default_gateway_url)
        else:
            gateway_status = gateway_status_resp.status_code
            gateway_validated = gateway_status == 401
            if not gateway_validated:
                msg = (
                    "Should require authentication"
                    if gateway_status == 200
                    else gateway_status_resp.reason_phrase
                )
                tell(f"Not a gateway URL: '{gateway_url}': {msg}")
                gateway_url = _gateway_url_for(default_gateway_url)
            else:
                tell(f"Using gateway: {gateway_url}")
    return gateway_url


def request_migrate_to_gateway_interactive(profile, msg):
    """Asks to migrate to an api-gateway configuration."""
    tell(msg)
    tell(
        "NOTE: Migrating to an api-gateway will make this "
        "profile unusable for older waylay-py versions."
    )
    ans = ask_yes_no(f"Migrate '{profile}' to use an api-gateway? [Y/n]", True)
    if not ans:
        tell(f"Not migrating configuration profile '{profile}'")
    return ans


def request_client_credentials_interactive(
    default_gateway_url: str = DEFAULT_GATEWAY_URL,
) -> WaylayCredentials:
    """Asks interactively for client credentials.

    Default callback provider for an interactive WaylayConfig.

    """
    tell("Authenticating to the Waylay Platform")
    gateway_url = ask_gateway(default_gateway_url)
    tell("Please provide client credentials for the waylay data client.")
    credentials = ClientCredentials(api_key="", api_secret="", gateway_url=gateway_url)
    retry = 0
    while not credentials.is_well_formed() and retry < 3:
        api_key = ask(prompt="> apiKey : ").strip()
        api_secret = ask_secret(prompt="> apiSecret : ").strip()
        credentials = ClientCredentials(
            api_key=api_key, api_secret=api_secret, gateway_url=gateway_url
        )
        if not credentials.is_well_formed():
            retry += 1
            if retry >= 3:
                tell("Too many attempts, failing authentication")
                raise AuthError("Too many attempts, failing authentication")
            tell("Invalid apiKey or apiSecret, please retry")
    return credentials


def request_store_config_interactive(profile, save_callback):
    """Save interactively the storage of credentials as a profile."""
    if ask_yes_no(
        f"> Do you want to store these credentials with profile={profile}? [Y]: ", True
    ):
        save_location = save_callback()
        tell(
            f"Credential configuration stored as \n\t{save_location}\n"
            "Please make sure this file is treated securely.\n"
            "If compromised, _Revoke_ the api-key on the Waylay Console!"
        )


def _gateway_url_for(url_input: str):
    """Infer the gateway url from user input or existing accounts url."""
    url_input = (url_input or "").lower()
    if "accounts-api" in url_input:
        url_input = url_input.replace("accounts-api", "api")
    elif url_input in ("api", "", "enterprise"):
        url_input = "api.waylay.io"
    elif re.match(r"^[a-z0-9]+$", url_input):
        url_input = f"api-{url_input}.waylay.io"
    return _root_url_for(url_input)


def _root_url_for(host_or_url: str) -> str:
    scheme, loc, path, query, fragment = urllib.parse.urlsplit(host_or_url)

    if not scheme and not loc:
        # make sure any host name is converted in a https:// url
        scheme = "https"
        loc = path
        path = ""

    if path.endswith("/"):
        # tenant settings root urls are without trailing slash
        log.warning("Trailing slashes trimmed: %s", host_or_url)
        path = path.rstrip("/")

    return urllib.parse.urlunsplit([scheme, loc, path, query, fragment])
