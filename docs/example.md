```python
import os
import asyncio

from waylay.client import WaylayClient
from waylay.exceptions import RestResponseError

try:
    from waylay.services.registry.queries.plug_functions_api import ListVersionsQuery
    from waylay.services.registry.models import ListPlugsWithQueryResponseV2
    registry_types_available = True
except ImportError:
    registry_types_available = False


[api_key, api_secret] = os.environ["WU"].split(':')
waylay = WaylayClient.from_client_credentials(
    api_key=api_key, api_secret=api_secret, gateway_url='https://api-aws-dev.waylay.io')

async def main():
    try:
        # example of a request
        query_: 'ListVersionsQuery' = {'archive_format': ['node'], 'include_deprecated': True}
        result = await waylay.registry.plug_functions.list_versions('test', query=query_)
        print(type(result)) # `ListPlugsWithQueryResponseV2` if registry_types_available else `SimpleNamespace`
        print(result.entities[0].plug.name, result.entities[0].plug.version, result.entities[0].status)

        # example of a request where the result should include http info such as `status_code`, `raw_data`, ...
        result = await waylay.registry.plug_functions.list_versions('test', query=query_, with_http_info=True)
        print(result.status_code, result.data.entities[0].plug.name)

        # example of a request that will result in an ApiError
        bad_query: ListVersionsQuery = {'archive_format': ['node'], 'include_deprecated': True, 'limit': 500000}
        result = await waylay.registry.plug_functions.list_versions('test', query=bad_query)
        
    except RestResponseError as e:
        print("Exception: %s" % e)

asyncio.run(main())

```