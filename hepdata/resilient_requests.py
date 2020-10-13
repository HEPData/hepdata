# -*- coding: utf-8 -*-

from builtins import super

import requests

from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from hepdata.config import NGINX_TIMEOUT

DEFAULT_TIMEOUT = NGINX_TIMEOUT  # seconds
TOTAL_RETRIES = 8


class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self.timeout = DEFAULT_TIMEOUT
        if "timeout" in kwargs:
            self.timeout = kwargs["timeout"]
            del kwargs["timeout"]
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        timeout = kwargs.get("timeout")
        if timeout is None:
            kwargs["timeout"] = self.timeout
        return super().send(request, **kwargs)


retry_strategy = Retry(total=TOTAL_RETRIES,
                       backoff_factor=4,
                       status_forcelist=[429, 500, 502, 503, 504],
                       method_whitelist=["GET", "POST"])
adapter = TimeoutHTTPAdapter(max_retries=retry_strategy)


def resilient_requests(func, *args, **kwargs):
    with requests.Session() as session:
        session.mount("https://", adapter)
        response = getattr(session, func)(*args, **kwargs)
    return response
