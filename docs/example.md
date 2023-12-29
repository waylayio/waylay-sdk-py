```python
import os
import asyncio

from waylay import WaylayClient
from waylay.exceptions import RestResponseError
from waylay.api import ApiResponse

from waylay.service import registry


[api_key, api_secret] = os.environ["WU"].split(':')
waylay = WaylayClient.from_client_credentials(
    api_key=api_key, api_secret=api_secret, gateway_url='https://api-aws-dev.waylay.io')

async def main():
    try:
        # example of a request
        query: registry.types.queries.plug_functions.ListVersionsQuery = {'archive_format': ['node'], 'include_deprecated': True, 'limit': 500000}
        result = await waylay.registry.plug_functions.list_versions('test', query=query)
        print(result.entities[0].plug.name, result.entities[0].plug.version, result.entities[0].status)

        # example of a request where the result should include http info such as `status_code`, `raw_data`, ...
        result: ApiResponse[registry.types.ListPlugsWithQueryResponseV2] = await waylay.registry.plug_functions.list_versions('test', query=query, with_http_info=True)
        print(result.status_code)

        # example of a request that will result in an ApiError
        query: registry.types.queries.plug_functions.ListVersionsQuery = {'archive_format': ['node'], 'include_deprecated': True, 'limit': 500000}
        result = await waylay.registry.plug_functions.list_versions('test', query=query)
        
    except RestResponseError as e:
        print("Exception: %s" % e)

asyncio.run(main())

```