""" REST client implementation """

import httpx
from waylay.service.configuration import ApiConfig

from waylay.service.exceptions import ApiException, ApiValueError

RESTResponse = httpx.Response

class RESTClient:

    def __init__(self, configuration: ApiConfig) -> None:

        additional_httpx_kwargs = {
            "cert": configuration.cert_file,
            "verify": configuration.ssl_ca_cert,
        }

        self.client = httpx.AsyncClient(
            auth=configuration.waylay_config.auth,
            **additional_httpx_kwargs
        )

    async def request(
        self,
        method,
        url,
        query=None,
        headers=None,
        body=None,
        files=None,
        _request_timeout=None
    ) -> RESTResponse:
        """Perform requests.

        :param method: http request method
        :param url: http request url
        :param query: http query parameters
        :param headers: http request headers
        :param body: request json body, for `application/json`
        :param files: request file parameters (`multipart/form-data`)
        :param _request_timeout: timeout setting for this request. If one
                                 number provided, it will be total request
                                 timeout. It can also be a pair (tuple) of
                                 (connection, read) timeouts.
        """
        method = method.upper()
        headers = headers or {}

        assert method in [
            'GET',
            'HEAD',
            'DELETE',
            'POST',
            'PUT',
            'PATCH',
            'OPTIONS'
        ]

        if files and body:
            raise ApiValueError(
                "body parameter cannot be used with files parameter."
            )


        timeout = None
        if _request_timeout:
            if isinstance(_request_timeout, (int, float)):
                timeout = _request_timeout
            elif (
                    isinstance(_request_timeout, tuple)
                    and len(_request_timeout) == 2
                ):
                timeout = _request_timeout

        # For `POST`, `PUT`, `PATCH`, `OPTIONS`, `DELETE`
        if method in ['POST', 'PUT', 'PATCH', 'OPTIONS', 'DELETE']:
            content_type = headers.get('Content-Type')
            if content_type and content_type == 'multipart/form-data':
                return await self.client.request(
                    method,
                    url,
                    params=query,
                    files=files,
                    timeout=timeout,
                    headers=headers
                )
            else:
                return await self.client.request(
                        method,
                        url,
                        params=query,
                        data=body,
                        timeout=timeout,
                        headers=headers
                    )
        
        # For `GET`, `HEAD`
        else:
            return await self.client.request(
                method,
                url,
                params=query,
                timeout=timeout,
                headers=headers
            )
