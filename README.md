# Waylay Python SDK

Python SDK for the Waylay Platform.

This `waylay-sdk` package provides a basic SDK client for the [Waylay REST apis](https://docs.waylay.io/#/api/?id=openapi-docs). 

See [Waylay Docs](https://docs.waylay.io/#/api/sdk/python) for documentation.

## Installation

This package requires a python runtime `3.9` or higher.

The basic client can be installed with
```bash
pip install waylay-sdk
```

This client provides basic configuration, authorization and plugin features for the SDK.

It includes a generic http client to make authenticated calls to the services available on your _Waylay_ gateway endpoint.

Support for specific Waylay services or tools is provided by separate [service](#service-packages) and [tool](#tool-packages) packages.

## Basic usage

### In webscripts and plugins

The SDK client can be used in the _python_ webscripts and plugins of the Waylay platform.

In that case, the webscript or plugin _runtime_ will configure and authenticate a client, and 
provide it as a `waylay` parameter to the _webscript_ or _plugin_ callback function.

You just need to state the required SDK package dependencies when authoring the _webscript_ or _plugin_.

```python
async def execute(request: Request, waylay: WaylayClient):
    # list templates with the query as specified in the request body
    template_query = request.json()

    # with only the 'waylay-sdk' package:
    templates = await waylay.api_client('GET', '/rules/v1/templates', query=template_query)

    # with the 'waylay-rules-sdk' service plugin package
    # templates = await waylay.rules.templates.list(query=template_query)
    return templates
```

### Interactive Authentication
When used outside the Waylay platform (e.g. in a _python notebook_) the client requires you to provide
* the gateway endpoint: `api.waylay.io` for Enterprise users,
* an API key-secret pair: see [Waylay Console](console.waylay.io) at _>Settings>Authentication keys_.

```python
from waylay.sdk install WaylayClient

# this will interactively request the gateway and credentials on first usage.
client = WaylayClient.from_profile()

# list the available service packages
client.services

# use the generic api client to see the status page of the 'registry' service.
resp = await client.api_client.request('GET', '/registry/v2')
```

Credentials and endpoints are stored in a local _profile_ file (you can have multiple such profiles).
Other authentication methods are available (JWToken, pass apiKey/Secret directly)

## Service packages

Support for a specific Waylay REST api comes as a separate _service package_.
Each _service_ provides two packages:
* an _api_ package `waylay-<service>-sdk` that describes all resources and actions for that service. JSON request and responses are represented as basic python data (_dict_, _list_, primitives)
* a _types_ package `waylay-<service>-sdk-types` that provides [pydantic](https://docs.pydantic.dev/) models to represent JSON request and responses.

The _types_ package is optional. When installed, its _pydantic_ models are used to serialize requests and deserialize responses. When used in a python IDE, code completion will help you navigate the attributes of request and responses.
This makes it easier to interact with the API as a developer. 
But as the underlying REST api evolves, the _types_ package might require regular dependency updates.

Use the _types_ package for interactive cases (python notebooks), or solutions that are regularly tested and maintained. 

When not installed, the SDK client does not interfere with the json representations of requests and responses, and you should check the [API documentation](https://docs.waylay.io/#/api/?id=openapi-docs) of the service for exact specifications.

The Service plugs are _generated_ from their [openapi description](https://docs.waylay.io/#/api/?id=openapi-docs).

### `waylay-alarms-sdk` _Alarms_ api package

The [waylay-alarms-sdk](https://pypi.org/project/waylay-alarms-sdk) package provides the client bindings for the [Alarms](https://docs.waylay.io/#/api/alarms/) service, based on its [openapi](https://docs.waylay.io/openapi/public/redocly/alarms.html) specification.

```bash
## with types
pip install waylay-alarms-sdk[types]

## without types
pip install waylay-alarms-sdk
```

### `waylay-data-sdk` _Data_ (broker) api package

The [waylay-data-sdk](https://pypi.org/project/waylay-data-sdk) package provides the client bindings for the `data` api of the [broker](https://docs.waylay.io/#/api/broker/) service, based on its [openapi](https://docs.waylay.io/openapi/public/redocly/broker.html) specification.

```bash
## with types
pip install waylay-data-sdk[types]

## without types
pip install waylay-data-sdk
```

### `waylay-resources-sdk` _Resources_ (digital twin) api package

The [waylay-resources-sdk](https://pypi.org/project/waylay-resources-sdk) package provides the client bindings for the [resources](https://docs.waylay.io/#/api/resources/) service, based on its [openapi](https://docs.waylay.io/openapi/public/redocly/resources.html) specification.

```bash
## with types
pip install waylay-resources-sdk[types]

## without types
pip install waylay-resources-sdk
```

### `waylay-rules-sdk` _Rules_ (rules engine) api package

The [waylay-rules-sdk](https://pypi.org/project/waylay-rules-sdk) package provides the client bindings for the [rules](https://docs.waylay.io/#/api/rules/) service, based on its [openapi](https://docs.waylay.io/openapi/public/redocly/rules.html) specification.

```bash
## with types
pip install waylay-rules-sdk[types]

## without types
pip install waylay-rules-sdk
```

### `waylay-storage-sdk` _Storage_ (file object storage) api package

The [waylay-storage-sdk](https://pypi.org/project/waylay-storage-sdk) package provides the client bindings for the [storage](https://docs.waylay.io/#/api/storage/) service, based on its [openapi](https://docs.waylay.io/openapi/public/redocly/storage.html) specification.

```bash
## with types
pip install waylay-storage-sdk[types]

## without types
pip install waylay-storage-sdk
```

### `waylay-registry-sdk` _Function Registry V2_ api package

The [waylay-registry-sdk](https://pypi.org/project/waylay-registry-sdk) package provides the client bindings for the [registry v2](https://docs.waylay.io/#/api/registry/) service, based on its [openapi](https://docs.waylay.io/openapi/public/redocly/registry.html) specification.

```bash
## with types
pip install waylay-registry-sdk[types]

## without types
pip install waylay-registry-sdk
```


## Tool packages

Tool packages provide SDK extensions for specific use cases.


### `waylay-ml-adapter-sdk` _ML Adapter_ tool package

The [waylay-ml-adapter-sdk](https://pypi.org/project/waylay-ml-adapter-sdk) package provides utilities for using and deploying Machine Learning models in plugs and webscripts.

```bash
## basic install
pip install waylay-ml-adapter-sdk

## install with support for pytorch models
pip install waylay-ml-adapter-sdk[pytorch]

```
