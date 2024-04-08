# Waylay Python SDK

Python SDK for the Waylay Platform.

This `waylay-sdk-core` package provides a basic SDK client for the [Waylay REST apis](https://docs.waylay.io/#/api/?id=openapi-docs). 

See [Waylay Docs](https://docs.waylay.io/#/api/sdk/python) for documentation.

## Installation

This package requires a python runtime `3.9` or higher.

The basic client can be installed with
```bash
pip install waylay-sdk-core
```

This client provides configuration, authorization and plugin features for the SDK.

It includes a generic http client to make authenticated calls to the services available on your _Waylay_ gateway endpoint.

Support for specific Waylay services or tools is provided by separate extension packages.

See [`waylay-sdk`](https://pypi.org/project/waylay-sdk) to install a client that includes the recommended extensions.

## Basic usage

### Interactive Authentication

When used outside the Waylay platform (e.g. in a _python notebook_) the client requires you to provide
* the gateway endpoint: `api.waylay.io` for Enterprise users,
* an API key-secret pair: see [Waylay Console](console.waylay.io) at _>Settings>Authentication keys_.

```python
from waylay.sdk import WaylayClient

# this will interactively request the gateway and credentials on first usage.
client = WaylayClient.from_profile()

# list the available service packages
client.services

# use the generic api client to see the status page of the 'registry' service.
resp = await client.api_client.request('GET', '/registry/v2')
```

Credentials and endpoints are stored in a local _profile_ file (you can have multiple such profiles).
Other authentication methods are available (JWToken, pass apiKey/Secret directly)

